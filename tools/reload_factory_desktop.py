"""Reload only the verified factory shell so it rereads the app list."""
import json
import os
import signal
import subprocess
import time

BASE='/opt/device_guard'
if os.path.isfile(BASE+'/runtime/launcher.pid'):
    raise RuntimeError('Exit Device Guard before reloading the factory desktop')
matches=[]
for name in os.listdir('/proc'):
    if name.isdigit():
        try:
            args=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')
            if args[0]==b'/opt/ui/systemui':matches.append(int(name))
        except OSError:pass
if len(matches)!=1:raise RuntimeError('Expected exactly one factory shell; leaving all processes unchanged')
pid=matches[0]
raw=open('/proc/%s/environ'%pid,'rb').read()
env=os.environ.copy()
for item in raw.split(b'\0'):
    if b'=' not in item:continue
    key,value=item.split(b'=',1)
    key=key.decode('utf8','replace')
    if key.startswith(('QT_','TSLIB_','QML')) or key in ('DISPLAY','LD_LIBRARY_PATH','XDG_RUNTIME_DIR'):
        env[key]=value.decode('utf8','replace')
os.kill(pid,signal.SIGTERM)
for unused in range(60):
    try:
        state=open('/proc/%s/status'%pid).read()
        if '\nState:\tZ' in '\n'+state:break
    except OSError:break
    time.sleep(.1)
else:raise RuntimeError('Factory shell did not exit; no replacement was started')
log=open(BASE+'/runtime/factory-desktop.log','a')
process=subprocess.Popen(['/opt/ui/systemui'],cwd='/',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
time.sleep(4)
if process.poll() is not None:raise RuntimeError('Factory shell did not remain running; inspect runtime/factory-desktop.log')
result={'previous_pid':pid,'new_pid':process.pid,'reloaded':True}
with open(BASE+'/desktop_entry/reload.json','w') as stream:json.dump(result,stream,indent=2)
print(json.dumps(result))
