"""Deterministic, I/O-free alarm state machine; all durations use monotonic time."""
import math

DEFAULTS = {
    'tilt_deg': 15.0, 'motion_g': 0.18, 'gyro_dps': 25.0,
    'tilt_hold_ms': 1200, 'motion_hold_ms': 800, 'arming_seconds': 5,
    'sound_enabled': False, 'calibration_seconds': 2.0,
}
LIMITS = {
    'tilt_deg': (5, 60), 'motion_g': (0.08, 1.5), 'gyro_dps': (10, 180),
    'tilt_hold_ms': (300, 5000), 'motion_hold_ms': (300, 5000),
    'arming_seconds': (3, 30), 'calibration_seconds': (1, 5),
}
STATE_TEXT = {'DISARMED': '未布防', 'CALIBRATING': '静止校准中',
              'ARMING': '布防倒计时', 'ARMED': '正在监测',
              'ALARM': '检测到异常', 'FAULT': '传感器异常'}


def norm(vector):
    return math.sqrt(sum(v*v for v in vector))


def validate_config(changes, current=None):
    result = dict(DEFAULTS if current is None else current)
    for key, value in changes.items():
        if key == 'sound_enabled':
            if not isinstance(value, bool):
                raise ValueError('声音开关必须是布尔值')
        elif key in LIMITS:
            low, high = LIMITS[key]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('%s应在%s～%s之间' % (key, low, high))
            if key.endswith('_ms') or key == 'arming_seconds':
                value = int(value)
        else:
            raise ValueError('未知参数：' + key)
        result[key] = value
    return result


class GuardEngine:
    def __init__(self, config=None):
        self.config = validate_config(config or {})
        self.state = 'DISARMED'
        self.message = '请将设备放稳，先完成静止校准'
        self.baseline = None
        self.gravity = None
        self.last_t = None
        self.last_good = None
        self.cal_start = None
        self.cal_samples = []
        self.arm_deadline = None
        self.error_start = None
        self.recovery_start = None
        self.tilt_since = None
        self.motion_since = None
        self.angle = 0.0
        self.motion = 0.0
        self.gyro = 0.0
        self.muted = False
        self.alarm_reason = ''
        self.sensor_ok = False
        self.cal_progress = 0.0

    def action(self, name, now):
        if name == 'disarm':
            self.state = 'DISARMED' if self.sensor_ok else 'FAULT'
            self.message = '已撤防，报警已确认' if self.sensor_ok else '已撤防，请检查传感器'
            self.muted = False
            self.tilt_since = self.motion_since = None
            self.arm_deadline = None
            self.alarm_reason = ''
        elif name == 'mute':
            self.muted = True
            self.message = '声音已关闭，异常状态仍然保留'
        elif name == 'calibrate':
            if self.state not in ('DISARMED',) or not self.sensor_ok:
                raise ValueError('请先撤防并确认传感器正常，再进行校准')
            self.state = 'CALIBRATING'
            self.cal_start = now
            self.cal_samples = []
            self.cal_progress = 0.0
            self.message = '请保持设备静止'
        elif name == 'arm':
            if self.state != 'DISARMED' or not self.sensor_ok or self.baseline is None:
                raise ValueError('请先撤防并完成静止校准')
            self.state = 'ARMING'
            self.arm_deadline = now + self.config['arming_seconds']
            self.muted = False
            self.message = '倒计时结束后开始监测，可以点击撤防取消'
        else:
            raise ValueError('未知操作')

    def failure(self, now, detail):
        self.sensor_ok = False
        self.recovery_start = None
        if self.error_start is None:
            self.error_start = now
        if now - self.error_start >= 0.3 and self.state not in ('FAULT', 'ALARM'):
            was_active = self.state in ('ARMED', 'ARMING')
            self.state = 'FAULT'
            self.baseline = None
            self.message = '传感器数据中断，请检查接口；恢复后需要重新校准'
            self.tilt_since = self.motion_since = None
            return {'kind': 'sensor_fault', 'reason': detail, 'was_active': was_active}
        return None

    def feed(self, sample, now):
        accel = sample['accel']
        gyro = sample['gyro']
        if len(accel) != 3 or len(gyro) != 3 or not all(math.isfinite(v) for v in accel + gyro) or norm(accel) < 0.05:
            return self.failure(now, '传感器返回无效数据')
        self.last_good = now
        self.error_start = None
        self.sensor_ok = True
        dt = 0.02 if self.last_t is None else max(0.001, min(0.25, now-self.last_t))
        self.last_t = now
        if self.gravity is None:
            self.gravity = list(accel)
        alpha = 1.0 - math.exp(-dt / 0.25)
        self.gravity = [old + alpha*(new-old) for old, new in zip(self.gravity, accel)]
        self.motion = norm([v-g for v, g in zip(accel, self.gravity)])
        self.gyro = norm(gyro)
        if self.baseline is not None:
            cosine = sum(a*b for a, b in zip(self.gravity, self.baseline)) / max(1e-9, norm(self.gravity)*norm(self.baseline))
            self.angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        if self.state == 'FAULT':
            if self.recovery_start is None:
                self.recovery_start = now
            if now-self.recovery_start >= 2.0:
                self.state = 'DISARMED'
                self.message = '数据已恢复，请重新静止校准后布防'
            return None
        if self.state == 'CALIBRATING':
            self.cal_samples.append((list(accel), self.gyro))
            self.cal_progress = min(1.0, (now-self.cal_start)/self.config['calibration_seconds'])
            if self.cal_progress >= 1:
                means = [sum(row[0][axis] for row in self.cal_samples)/len(self.cal_samples) for axis in range(3)]
                deviations = [math.sqrt(sum((row[0][axis]-means[axis])**2 for row in self.cal_samples)/len(self.cal_samples)) for axis in range(3)]
                stable = max(deviations) < 0.03 and max(row[1] for row in self.cal_samples) < 8 and 0.7 < norm(means) < 1.3
                self.state = 'DISARMED'
                if stable:
                    self.baseline = means
                    self.gravity = list(means)
                    self.angle = 0.0
                    self.message = '校准完成，可以布防'
                    return {'kind': 'calibrated', 'baseline': means}
                self.baseline = None
                self.message = '校准时检测到运动，请放稳后重试'
                return {'kind': 'calibration_rejected'}
            return None
        if self.state == 'ARMING':
            if now >= self.arm_deadline:
                self.state = 'ARMED'
                self.message = '监测中：持续倾斜或搬动将触发报警'
                self.tilt_since = self.motion_since = None
            return None
        if self.state != 'ARMED':
            return None
        if self.angle >= self.config['tilt_deg'] and self.tilt_since is None:
            self.tilt_since = now
        elif self.angle < self.config['tilt_deg']*0.7:
            self.tilt_since = None
        moving = self.motion >= self.config['motion_g'] or self.gyro >= self.config['gyro_dps']
        settled = self.motion < self.config['motion_g']*0.7 and self.gyro < self.config['gyro_dps']*0.7
        if moving and self.motion_since is None:
            self.motion_since = now
        elif settled:
            self.motion_since = None
        tilt_hit = self.tilt_since is not None and (now-self.tilt_since)*1000 >= self.config['tilt_hold_ms']
        move_hit = self.motion_since is not None and (now-self.motion_since)*1000 >= self.config['motion_hold_ms']
        if tilt_hit or move_hit:
            kind = 'combined' if tilt_hit and move_hit else ('tilt' if tilt_hit else 'motion')
            self.alarm_reason = {'tilt': '持续倾斜超过阈值', 'motion': '持续搬动或旋转', 'combined': '倾斜与搬动同时异常'}[kind]
            self.state = 'ALARM'
            self.message = '报警已锁存，请确认设备安全后撤防'
            return {'kind': kind, 'reason': self.alarm_reason, 'angle': round(self.angle, 2), 'motion': round(self.motion, 3), 'gyro': round(self.gyro, 2)}
        return None

    def status(self, now):
        return {'state': self.state, 'state_text': STATE_TEXT[self.state], 'message': self.message,
                'sensor_ok': self.sensor_ok, 'calibrated': self.baseline is not None,
                'angle': round(self.angle, 2), 'motion': round(self.motion, 3), 'gyro': round(self.gyro, 2),
                'countdown': max(0, int(math.ceil(self.arm_deadline-now))) if self.state == 'ARMING' else 0,
                'cal_progress': round(self.cal_progress, 3), 'muted': self.muted,
                'alarm_reason': self.alarm_reason,
                'tilt_progress': min(1.0, (now-self.tilt_since)*1000/self.config['tilt_hold_ms']) if self.tilt_since is not None else 0,
                'motion_progress': min(1.0, (now-self.motion_since)*1000/self.config['motion_hold_ms']) if self.motion_since is not None else 0}
