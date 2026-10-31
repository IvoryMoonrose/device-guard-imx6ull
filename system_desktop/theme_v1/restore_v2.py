"""Rollback the background/boot/layout fix only; --check verifies without writing."""
import hashlib,json,os,signal,subprocess,sys,time
ROOT='/opt/device_guard/system_theme'
installed=json.load(open(ROOT+'/upgrade_v2_installed.json'))
manifest=json.load(open(installed['backup']+'/manifest.json'))
def digest(path):return hashlib.sha256(open(path,'rb').read()).hexdigest()
for entry in manifest['changes']:
    assert digest(entry['target'])==entry['after'],'Later edits: '+entry['target']
    if entry['existed']:assert digest(entry['backup'])==entry['before'],'Backup mismatch: '+entry['target']
if '--check' in sys.argv:
    print(json.dumps({'rollback_verified':len(manifest['changes']),'backup':installed['backup'],'read_only':True}));sys.exit(0)
assert not os.path.isfile('/opt/device_guard/runtime/launcher.pid'),'End Device Guard in Tasks first'
for name in os.listdir('/proc'):
    if not name.isdigit():continue
    try:argv=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')
    except OSError:continue
    if argv[0].startswith(b'/opt/ui/src/apps/'):raise RuntimeError('End background applications in Tasks first')
pid=int(open(ROOT+'/runtime/nav.pid').read())
if open('/proc/%d/cmdline'%pid,'rb').read().split(b'\0')[0]==(ROOT+'/bin/navd').encode('utf8'):os.kill(pid,signal.SIGTERM);time.sleep(.3)
for entry in reversed(manifest['changes']):
    if entry['existed']:
        data=open(entry['backup'],'rb').read();temporary=entry['target']+'.restore-v2'
        with open(temporary,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(temporary,entry['mode']);os.replace(temporary,entry['target'])
    else:os.unlink(entry['target'])
os.replace(ROOT+'/upgrade_v2_installed.json',ROOT+'/upgrade_v2_restored.json')
subprocess.check_call(['/usr/bin/python3','/opt/device_guard/tools/reload_factory_desktop.py'])
print('Restored the previous theme version and original background policy')
