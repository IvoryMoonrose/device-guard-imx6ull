"""Upgrade this verified v1 installation; preserve a complete rollback snapshot."""
import hashlib,json,os,shutil,signal,stat,subprocess,time
ROOT='/opt/device_guard/system_theme'
BACKUP=ROOT+'/backup_v2_20261021'
attempt=1
while os.path.exists(BACKUP):
    attempt+=1;BACKUP=ROOT+'/backup_v2_20261021_%02d'%attempt
assert not os.path.isfile(ROOT+'/upgrade_v2_installed.json'),'Version 2 is already installed'
def digest(path):
    with open(path,'rb') as stream:return hashlib.sha256(stream.read()).hexdigest()
def atomic(path,data,mode):
    temporary=path+'.theme-v2'
    with open(temporary,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.chmod(temporary,mode);os.replace(temporary,path)
def broker_stop():
    try:
        pid=int(open(ROOT+'/runtime/nav.pid').read())
        if open('/proc/%d/cmdline'%pid,'rb').read().split(b'\0')[0]==(ROOT+'/bin/navd').encode('utf8'):os.kill(pid,signal.SIGTERM);time.sleep(.3)
    except (OSError,ValueError):pass
assert not os.path.isfile('/opt/device_guard/runtime/launcher.pid'),'Exit Device Guard first'
for name in os.listdir('/proc'):
    if not name.isdigit():continue
    try:argv=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')
    except OSError:continue
    if argv and argv[0].startswith(b'/opt/ui/src/apps/'):raise RuntimeError('Close factory apps before upgrade')
v1=json.load(open(ROOT+'/installed.json'))
assert v1['version']==1,'Upgrade requires the original v1 installation'
for entry in json.load(open(v1['backup']+'/manifest.json'))['changes']:
    assert digest(entry['target'])==entry['after'],'Later edits: '+entry['target']
sources={
 '/opt/ui/systemui':ROOT+'/bin/desktop_entry',
 '/opt/device_guard/device_guard_launcher':ROOT+'/bin/device_guard_launcher',
 '/opt/device_guard/device_guard_view':ROOT+'/bin/device_guard_view',
 '/opt/device_guard/fast_launcher.c':ROOT+'/upgrade/fast_launcher.c',
 ROOT+'/bin/navd':ROOT+'/upgrade/navd',
}
for name in os.listdir(ROOT+'/upgrade/qml'):sources[ROOT+'/qml/'+name]=ROOT+'/upgrade/qml/'+name
for name in ['Main.qml','GuardContent.qml','SystemNav.qml','NavApi.js']:sources['/opt/device_guard/ui/'+name]=ROOT+'/upgrade/guard/'+name
os.makedirs(BACKUP+'/files')
changes=[]
def stage(target,data,mode=None):
    existed=os.path.isfile(target);oldmode=stat.S_IMODE(os.stat(target).st_mode) if existed else 0o644
    backup=BACKUP+'/files/'+target.lstrip('/').replace('/','__')
    if existed:shutil.copy2(target,backup)
    changes.append({'target':target,'backup':backup,'before':digest(target) if existed else None,'after':hashlib.sha256(data).hexdigest(),'mode':oldmode,'new_mode':mode or oldmode,'existed':existed,'data':data})
for target,source in sources.items():
    with open(source,'rb') as stream:stage(target,stream.read(),0o755 if target.endswith(('/systemui','/navd','/device_guard_launcher','/device_guard_view')) else None)
cfg='/opt/ui/src/ATK-IMX6U/'
apps=[]
for filename in ['apk1.cfg','apk2.cfg','apk3.cfg']:
    for line in open(cfg+filename,encoding='utf8'):
        if line.strip() and line.strip() not in apps:apps.append(line.strip())
assert len(apps)==16
stage(cfg+'apk1.cfg',('\n'.join(apps)+'\n').encode('utf8'))
stage(cfg+'apk2.cfg',b'');stage(cfg+'apk3.cfg',b'')
conf='/opt/ui/src/apps/resource/systemui.conf'
lines=open(conf,encoding='utf8').read().splitlines()
lines=[line for line in lines if not line.startswith('background-task=')]
lines.append('background-task='+','.join(line.split()[-1] for line in apps))
stage(conf,('\n'.join(lines)+'\n').encode('utf8'))
manifest={'version':2,'changes':[{key:value for key,value in entry.items() if key!='data'} for entry in changes]}
with open(BACKUP+'/manifest.json','w') as stream:json.dump(manifest,stream,indent=2)
broker_stop()
try:
    for entry in changes:atomic(entry['target'],entry['data'],entry['new_mode'])
    for entry in changes:assert digest(entry['target'])==entry['after']
    subprocess.check_call(['/usr/bin/python3','/opt/device_guard/tools/reload_factory_desktop.py'])
except Exception:
    broker_stop()
    for entry in reversed(changes):
        if entry['existed']:
            with open(entry['backup'],'rb') as stream:atomic(entry['target'],stream.read(),entry['mode'])
        elif os.path.isfile(entry['target']):os.unlink(entry['target'])
    env=os.environ.copy();env.update(QT_QUICK_BACKEND='software',QT_QPA_FONTDIR='/usr/share/fonts/ttf',QT_QPA_PLATFORM='linuxfb:tty=/dev/fb0',QT_QPA_FB_TSLIB='1')
    # The reload helper has already terminated the previous shell if load failed.
    found=False
    for name in os.listdir('/proc'):
        if not name.isdigit():continue
        try:found=found or open('/proc/'+name+'/cmdline','rb').read().split(b'\0')[0]==b'/opt/ui/systemui'
        except OSError:pass
    if not found:
        log=open(ROOT+'/runtime/recovery-v2.log','a')
        subprocess.Popen(['/opt/ui/systemui'],cwd='/',env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    raise
with open(ROOT+'/upgrade_v2_installed.json','w') as stream:json.dump({'version':2,'backup':BACKUP,'files':len(changes)},stream,indent=2)
print(json.dumps({'installed':True,'version':2,'files':len(changes),'backup':BACKUP}))
