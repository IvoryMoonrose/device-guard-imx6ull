import ctypes
import glob
import math
import os
import re
import time


class Icm20608:
    def __init__(self, path='/dev/icm20608'):
        self.fd = os.open(path, os.O_RDONLY)
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.read.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
        self.libc.read.restype = ctypes.c_ssize_t

    def read(self):
        sentinel = 0x5A5A5A5A
        data = (ctypes.c_int32*7)(*([sentinel]*7))
        result = self.libc.read(self.fd, data, ctypes.sizeof(data))
        if result < 0:
            raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
        if any(value == sentinel for value in data):
            raise IOError('六轴设备未写入完整的28字节数据')
        # Factory driver config: +/-2000 dps (16.4 LSB/dps), +/-16 g (2048 LSB/g).
        return {'gyro': [data[i]/16.4 for i in range(3)],
                'accel': [data[i]/2048.0 for i in range(3, 6)],
                'chip_temperature': data[6]/326.8+25,
                'raw': list(data)}

    def close(self):
        os.close(self.fd)


class ReplaySensor:
    def __init__(self):
        self.started = time.monotonic()
        self.scenario = 'static'
        self.scenario_started = self.started

    def set_scenario(self, name):
        if name not in ('static', 'tilt', 'motion', 'tap', 'fault'):
            raise ValueError('未知回放场景')
        self.scenario = name
        self.scenario_started = time.monotonic()

    def read(self):
        elapsed = time.monotonic()-self.scenario_started
        if self.scenario == 'fault':
            raise IOError('回放测试：模拟传感器断流')
        angle = math.radians(28) if self.scenario == 'tilt' else 0
        accel = [math.sin(angle), 0, math.cos(angle)]
        gyro = [0, 0, 0]
        if self.scenario == 'motion':
            gyro = [0, 42, 0]
            accel[0] += 0.28*math.sin(elapsed*25)
        if self.scenario == 'tap' and elapsed < 0.12:
            gyro = [0, 65, 0]
            accel[0] += 0.5
        return {'gyro': gyro, 'accel': accel, 'chip_temperature': 30, 'raw': None}

    def close(self):
        pass


class Indicators:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.paths = {}
        self.original = {}
        self.last = {}
        for path in glob.glob('/sys/class/leds/*') if enabled else []:
            name = os.path.basename(path)
            if name == 'beep':
                key = 'buzzer'
            elif name in ('sys-led', 'red', 'led0', 'led'):
                key = 'led'
            else:
                continue
            self.paths[key] = path
            self.original[key] = {'brightness': self._read(path+'/brightness')}
            trigger = self._read(path+'/trigger')
            selected = re.search(r'\[([^\]]+)\]', trigger or '')
            if selected:
                self.original[key]['trigger'] = selected.group(1)
                self._write(path+'/trigger', 'none')

    @staticmethod
    def _read(path):
        try:
            with open(path) as stream:
                return stream.read().strip()
        except OSError:
            return None

    @staticmethod
    def _write(path, value):
        try:
            with open(path, 'w') as stream:
                stream.write(str(value))
            return True
        except OSError:
            return False

    def update(self, state, now, sound, muted):
        alarm = state in ('ALARM', 'FAULT')
        buzzer = alarm and sound and not muted and (now % 1.2 < 0.18 or 0.3 < now % 1.2 < 0.48)
        led = (int(now*6) % 2 == 0) if alarm else ((int(now*2) % 2 == 0) if state in ('ARMED', 'ARMING') else False)
        for name, active in (('buzzer', buzzer), ('led', led)):
            if name in self.paths and self.last.get(name) != int(active):
                self._write(self.paths[name]+'/brightness', int(active))
                self.last[name] = int(active)

    def close(self):
        for name, path in self.paths.items():
            self._write(path+'/brightness', 0 if name == 'buzzer' else self.original[name].get('brightness', '0'))
            if 'trigger' in self.original[name]:
                self._write(path+'/trigger', self.original[name]['trigger'])
