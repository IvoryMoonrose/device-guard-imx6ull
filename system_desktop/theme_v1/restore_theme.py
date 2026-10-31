"""Hash-guarded rollback to the desktop/app versions from before this theme."""
import hashlib,json,os,signal,subprocess
ROOT='/opt/device_guard/system_theme'
installed=json.load(open(ROOT+'/installed.json'))
manifest=json.load(open(installed['backup']+'/manifest.json'))
def digest(path):
    with open(path,'rb') as stream:return hashlib.sha256(stream.read()).hexdigest()
def atomic(path,data,mode):
    temporary=path+'.theme-restore'
    with open(temporary,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.chmod(temporary,mode);os.replace(temporary,path)
assert not os.path.isfile('/opt/device_guard/runtime/launcher.pid'),'Exit Device Guard first'
for name in os.listdir('/proc'):
    if not name.isdigit():continue
    try:argv=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')
    except OSError:continue
    if argv and argv[0].startswith(b'/opt/ui/src/apps/'):raise RuntimeError('Close factory applications before restoring')
for entry in manifest['changes']:
    assert digest(entry['target'])==entry['after'],'Later edits found: '+entry['target']
    if entry['existed']:assert digest(entry['backup'])==entry['before']
for entry in reversed(manifest['changes']):
    if entry['existed']:
        with open(entry['backup'],'rb') as stream:atomic(entry['target'],stream.read(),entry['mode'])
    else:os.unlink(entry['target'])
for entry in manifest['caches']:
    assert digest(entry['backup'])==entry['before']
    with open(entry['backup'],'rb') as stream:atomic(entry['target'],stream.read(),entry['mode'])
try:
    pid=int(open(ROOT+'/runtime/nav.pid').read())
    argv=open('/proc/%d/cmdline'%pid,'rb').read().split(b'\0')
    if argv[0]==(ROOT+'/bin/navd').encode('utf8'):os.kill(pid,signal.SIGTERM)
except (OSError,ValueError):pass
subprocess.check_call(['/usr/bin/python3','/opt/device_guard/tools/reload_factory_desktop.py'])
print('Restored the previous single-page desktop, icons, wallpaper and application navigation')
