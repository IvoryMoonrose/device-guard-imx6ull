#!/usr/bin/env python3
"""Run the course project and restore the previous factory desktop on exit."""
import os
import sys

if __name__ == '__main__':
    _native = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'device_guard_launcher')
    if os.path.isfile(_native) and os.access(_native, os.X_OK):
        os.execv(_native, [_native] + sys.argv[1:])

import argparse
import glob
import json
import signal
import subprocess
import time
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    base = os.path.dirname(os.path.abspath(__file__))
    runtime = os.path.join(base, 'runtime')
    os.makedirs(runtime, exist_ok=True)
    pid_file = os.path.join(runtime, 'launcher.pid')
    if os.path.exists(pid_file):
        try:
            old = int(open(pid_file).read())
            if b'launcher.py' in open('/proc/%s/cmdline' % old, 'rb').read():
                raise RuntimeError('Device Guard is already running')
        except (OSError, ValueError):
            pass
    with open(pid_file, 'w') as stream:
        stream.write(str(os.getpid()))
    previous = []
    backend = view = None
    saved_fb = None
    stopped = [False]
    def stop(signum, frame):
        stopped[0] = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    environment = os.environ.copy()
    environment.update({'QT_QUICK_BACKEND': 'software', 'QT_QPA_FB_TSLIB': '1',
                        'QT_QPA_FONTDIR': '/usr/share/fonts/ttf',
                        'QT_QPA_PLATFORM': 'linuxfb:tty=/dev/fb0',
                        'TSLIB_TSDEVICE': '/dev/input/event1', 'DISPLAY': ':0.0'})
    logs = []
    try:
        # The supplied image keeps the matching sensor driver under /home/root,
        # but does not load it automatically after a power cycle.
        if not args.replay and not os.path.exists('/dev/icm20608'):
            module = '/home/root/driver/icm20608/icm20608.ko'
            if os.path.isfile(module):
                subprocess.check_call(['/sbin/insmod', module])
        backend_log = open(os.path.join(runtime, 'backend.log'), 'a')
        gui_log = open(os.path.join(runtime, 'gui.log'), 'a')
        logs.extend([backend_log, gui_log])
        data = os.path.join(base, 'replay_data' if args.replay else 'data')
        command = [sys.executable, os.path.join(base, 'run.py'), '--data', data]
        if args.replay:
            command.extend(['--replay', '--no-indicators'])
        backend = subprocess.Popen(command, cwd=base, stdout=backend_log, stderr=subprocess.STDOUT)
        for unused in range(50):
            if backend.poll() is not None:
                raise RuntimeError('Backend did not start; see runtime/backend.log')
            try:
                urlopen('http://127.0.0.1:18765/api/state', timeout=0.2).read()
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError('Backend startup timeout')
        for directory in glob.glob('/proc/[0-9]*'):
            try:
                argv = open(directory+'/cmdline', 'rb').read()
                if argv.startswith(b'/opt/ui/') and 'libQt5Gui' in open(directory+'/maps').read():
                    pid = int(directory.split('/')[-1])
                    previous.append({'pid': pid, 'argv': argv.decode('utf8', 'replace')})
                    os.kill(pid, signal.SIGSTOP)
            except OSError:
                pass
        with open(os.path.join(runtime, 'previous_gui.json'), 'w') as stream:
            json.dump(previous, stream)
        try:
            with open('/dev/fb0', 'rb', buffering=0) as stream:
                saved_fb = stream.read(1024*600*2)
        except OSError:
            pass
        view = subprocess.Popen(['/usr/bin/qmlscene', os.path.join(base, 'ui', 'Main.qml')],
                                cwd=base, env=environment, stdout=gui_log, stderr=subprocess.STDOUT)
        with open(os.path.join(runtime, 'gui.pid'), 'w') as stream:
            stream.write(str(view.pid))
        while not stopped[0] and view.poll() is None and backend.poll() is None:
            time.sleep(0.2)
    finally:
        if view is not None and view.poll() is None:
            view.terminate()
            try:
                view.wait(timeout=3)
            except subprocess.TimeoutExpired:
                view.kill(); view.wait()
        if backend is not None and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill(); backend.wait()
        try:
            with open('/sys/class/leds/beep/brightness', 'w') as stream:
                stream.write('0')
        except OSError:
            pass
        for entry in previous:
            try:
                current = open('/proc/%s/cmdline' % entry['pid'], 'rb').read().decode('utf8', 'replace')
                if current == entry['argv']:
                    os.kill(entry['pid'], signal.SIGCONT)
            except OSError:
                pass
        if saved_fb:
            try:
                with open('/dev/fb0', 'r+b', buffering=0) as stream:
                    stream.write(saved_fb)
            except OSError:
                pass
        if os.path.exists(pid_file) and open(pid_file).read().strip() == str(os.getpid()):
            os.unlink(pid_file)
        for stream in logs:
            stream.close()


if __name__ == '__main__':
    main()
