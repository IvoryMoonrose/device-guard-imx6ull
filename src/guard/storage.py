import csv
import io
import json
import os
import threading
import time
from .sqlite_compat import connect

LABELS = {'tilt': '持续倾斜', 'motion': '持续搬动', 'combined': '倾斜与搬动', 'sensor_fault': '传感器断流'}


class EventStore:
    def __init__(self, directory):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self.lock = threading.RLock()
        self.db = connect(os.path.join(directory, 'events.sqlite3'))
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL, reason TEXT NOT NULL, angle REAL, motion REAL, gyro REAL, acknowledged REAL, samples TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, created REAL, action TEXT, detail TEXT)')
        self.db.commit()

    def add(self, event, source, samples):
        with self.lock:
            cursor = self.db.execute('INSERT INTO events(created,kind,source,reason,angle,motion,gyro,samples) VALUES(?,?,?,?,?,?,?,?)',
                (time.time(), event['kind'], source, event.get('reason', ''), event.get('angle', 0), event.get('motion', 0), event.get('gyro', 0), json.dumps(samples)))
            self.db.commit()
            return cursor.lastrowid

    def finish(self, event_id, samples):
        with self.lock:
            self.db.execute('UPDATE events SET samples=? WHERE id=?', (json.dumps(samples), event_id))
            self.db.commit()

    def acknowledge(self, event_id):
        with self.lock:
            self.db.execute('UPDATE events SET acknowledged=? WHERE id=?', (time.time(), event_id))
            self.db.commit()

    def audit(self, action, detail=''):
        with self.lock:
            self.db.execute('INSERT INTO audit(created,action,detail) VALUES(?,?,?)', (time.time(), action, detail))
            self.db.commit()

    @staticmethod
    def present(row):
        result = dict(row)
        result['time_text'] = time.strftime('%m-%d %H:%M:%S', time.localtime(result['created']))
        result['kind_text'] = LABELS.get(result['kind'], result['kind'])
        result['source_text'] = '实机采集' if result['source'] == 'hardware' else '回放测试'
        return result

    def list(self, limit=50):
        with self.lock:
            rows = self.db.execute('SELECT id,created,kind,source,reason,angle,motion,gyro,acknowledged FROM events ORDER BY id DESC LIMIT ?', (min(200, max(1, limit)),)).fetchall()
            return [self.present(row) for row in rows]

    def detail(self, event_id):
        with self.lock:
            row = self.db.execute('SELECT * FROM events WHERE id=?', (int(event_id),)).fetchone()
            if row is None:
                return None
            result = self.present(row)
            result['samples'] = json.loads(result['samples'])
            return result

    def count(self):
        with self.lock:
            return self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]

    def export_csv(self):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['事件编号', '时间', '事件类型', '数据来源', '原因', '倾斜角度_deg', '动态加速度_g', '角速度_dps', '已确认'])
        with self.lock:
            rows = self.db.execute('SELECT * FROM events ORDER BY id DESC').fetchall()
            for row in rows:
                event = self.present(row)
                writer.writerow([event['id'], time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event['created'])), event['kind_text'], event['source_text'], event['reason'], event['angle'], event['motion'], event['gyro'], '是' if event['acknowledged'] else '否'])
        return ('\ufeff'+stream.getvalue()).encode('utf8')

    def close(self):
        with self.lock:
            self.db.close()


def save_config(directory, config):
    path = os.path.join(directory, 'config.json')
    temporary = path+'.new'
    with open(temporary, 'w') as stream:
        json.dump(config, stream, ensure_ascii=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_config(directory):
    try:
        with open(os.path.join(directory, 'config.json')) as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {}
