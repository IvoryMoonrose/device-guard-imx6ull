"""Emergency restore if the launcher was forcibly killed. No unrelated PIDs."""
import json
import os
import signal

base='/opt/device_guard/runtime'
try:
    entries=json.load(open(base+'/previous_gui.json'))
except (OSError,ValueError):
    entries=[]
for entry in entries:
    try:
        current=open('/proc/%s/cmdline'%entry['pid'],'rb').read().decode('utf8','replace')
        if current==entry['argv']:
            os.kill(entry['pid'],signal.SIGCONT)
            print('Resumed factory GUI',entry['pid'])
    except OSError:
        pass
try:
    with open('/sys/class/leds/beep/brightness','w') as stream:stream.write('0')
except OSError:
    pass
