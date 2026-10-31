"""Install one reversible entry in the supplied ALPHA systemui launcher."""
import argparse
import hashlib
import json
import os
import shutil
import time

BASE='/opt/device_guard'
CFG='/opt/ui/src/ATK-IMX6U/apk1.cfg'
ICON='/opt/ui/src/appicons/device_guard.png'
APP='/opt/ui/src/apps/device_guard'
ENTRY='appicons/device_guard.png 设备守护 device_guard'
WRAPPER='#!/bin/sh\ncd /opt/device_guard || exit 1\nmkdir -p /opt/device_guard/runtime\nif test -x ./device_guard_launcher; then\n  exec /opt/device_guard/device_guard_launcher >>./runtime/desktop-entry.log 2>&1\nfi\nexec /usr/bin/python3 /opt/device_guard/launcher.py >>./runtime/desktop-entry.log 2>&1\n'
MANIFEST=BASE+'/desktop_entry/manifest.json'

def digest(path):
    with open(path,'rb') as stream:return hashlib.sha256(stream.read()).hexdigest()
def atomic(path,data,mode=None):
    with open(path+'.guard-new','wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    if mode is not None:os.chmod(path+'.guard-new',mode)
    os.replace(path+'.guard-new',path)

parser=argparse.ArgumentParser();parser.add_argument('--uninstall',action='store_true');args=parser.parse_args()
if args.uninstall:
    with open(MANIFEST,encoding='utf8') as stream:manifest=json.load(stream)
    with open(CFG,encoding='utf8') as stream:lines=stream.read().splitlines()
    changed=[line for line in lines if line.split()[-1:] == ['device_guard'] and line!=ENTRY]
    if changed:raise RuntimeError('This launcher entry has later edits; leaving it unchanged')
    atomic(CFG,('\n'.join(line for line in lines if line!=ENTRY)+'\n').encode('utf8'))
    for path,key in [(APP,'wrapper_sha256'),(ICON,'icon_sha256')]:
        if os.path.isfile(path) and digest(path)==manifest[key]:os.unlink(path)
    print('Removed only the Device Guard entry; reload the factory desktop to refresh icons')
else:
    if not os.path.isfile(CFG):raise RuntimeError('This image does not have the verified ALPHA launcher configuration')
    source=BASE+'/assets/guardian-anime-v1.png'
    if not os.path.isfile(source):raise RuntimeError('Project icon asset is missing')
    with open(CFG,'rb') as stream:before=stream.read()
    lines=before.decode('utf8').splitlines()
    related=[line for line in lines if line.split()[-1:]==['device_guard']]
    if related and related!=[ENTRY]:raise RuntimeError('Another Device Guard entry exists; leaving it unchanged')
    os.makedirs(BASE+'/desktop_entry',exist_ok=True)
    backup=BASE+'/desktop_entry/apk1.before_'+time.strftime('%Y%m%d_%H%M%S')+'.cfg'
    if not related:
        if os.path.exists(APP) or os.path.exists(ICON):raise RuntimeError('Target app/icon already exists without our entry')
        atomic(backup,before)
    else:
        with open(MANIFEST,encoding='utf8') as stream:old=json.load(stream)
        if digest(APP)!=old['wrapper_sha256'] or digest(ICON)!=old['icon_sha256']:
            raise RuntimeError('Installed files have later edits; leaving them unchanged')
        backup=old['backup']
    with open(source,'rb') as stream:atomic(ICON,stream.read(),0o644)
    atomic(APP,WRAPPER.encode('utf8'),0o755)
    if not related:atomic(CFG,(ENTRY+'\n').encode('utf8')+before)
    manifest={'config':CFG,'entry':ENTRY,'backup':backup,'wrapper':APP,'icon':ICON,
              'wrapper_sha256':digest(APP),'icon_sha256':digest(ICON),'installed_at':time.time()}
    atomic(MANIFEST,json.dumps(manifest,ensure_ascii=True,indent=2).encode('utf8'))
    print(json.dumps(manifest,ensure_ascii=True))
