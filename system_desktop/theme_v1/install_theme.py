"""Transactional install of the desktop theme and shared application navigation."""
import hashlib,json,os,shutil,stat,subprocess,time

ROOT='/opt/device_guard/system_theme'
BACKUP=ROOT+'/backup_install_20261021'
attempt=1
while os.path.exists(BACKUP):
    attempt+=1;BACKUP=ROOT+'/backup_install_20261021_%02d'%attempt
plan=json.load(open(ROOT+'/resource_plan.json'))

def digest(path):
    with open(path,'rb') as stream:return hashlib.sha256(stream.read()).hexdigest()
def write(path,data,mode):
    temporary=path+'.theme-new'
    with open(temporary,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.chmod(temporary,mode);os.replace(temporary,path)
def add_file(changes,target,source,mode=None):
    existed=os.path.isfile(target)
    relative=target.lstrip('/').replace('/','__')
    entry={'target':target,'source':source,'existed':existed,'backup':BACKUP+'/files/'+relative,
           'mode':stat.S_IMODE(os.stat(target).st_mode) if existed else (mode or 0o644),
           'before':digest(target) if existed else None,'after':digest(source)}
    if mode is not None:entry['mode']=mode
    changes.append(entry)

assert not os.path.isfile('/opt/device_guard/runtime/launcher.pid'),'Exit Device Guard before installation'
assert digest('/opt/device_guard/ui/Main.qml') in [digest(ROOT+'/guard/OriginalMain.qml'),digest(ROOT+'/guard/Main.qml')],'Device Guard UI has later edits'
assert digest('/opt/ui/systemui')==plan['desktop']['before'],'Factory desktop has other edits'
assert not os.path.exists('/opt/ui/systemui.core'),'Unexpected pre-existing desktop core'
for name,item in plan['apps'].items():
    assert digest('/opt/ui/src/apps/'+name)==item['before'],'Application changed: '+name
    assert digest(ROOT+'/apps/'+name)==item['after']

changes=[]
add_file(changes,'/opt/ui/systemui.core',ROOT+'/bin/systemui.core',0o755)
add_file(changes,'/opt/ui/systemui',ROOT+'/bin/desktop_entry',0o755)
for name in plan['apps']:add_file(changes,'/opt/ui/src/apps/'+name,ROOT+'/apps/'+name,0o755)
for name in list(plan['apps'])+['device_guard']:
    add_file(changes,'/opt/ui/src/appicons/'+name+'.png',ROOT+'/assets/'+name+'.png',0o644)
add_file(changes,'/opt/ui/src/ipad/ipad/ipad.jpg',ROOT+'/assets/wallpaper.jpg',0o644)
for name in ['Main.qml','GuardContent.qml','SystemNav.qml','NavApi.js']:
    add_file(changes,'/opt/device_guard/ui/'+name,ROOT+'/guard/'+name,0o644)
for name in ['nav-back.png','nav-home.png','nav-tasks.png','crest.png']:
    add_file(changes,'/opt/device_guard/assets/hud/'+name,ROOT+'/assets/'+name,0o644)
for name in ['device_guard_launcher','device_guard_view']:
    add_file(changes,'/opt/device_guard/'+name,ROOT+'/bin/'+name,0o755)
add_file(changes,'/opt/device_guard/fast_launcher.c',ROOT+'/fast_launcher.c',0o644)
os.makedirs(ROOT+'/generated',exist_ok=True)
cfg='/opt/ui/src/ATK-IMX6U/'
app_lines=[]
for name in ['apk1.cfg','apk2.cfg','apk3.cfg']:
    for line in open(cfg+name,encoding='utf8'):
        if line.strip() and line.strip() not in app_lines:app_lines.append(line.strip())
assert len(app_lines)==16
for name,data in [('apk1.cfg','\n'.join(app_lines)+'\n'),('apk2.cfg',''),('apk3.cfg','')]:
    with open(ROOT+'/generated/'+name,'w',encoding='utf8') as stream:stream.write(data)
    add_file(changes,cfg+name,ROOT+'/generated/'+name)
conf='/opt/ui/src/apps/resource/systemui.conf'
lines=[line for line in open(conf,encoding='utf8').read().splitlines() if not line.startswith('background-task=')]
lines.append('background-task='+','.join(line.split()[-1] for line in app_lines))
with open(ROOT+'/generated/systemui.conf','w',encoding='utf8') as stream:stream.write('\n'.join(lines)+'\n')
add_file(changes,conf,ROOT+'/generated/systemui.conf')

# Refuse to replace an application while it is being used.
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    try:argv=open('/proc/'+pid+'/cmdline','rb').read().split(b'\0')
    except OSError:continue
    if argv and argv[0].startswith(b'/opt/ui/src/apps/'):
        raise RuntimeError('Close factory applications before installing: '+argv[0].decode('utf8'))
os.makedirs(BACKUP+'/files')
for entry in changes:
    if entry['existed']:shutil.copy2(entry['target'],entry['backup'])

cache_entries=[]
for app,urls in plan['qrc_urls'].items():
    directory='/home/root/.cache/'+app+'/qmlcache'
    if not os.path.isdir(directory):continue
    for name in os.listdir(directory):
        if not name.endswith('.qmlc'):continue
        target=directory+'/'+name
        raw=open(target,'rb').read()
        if any(url.encode('utf8') in raw or url.encode('utf-16le') in raw for url in urls):
            backup=BACKUP+'/cache/'+app+'/'+name
            os.makedirs(os.path.dirname(backup),exist_ok=True);shutil.copy2(target,backup)
            cache_entries.append({'target':target,'backup':backup,'mode':stat.S_IMODE(os.stat(target).st_mode),'before':digest(target)})
manifest={'version':2,'changes':changes,'caches':cache_entries,'resource_plan':plan,'installed_at':time.time()}
with open(BACKUP+'/manifest.json','w') as stream:json.dump(manifest,stream,indent=2)
try:
    for entry in changes:
        with open(entry['source'],'rb') as stream:write(entry['target'],stream.read(),entry['mode'])
    for entry in cache_entries:os.replace(entry['target'],entry['target']+'.before-guard-theme-'+str(attempt))
    for entry in changes:assert digest(entry['target'])==entry['after']
    subprocess.check_call(['/usr/bin/python3','/opt/device_guard/tools/reload_factory_desktop.py'])
except Exception:
    for entry in reversed(changes):
        if entry['existed']:
            with open(entry['backup'],'rb') as stream:write(entry['target'],stream.read(),entry['mode'])
        elif os.path.isfile(entry['target']):os.unlink(entry['target'])
    for entry in cache_entries:
        with open(entry['backup'],'rb') as stream:write(entry['target'],stream.read(),entry['mode'])
    # If the replacement exited during load, bring the previous desktop back.
    existing=[]
    for name in os.listdir('/proc'):
        if not name.isdigit():continue
        try:argv=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')
        except OSError:continue
        if argv[0]==b'/opt/ui/systemui':existing.append(name)
    if not existing:
        env=os.environ.copy();env.update(QT_QUICK_BACKEND='software',QT_QPA_FONTDIR='/usr/share/fonts/ttf',QT_QPA_PLATFORM='linuxfb:tty=/dev/fb0',QT_QPA_FB_TSLIB='1')
        log=open(ROOT+'/runtime/recovery.log','a')
        subprocess.Popen(['/opt/ui/systemui'],cwd='/opt/ui',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    raise
with open(ROOT+'/installed.json','w') as stream:json.dump({'version':2,'backup':BACKUP,'files':len(changes)},stream)
print(json.dumps({'installed':True,'applications':len(plan['apps']),'files':len(changes),'backup':BACKUP}))
