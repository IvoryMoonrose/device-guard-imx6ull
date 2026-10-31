"""Measure the real desktop touch to service / framebuffer, then exit cleanly."""
import argparse
import json
import os
import re
import struct
import time
from urllib.request import Request, urlopen

BASE = '/opt/device_guard'


def touch(x, y):
    fd = os.open('/dev/input/event1', os.O_WRONLY)
    try:
        for kind, code, value in [(3, 47, 0), (3, 57, 113), (3, 53, x), (3, 54, y), (0, 0, 0)]:
            os.write(fd, struct.pack('llHHi', 0, 0, kind, code, value))
        time.sleep(.06)
        for kind, code, value in [(3, 47, 0), (3, 57, -1), (0, 0, 0)]:
            os.write(fd, struct.pack('llHHi', 0, 0, kind, code, value))
    finally:
        os.close(fd)


def frame_samples():
    with open('/dev/fb0', 'rb', buffering=0) as stream:
        data = stream.read(1024 * 600 * 2)
    return [data[(y*1024+x)*2:(y*1024+x)*2+2]
            for y in range(120, 500, 30) for x in range(200, 800, 30)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='baseline')
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--leave-open', action='store_true')
    args = parser.parse_args()
    results = []
    for run in range(args.runs):
        if os.path.exists(BASE+'/runtime/launcher.pid'):
            raise RuntimeError('Exit the project before measuring desktop startup')
        before = frame_samples()
        gui_log=BASE+'/runtime/gui.log'
        log_start=os.path.getsize(gui_log) if os.path.exists(gui_log) else 0
        wall_start=time.time()
        t0 = time.monotonic()
        touch(117, 124)
        timings = {}
        state = None
        while time.monotonic()-t0 < 40:
            elapsed = time.monotonic()-t0
            if 'launcher_s' not in timings and os.path.exists(BASE+'/runtime/launcher.pid'):
                timings['launcher_s'] = round(elapsed, 3)
            if 'service_s' not in timings:
                try:
                    state = json.loads(urlopen('http://127.0.0.1:18765/api/state', timeout=.08).read().decode('utf8'))
                    timings['service_s'] = round(time.monotonic()-t0, 3)
                except OSError:
                    pass
            if 'first_frame_s' not in timings and os.path.exists(BASE+'/runtime/gui.pid'):
                now = frame_samples()
                if sum(a != b for a, b in zip(before, now)) > len(now)*.6:
                    timings['first_frame_s'] = round(time.monotonic()-t0, 3)
            if args.label!='baseline' and 'ui_data_s' not in timings:
                try:
                    with open(gui_log) as stream:
                        stream.seek(log_start)
                        ready=re.search(r'GUARD_UI_READY\s+(\d+)',stream.read())
                    if ready:timings['ui_data_s']=round(int(ready.group(1))/1000.-wall_start,3)
                except OSError:pass
            if 'first_frame_s' in timings and 'service_s' in timings and (args.label=='baseline' or 'ui_data_s' in timings):
                break
            time.sleep(.04)
        assert state is not None and state['sensor_ok'] and not state['config']['sound_enabled'], state
        assert 'first_frame_s' in timings, timings
        if args.label!='baseline':
            paused=json.load(open(BASE+'/runtime/previous_gui.json'))
            assert any(entry['argv'].startswith('/opt/ui/systemui\0') for entry in paused)
            assert all('T (stopped)' in open('/proc/%s/status'%entry['pid']).read() for entry in paused)
            timings['paused_factory_gui_count']=len(paused)
        time.sleep(.3)
        timings.update(run=run+1, source=state['source'])
        results.append(timings)
        print(json.dumps(timings), flush=True)
        if args.leave_open and run==args.runs-1:
            break
        urlopen(Request('http://127.0.0.1:18765/api/shutdown', data=b'{}', headers={'Content-Type':'application/json'}), timeout=3).read()
        for unused in range(100):
            if not os.path.isfile(BASE+'/runtime/launcher.pid'):
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Desktop did not restore')
        time.sleep(.8)
    directory = BASE+'/evidence/startup'
    os.makedirs(directory, exist_ok=True)
    with open(directory+'/'+args.label+'.json', 'w') as stream:
        json.dump(results, stream, indent=2)


if __name__ == '__main__':
    main()
