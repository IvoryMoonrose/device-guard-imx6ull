import collections
import json
import threading
import time

from .engine import GuardEngine, validate_config
from .hardware import Icm20608, Indicators, ReplaySensor
from .storage import EventStore, load_config, save_config


class GuardService:
    def __init__(self, directory, replay=False, indicators=True):
        self.lock = threading.RLock()
        self.directory = directory
        self.store = EventStore(directory)
        try:
            self.engine = GuardEngine(load_config(directory))
        except ValueError:
            self.engine = GuardEngine()
        self.replay = replay
        self.source = 'replay' if replay else 'hardware'
        self.sensor = None
        self.outputs = Indicators(indicators)
        self.history = collections.deque(maxlen=150)
        self.pending = None
        self.active_event = None
        self.storage_error = ''
        self.last_sample = {}
        self.running = True
        self.thread = threading.Thread(target=self.loop)
        self.thread.daemon = True
        self.started = time.monotonic()
        self.last_history = 0
        self.sample_count = 0
        self.error_count = 0
        self.store.audit('start', self.source)

    def start(self):
        self.thread.start()

    def _record(self, event, now):
        if event['kind'] in ('calibrated', 'calibration_rejected'):
            self.store.audit(event['kind'], json.dumps(event))
            return
        before = [dict(point) for point in self.history if point['mono'] >= now-3]
        event_id = self.store.add(event, self.source, before)
        self.pending = {'id': event_id, 'until': now+3, 'samples': before}
        self.active_event = event_id

    def loop(self):
        while self.running:
            cycle_start = time.monotonic()
            try:
                if self.sensor is None:
                    self.sensor = ReplaySensor() if self.replay else Icm20608()
                sample = self.sensor.read()
                with self.lock:
                    self.last_sample = sample
                    self.sample_count += 1
                    event = self.engine.feed(sample, cycle_start)
            except (OSError, ValueError, RuntimeError) as exc:
                with self.lock:
                    self.error_count += 1
                    event = self.engine.failure(cycle_start, str(exc))
                if self.sensor is not None and not self.replay:
                    try:
                        self.sensor.close()
                    except OSError:
                        pass
                    self.sensor = None
            with self.lock:
                try:
                    if cycle_start-self.last_history >= 0.2:
                        self.last_history = cycle_start
                        point = {'mono': round(cycle_start, 3), 't': round(cycle_start-self.started, 2),
                                 'angle': round(self.engine.angle, 2), 'motion': round(self.engine.motion, 3), 'gyro': round(self.engine.gyro, 2)}
                        self.history.append(point)
                        if self.pending:
                            self.pending['samples'].append(point)
                    if event:
                        self._record(event, cycle_start)
                    if self.pending and cycle_start >= self.pending['until']:
                        self.store.finish(self.pending['id'], self.pending['samples'])
                        self.pending = None
                except Exception as exc:
                    self.storage_error = str(exc)
                self.outputs.update(self.engine.state, cycle_start, self.engine.config['sound_enabled'], self.engine.muted)
            time.sleep(max(0.001, 0.02-(time.monotonic()-cycle_start)))

    def snapshot(self):
        with self.lock:
            result = self.engine.status(time.monotonic())
            result.update({'config': dict(self.engine.config), 'source': self.source,
                           'source_text': '回放测试' if self.replay else '实机采集',
                           'history': list(self.history), 'events': self.store.list(8),
                           'event_count': self.store.count(), 'active_event': self.active_event,
                           'time_text': time.strftime('%Y-%m-%d %H:%M:%S'),
                           'uptime_seconds': int(time.monotonic()-self.started),
                           'sample_count': self.sample_count, 'error_count': self.error_count,
                           'storage_error': self.storage_error, 'outputs': sorted(self.outputs.paths),
                           'accel': self.last_sample.get('accel', [0, 0, 0]),
                           'gyro_axes': self.last_sample.get('gyro', [0, 0, 0])})
            return result

    def action(self, name):
        with self.lock:
            self.engine.action(name, time.monotonic())
            if name == 'disarm' and self.active_event:
                self.store.acknowledge(self.active_event)
                self.active_event = None
            self.store.audit(name)
        return self.snapshot()

    def configure(self, changes):
        with self.lock:
            if self.engine.state != 'DISARMED':
                raise ValueError('请先撤防，再修改监测参数')
            config = validate_config(changes, self.engine.config)
            save_config(self.directory, config)
            self.engine.config = config
            self.store.audit('config', json.dumps(config))
        return self.snapshot()

    def acknowledge(self, event_id):
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id < 1:
            raise ValueError('事件编号无效')
        with self.lock:
            if self.store.detail(event_id) is None:
                raise ValueError('记录不存在')
            self.store.acknowledge(event_id)
            self.store.audit('acknowledge', str(event_id))
            return self.store.detail(event_id)

    def replay_scenario(self, name):
        if not self.replay:
            raise ValueError('实机模式不接受回放输入')
        with self.lock:
            if not isinstance(self.sensor, ReplaySensor):
                raise ValueError('回放传感器尚未就绪')
            self.sensor.set_scenario(name)
        return self.snapshot()

    def close(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(2)
        with self.lock:
            if self.pending:
                self.store.finish(self.pending['id'], self.pending['samples'])
            self.outputs.close()
            if self.sensor:
                self.sensor.close()
            self.store.audit('stop')
            self.store.close()
