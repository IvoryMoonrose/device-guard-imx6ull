"""Use tiny QRC bridges; keep vendor native code, resource tables and sizes intact."""
from pathlib import Path
import hashlib,json,re,shutil,struct,zlib

BASE=Path(__file__).resolve().parent
PAYLOAD=BASE/'payload'
(PAYLOAD/'apps').mkdir(parents=True,exist_ok=True)
shutil.copytree(BASE/'runtime_src/qml',PAYLOAD/'qml',dirs_exist_ok=True)

def resources(raw):
    found=[]
    for match in re.finditer(b'\x78[\x01\x9c\xda]',raw):
        obj=zlib.decompressobj()
        try:source=obj.decompress(raw[match.start():])
        except zlib.error:continue
        if b'import QtQuick' not in source:continue
        size=len(raw[match.start():])-len(obj.unused_data)
        if match.start()<8:continue
        prefix=struct.unpack('>II',raw[match.start()-8:match.start()])
        if prefix!=(size+4,len(source)):continue
        found.append({'source':source,'offset':match.start(),'length':size,'compressed':True})
    for match in re.finditer(rb'/\*\*\*',raw):
        if match.start()<4:continue
        size=struct.unpack('>I',raw[match.start()-4:match.start()])[0]
        if not 50<size<100000:continue
        source=raw[match.start():match.start()+size]
        if b'import QtQuick' in source:found.append({'source':source,'offset':match.start(),'length':size,'compressed':False})
    return found

def replace_resource(raw,item,source):
    offset=item['offset'];length=item['length'];source=source.encode('utf8') if isinstance(source,str) else source
    if item['compressed']:
        packed=zlib.compress(source,9)
        assert len(packed)<=length
        encoded=packed+b'\0'*(length-len(packed))
        assert zlib.decompress(encoded)==source
        result=raw[:offset-4]+struct.pack('>I',len(source))+encoded+raw[offset+length:]
    else:
        assert len(source)<=length
        result=raw[:offset]+source+b' '*(length-len(source))+raw[offset+length:]
    assert len(result)==len(raw)
    return result

def bridge(component):
    return 'import QtQuick 2.12\nimport "file:///opt/device_guard/system_theme/qml" as T\nT.'+component+'{}\n'

HOOKS={
 'FileViewLayout.qml':('FileLayout', '''function themeBack(){
 if(warningDialog.opened){warningDialog.close();return true;}
 if(folderNavigation.count>1){var item=folderNavigation.model.get(folderNavigation.count-2);fileView.folderPathName=item.folderPathName;fileView.currtentPathName=item.currtentPathName;folderNavigation.model.remove(folderNavigation.count-1);folderNavigation.currentIndex=folderNavigation.count-1;fileView.folderNavigationItemCount=folderNavigation.count;return true;}return false;}
 '''),
 'PhotoViewLayout.qml':('PhotoLayout', 'function themeBack(){if(swipeView.currentIndex>0){swipeView.currentIndex=0;return true;}return false;}\n'),
 'SettingsLayout.qml':('SettingsLayout', 'function themeBack(){if(actionSheet.opened){actionSheet.close();return true;}if(customDialog.opened){customDialog.close();return true;}if(wifiPageSwipeView.currentIndex>0){wifiPageSwipeView.currentIndex=0;return true;}return false;}\n'),
 'NotepadLayout.qml':('NotepadLayout', 'function themeBeforeHome(){if(notepad_swipeView.currentIndex===1)notepad_swipeView.itemAt(1).clickedFunc();}\nfunction themeBack(){if(removeFile_drawer_bottom.visible&&removeFile_drawer_bottom.y<height){removeFile_drawer_bottom.close();return true;}if(notepad_swipeView.currentIndex===1){notepad_swipeView.itemAt(1).clickedFunc();return true;}return false;}\n'),
}

plan={'apps':{},'qrc_urls':{},'version':1}
for binary in sorted((BASE/'original_apps').iterdir()):
    original=binary.read_bytes();raw=original;entries=resources(raw)
    original_out=BASE/'qml_original'/binary.name;original_out.mkdir(parents=True,exist_ok=True)
    clients=[entry for entry in entries if re.search(rb'@brief\s+Client\.qml',entry['source'])]
    assert len(clients)==1,(binary.name,len(clients))
    raw=replace_resource(raw,clients[0],bridge('Client'))
    urls=['qrc:/Client.qml']
    for entry in entries:
        brief=re.search(rb'@brief\s+(\S+\.qml)',entry['source'])
        if not brief:continue
        name=brief.group(1).decode('ascii');(original_out/name).write_bytes(entry['source'])
        if name in HOOKS:
            component,hook=HOOKS[name]
            source=entry['source'].decode('utf8')
            # Other components and static resources remain in their vendor QRC.
            lines=source.splitlines();first=next(i for i,line in enumerate(lines) if line.startswith('import '));lines.insert(first,'import "qrc:/"')
            source='\n'.join(lines)
            root_match=re.search(r'\n(?:Item|Rectangle)\s*\{',source)
            assert root_match,name
            source=source[:root_match.end()]+ '\n'+hook+source[root_match.end():]
            source=re.sub(r'(source:\s*")([A-Za-z][^":]*\.qml)(")',r'\1qrc:/\2\3',source)
            (PAYLOAD/'qml'/(component+'.qml')).write_text(source,encoding='utf8')
            raw=replace_resource(raw,entry,bridge(component));urls.append('qrc:/'+name)
    target=PAYLOAD/'apps'/binary.name;target.write_bytes(raw)
    plan['apps'][binary.name]={'before':hashlib.sha256(original).hexdigest(),'after':hashlib.sha256(raw).hexdigest()}
    plan['qrc_urls'][binary.name]=urls

raw=(BASE/'original_systemui').read_bytes()
entries=[entry for entry in resources(raw) if b'id: main_swipeView' in entry['source']]
assert len(entries)==1
result=replace_resource(raw,entries[0],bridge('Desktop'))
(PAYLOAD/'bin/systemui.core').write_bytes(result)
# The native vendor types are registered inside each application executable,
# rather than installed as a qmlscene plugin. Reuse an untouched minimal vendor
# host and replace only its main QML; no LED component is instantiated here.
host=(BASE/'original_apps/led').read_bytes()
entries=[entry for entry in resources(host) if re.search(rb'@brief\s+main\.qml',entry['source'])]
assert len(entries)==1
host_qml='''import QtQuick 2.12
import QtQuick.Window 2.12
import "file:///opt/device_guard/ui" as G
Window{id:window;visible:true;width:1024;height:600;x:0;y:0;flags:Qt.FramelessWindowHint;G.Main{anchors.fill:parent}}
'''
(PAYLOAD/'bin/device_guard_view').write_bytes(replace_resource(host,entries[0],host_qml))
(PAYLOAD/'guard_host.qml').write_text(host_qml,encoding='utf8')
plan['desktop']={'before':hashlib.sha256(raw).hexdigest(),'after':hashlib.sha256(result).hexdigest()}
plan['qrc_urls']['systemui']=['qrc:/main.qml']
(PAYLOAD/'resource_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
print(json.dumps({'apps':len(plan['apps']),'modified_qrc_urls':plan['qrc_urls']},indent=2))
