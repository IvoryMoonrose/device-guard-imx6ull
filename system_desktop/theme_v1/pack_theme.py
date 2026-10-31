from pathlib import Path
import json,shutil,tarfile
base=Path(__file__).resolve().parent
payload=base/'payload'
guard=payload/'guard';guard.mkdir(exist_ok=True)
shutil.copy2(base.parents[1]/'src/device_guard_launcher',payload/'bin/device_guard_launcher')
shutil.copy2(payload/'bin/device_guard_view',base.parents[1]/'src/device_guard_view')
shutil.copy2(base/'original_guard/Main.qml',guard/'OriginalMain.qml')
shutil.copy2(base.parents[1]/'src/fast_launcher.c',payload/'fast_launcher.c')
content=(base/'original_guard/Main.qml').read_text(encoding='utf8')
content=content.replace('property int page: 0','property int page: 0\n    property bool foreground: true')
content=content.replace('Timer{interval:250;repeat:true;running:true;','Timer{interval:250;repeat:true;running:root.foreground;')
content=content.replace('function shutdown(){call("/api/shutdown",{},function(){Qt.quit();});}','signal closeRequested()\n    function shutdown(){closeRequested();}')
(guard/'GuardContent.qml').write_text(content,encoding='utf8')
nav=(base/'runtime_src/qml/Nav.qml').read_text(encoding='utf8').replace('"Api.js"','"NavApi.js"')
(guard/'SystemNav.qml').write_text(nav,encoding='utf8')
shutil.copy2(base/'runtime_src/qml/Api.js',guard/'NavApi.js')
for name in ['install_theme.py','restore_theme.py','benchmark_desktop.py','upgrade_v2.py','restore_v2.py','verify_v2.py']:
    source=base/name
    if source.exists():shutil.copy2(source,payload/name)
with tarfile.open(base/'theme.tar.gz','w:gz') as archive:
    for path in sorted(payload.rglob('*')):
        if not path.is_file():continue
        name=path.relative_to(payload).as_posix()
        info=archive.gettarinfo(str(path),arcname=name)
        info.mode=0o755 if name.startswith(('bin/','apps/')) else 0o644
        with path.open('rb') as stream:archive.addfile(info,stream)
print(base/'theme.tar.gz')
