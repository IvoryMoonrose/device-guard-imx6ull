"""Inspect or stop only this project's launcher from an SSH session."""
import argparse
import json
import os
import signal
import time
from urllib.request import urlopen

parser=argparse.ArgumentParser();parser.add_argument('action',choices=['status','stop']);args=parser.parse_args()
path='/opt/device_guard/runtime/launcher.pid'
pid=None
try:
    candidate=int(open(path).read())
    command=open('/proc/%s/cmdline'%candidate,'rb').read().split(b'\0')
    if b'/opt/device_guard/launcher.py' in command or command[0]==b'/opt/device_guard/device_guard_launcher':pid=candidate
except (OSError,ValueError):pass
if args.action=='stop' and pid is not None:
    os.kill(pid,signal.SIGTERM)
    for unused in range(80):
        if not os.path.exists(path):break
        time.sleep(.1)
    else:raise RuntimeError('Launcher did not stop; inspect runtime logs')
    pid=None
result={'running':pid is not None,'launcher_pid':pid}
if pid is not None:
    try:
        state=json.loads(urlopen('http://127.0.0.1:18765/api/state',timeout=4).read().decode('utf8'))
        result.update({k:state[k] for k in ('state','source','sensor_ok','calibrated','event_count','sample_count','error_count','config','time_text')})
    except OSError as exc:result['error']=str(exc)
print(json.dumps(result,ensure_ascii=True))
