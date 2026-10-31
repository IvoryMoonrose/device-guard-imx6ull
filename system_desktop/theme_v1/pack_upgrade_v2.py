from pathlib import Path
import tarfile
base=Path(__file__).resolve().parent
files=[]
for directory in ['qml','guard']:
    files.extend((path,'upgrade/'+directory+'/'+path.name) for path in (base/'payload'/directory).glob('*') if path.is_file())
for source,name in [('payload/bin/navd','upgrade/navd'),('payload/bin/desktop_entry','bin/desktop_entry'),('payload/bin/device_guard_launcher','bin/device_guard_launcher'),('payload/bin/device_guard_view','bin/device_guard_view'),('../../src/fast_launcher.c','upgrade/fast_launcher.c'),('upgrade_v2.py','upgrade_v2.py'),('restore_v2.py','restore_v2.py'),('verify_v2.py','verify_v2.py')]:files.append((base/source,name))
with tarfile.open(base/'upgrade_v2.tar.gz','w:gz') as archive:
    for path,name in files:
        info=archive.gettarinfo(str(path),arcname=name);info.mtime=0
        info.mode=0o755 if name.startswith('bin/') else 0o644
        with path.open('rb') as stream:archive.addfile(info,stream)
print(base/'upgrade_v2.tar.gz')
