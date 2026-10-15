"""Stage or archive a clean portable release; never publishes to GitHub."""
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.6.0'

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()

def manifest(stage):
    files = sorted(p for p in stage.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    (stage / 'SHA256SUMS.txt').write_text(''.join(digest(p) + '  ' + p.relative_to(stage).as_posix() + '\n' for p in files), encoding='utf-8')
    return files + [stage / 'SHA256SUMS.txt']

def prepare(stage, runtime):
    if stage.exists():
        raise RuntimeError('Use a new empty stage path; existing files are preserved')
    stage.mkdir(parents=True)
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode('utf-8').split('\0')
    for name in sorted(set(filter(None, names))):
        source = ROOT / name
        if not source.is_file():
            raise RuntimeError('Source snapshot contains a missing path: ' + name)
        if source.is_symlink():
            raise RuntimeError('Source symlink must be reviewed: ' + name)
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (stage / 'app').mkdir()
    for source in (runtime / 'app').glob('*.dll'):
        shutil.copy2(source, stage / 'app' / source.name)
    shutil.copy2(runtime / 'app/BeautyPlayerV060.exe', stage / 'app/BeautyPlayerV060.exe')
    shutil.copy2(runtime / 'Yingche.exe', stage / 'Yingche.exe')
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.onnx', '*.task', '*.tflite', '.git')
    for name in ['generic', 'gpupixel', 'imageformats', 'networkinformation', 'platforms', 'styles', 'tls', 'face_engine_v041', 'face_engine_v060']:
        shutil.copytree(runtime / 'app' / name, stage / 'app' / name, ignore=ignore)
    (stage / 'models').mkdir()
    (stage / 'models/README.txt').write_text('Native face models are installed explicitly using DownloadModels.cmd. See MODELS.md.\n', encoding='utf-8')
    assert not (stage / 'data').exists()
    assert not any((stage / 'app').rglob('*.onnx'))
    for name in ['Yingche.exe', 'app/BeautyPlayerV060.exe', 'app/face_engine_v060/FaceEngine.exe', 'app/face_engine_v041/FaceEngine.exe']:
        assert digest(stage / name) == digest(runtime / name), name
    manifest(stage)
    print('STAGED', stage, flush=True)

def archive(stage, assets):
    assets.mkdir(parents=True, exist_ok=True)
    files = manifest(stage)
    native = assets / f'Yingche-v{VERSION}-windows-x64.zip'
    extension = assets / f'Yingche-Edge-v{VERSION}.zip'
    for target in [native, extension]:
        if target.exists():
            raise RuntimeError('Archive already exists: ' + str(target))
    with zipfile.ZipFile(native, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for file in files:
            z.write(file, Path(stage.name) / file.relative_to(stage))
    with zipfile.ZipFile(extension, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for file in sorted((stage / 'edge-extension').rglob('*')):
            if file.is_file():
                z.write(file, file.relative_to(stage))
        for name in ['EDGE使用说明.md', 'THIRD_PARTY.md', 'LICENSE', 'NOTICE']:
            z.write(stage / name, name)
        for name in ['GPUPixel-Apache-2.0.txt', 'Emscripten-LICENSE.txt', 'GPUPixel-header-notices.txt']:
            z.write(stage / 'licenses' / name, 'licenses/' + name)
    result = {}
    for path in [native, extension]:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
        result[path.name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    (assets / 'SHA256SUMS.txt').write_text(''.join(v['sha256'] + '  ' + k + '\n' for k, v in result.items()), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['stage', 'archive'])
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    if args.action == 'stage':
        if not args.runtime_root:
            parser.error('--runtime-root is required for stage')
        prepare(args.stage.resolve(), args.runtime_root.resolve())
    else:
        if not args.assets:
            parser.error('--assets is required for archive')
        archive(args.stage.resolve(), args.assets.resolve())
