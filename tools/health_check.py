import fcntl
import json
import os
import struct
import time
from urllib.request import urlopen

def state():
    return json.loads(urlopen('http://127.0.0.1:18765/api/state',timeout=4).read().decode('utf8'))

samples = []
for unused in range(30):
    s=state()
    samples.append(dict(mono=time.monotonic(),**{k:s[k] for k in ('state','sample_count','error_count','angle','motion','gyro','event_count','sensor_ok','storage_error')}))
    time.sleep(0.5)
first,last=samples[0],samples[-1]
data={'snapshots':samples,'rate_hz':(last['sample_count']-first['sample_count'])/(last['mono']-first['mono']), 'errors_added':last['error_count']-first['error_count']}
fd=os.open('/dev/input/event1',os.O_RDONLY|os.O_NONBLOCK)
data['touch_axes']={}
for code in (0,1,47,53,54,57):
    try:
        buffer=bytearray(24)
        fcntl.ioctl(fd,0x80184540+code,buffer,True)
        data['touch_axes'][str(code)]=list(struct.unpack('6i',buffer))
    except OSError as exc:
        data['touch_axes'][str(code)]=str(exc)
os.close(fd)
data['events']=json.loads(urlopen('http://127.0.0.1:18765/api/events').read().decode('utf8'))
with open('/opt/device_guard/evidence/health_check.json','w',encoding='utf8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in data.items() if k!='snapshots'},ensure_ascii=True))
