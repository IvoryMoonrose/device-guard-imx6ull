from pathlib import Path
import tarfile

base=Path(__file__).resolve().parents[1]
target=base/'build/device_guard.tar.gz'
target.parent.mkdir(exist_ok=True)
with tarfile.open(target,'w:gz') as archive:
    for directory,prefix in [('src',''),('tests','tests'),('tools','tools')]:
        for path in sorted((base/directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo'):
                name=str(Path(prefix)/path.relative_to(base/directory)).replace('\\','/')
                info=archive.gettarinfo(str(path),arcname=name)
                info.mode=0o755 if name in ('device_guard_launcher','device_guard_view') or path.suffix=='.sh' else 0o644
                with path.open('rb') as stream:archive.addfile(info,stream)
print(target)
