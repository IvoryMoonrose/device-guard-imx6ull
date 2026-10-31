"""Create a consistent SQLite backup without copying a live WAL database."""
import json
import os
import subprocess
import time
from urllib.request import urlopen

base='/opt/device_guard'
target=base+'/backups/'+time.strftime('%Y%m%d_%H%M%S')
os.makedirs(target,exist_ok=True)
for name in ('data','replay_data'):
    database=base+'/'+name+'/events.sqlite3'
    if os.path.isfile(database):
        subprocess.check_call(['/usr/bin/sqlite3',database,".backup '"+target+'/'+name+".sqlite3'"])
        config=base+'/'+name+'/config.json'
        if os.path.isfile(config):
            with open(config,'rb') as src,open(target+'/'+name+'_config.json','wb') as dst:dst.write(src.read())
try:
    csv=urlopen('http://127.0.0.1:18765/api/export.csv',timeout=4).read()
    with open(target+'/events.csv','wb') as stream:stream.write(csv)
except OSError:
    pass
print(target)
