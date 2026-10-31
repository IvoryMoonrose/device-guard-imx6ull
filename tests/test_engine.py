import math
import os
import sys
import tempfile
import unittest

source = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, source if os.path.isdir(source) else os.path.join(os.path.dirname(__file__), '..'))
from guard.engine import GuardEngine, validate_config
from guard.storage import EventStore, load_config, save_config
from guard.sqlite_compat import connect


def reading(angle=0, rotation=0, x=0):
    radians = math.radians(angle)
    return {'accel': [math.sin(radians)+x, 0, math.cos(radians)], 'gyro': [0, rotation, 0]}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = GuardEngine()
        self.now = 0
        self.events = []
        self.advance(0.1)

    def advance(self, seconds, sample=None):
        for unused in range(int(seconds/0.02)+1):
            self.now += 0.02
            event = self.engine.feed(reading() if sample is None else sample, self.now)
            if event:
                self.events.append(event)

    def calibrate(self, sample=None):
        self.engine.action('calibrate', self.now)
        self.advance(2.2, sample)
        self.assertTrue(self.engine.baseline is not None)

    def arm(self):
        self.engine.action('arm', self.now)
        self.advance(5.2)
        self.assertEqual(self.engine.state, 'ARMED')

    def test_requires_calibration(self):
        with self.assertRaises(ValueError):
            self.engine.action('arm', self.now)

    def test_static_twenty_seconds_no_alarm(self):
        self.calibrate(); self.arm(); self.advance(20)
        self.assertEqual(self.engine.state, 'ARMED')

    def test_short_tap_not_accumulated(self):
        self.calibrate(); self.arm()
        for unused in range(5):
            self.advance(0.10, reading(rotation=80, x=0.55))
            self.advance(1.0)
        self.assertEqual(self.engine.state, 'ARMED')

    def test_sustained_tilt_and_latched_alarm(self):
        self.calibrate(); self.arm()
        start = self.now
        self.advance(2.0, reading(angle=28))
        self.assertEqual(self.engine.state, 'ALARM')
        self.assertEqual(self.events[-1]['kind'], 'tilt')
        self.advance(3)
        self.assertEqual(self.engine.state, 'ALARM')
        self.engine.action('mute', self.now)
        self.assertTrue(self.engine.muted)
        self.assertEqual(self.engine.state, 'ALARM')
        self.engine.action('disarm', self.now)
        self.assertEqual(self.engine.state, 'DISARMED')
        self.assertLess(self.now-start, 5.5)

    def test_sustained_rotation(self):
        self.calibrate(); self.arm()
        self.advance(1.1, reading(rotation=42))
        self.assertEqual(self.engine.state, 'ALARM')
        self.assertEqual(self.events[-1]['kind'], 'motion')

    def test_calibration_accepts_different_orientation(self):
        self.calibrate(reading(angle=35))
        self.engine.action('arm', self.now)
        self.advance(8, reading(angle=35))
        self.assertEqual(self.engine.state, 'ARMED')
        self.assertLess(self.engine.angle, 0.01)

    def test_moving_calibration_rejected(self):
        self.engine.action('calibrate', self.now)
        self.advance(2.2, reading(rotation=20))
        self.assertIsNone(self.engine.baseline)
        self.assertEqual(self.events[-1]['kind'], 'calibration_rejected')

    def test_countdown_does_not_alarm(self):
        self.calibrate()
        self.engine.action('arm', self.now)
        self.advance(4.8, reading(rotation=90))
        self.assertEqual(self.engine.state, 'ARMING')
        self.engine.action('disarm', self.now)
        self.advance(2)
        self.assertEqual(self.engine.state, 'DISARMED')

    def test_fault_and_recovery_never_rearms(self):
        self.calibrate(); self.arm()
        event = None
        for unused in range(20):
            self.now += 0.02
            new_event = self.engine.failure(self.now, 'test disconnect')
            event = new_event or event
        self.assertEqual(self.engine.state, 'FAULT')
        self.assertTrue(event['was_active'])
        self.advance(2.3)
        self.assertEqual(self.engine.state, 'DISARMED')
        self.assertIsNone(self.engine.baseline)

    def test_invalid_acceleration_rejected(self):
        self.calibrate(); self.arm()
        self.advance(0.6, {'accel': [0, 0, 0], 'gyro': [0, 0, 0]})
        self.assertEqual(self.engine.state, 'FAULT')

    def test_configuration_rejects_bad_values(self):
        for change in ({'tilt_deg': 0}, {'motion_g': float('nan')}, {'arming_seconds': True}, {'unknown': 4}, {'sound_enabled': 1}):
            with self.assertRaises(ValueError):
                validate_config(change)


class PersistenceTests(unittest.TestCase):
    def test_configuration_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            config = validate_config({'tilt_deg': 22})
            save_config(directory, config)
            self.assertEqual(load_config(directory)['tilt_deg'], 22)

    def test_events_survive_reopen_and_source_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(directory)
            key = store.add({'kind': 'tilt', 'reason': '持续倾斜', 'angle': 26}, 'replay', [{'angle': 15}])
            store.finish(key, [{'angle': 15}, {'angle': 26}])
            store.acknowledge(key)
            store.close()
            store = EventStore(directory)
            event = store.detail(key)
            self.assertEqual(event['source'], 'replay')
            self.assertEqual(len(event['samples']), 2)
            self.assertTrue(event['acknowledged'])
            self.assertIn('回放测试', store.export_csv().decode('utf8'))
            store.close()

    @unittest.skipUnless(os.name == 'posix', 'Native fallback requires Linux libsqlite3')
    def test_native_sqlite_binding_unicode_null_float(self):
        with tempfile.TemporaryDirectory() as directory:
            database = connect(os.path.join(directory, 'native.db'), force_native=True)
            database.execute('CREATE TABLE sample(id INTEGER PRIMARY KEY, text_value TEXT, nullable TEXT, number REAL)')
            database.execute('INSERT INTO sample(text_value,nullable,number) VALUES(?,?,?)', ("中文与引号'保持原样", None, 1.25))
            row = database.execute('SELECT * FROM sample').fetchone()
            self.assertEqual(row['text_value'], "中文与引号'保持原样")
            self.assertIsNone(row['nullable'])
            self.assertEqual(row['number'], 1.25)
            self.assertEqual(row[0], 1)
            self.assertEqual(dict(row)['id'], 1)
            database.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
