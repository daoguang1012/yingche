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
SERVICE = ['YingcheService.exe', 'app/YingcheBridge.exe']
# The service-only package omits the player and its video/beauty runtimes.
PLAYER_ONLY_DLLS = ('libmpv', 'mpv', 'gpupixel')

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

def prepare(stage, runtime, service_only=False):
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
        if service_only and source.name.lower().startswith(PLAYER_ONLY_DLLS):
            continue
        shutil.copy2(source, stage / 'app' / source.name)
    executables = SERVICE + ([] if service_only else ['Yingche.exe', 'app/BeautyPlayerV060.exe'])
    for name in executables:
        shutil.copy2(runtime / name, stage / name)
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.onnx', '*.task', '*.tflite', '.git')
    folders = ['platforms', 'styles', 'face_engine_v041'] if service_only else ['generic', 'gpupixel', 'imageformats', 'networkinformation', 'platforms', 'styles', 'tls', 'face_engine_v041', 'face_engine_v060']
    for name in folders:
        shutil.copytree(runtime / 'app' / name, stage / 'app' / name, ignore=ignore)
    (stage / 'models').mkdir()
    (stage / 'models/README.txt').write_text('Native face models are installed explicitly using DownloadModels.cmd. See MODELS.md.\n', encoding='utf-8')
    assert not (stage / 'data').exists()
    assert not any((stage / 'app').rglob('*.onnx'))
    engines = ['app/face_engine_v041/FaceEngine.exe'] + ([] if service_only else ['app/face_engine_v060/FaceEngine.exe'])
    for name in executables + engines:
        assert digest(stage / name) == digest(runtime / name), name
    if service_only:
        assert not (stage / 'app/BeautyPlayerV060.exe').exists() and not (stage / 'app/face_engine_v060').exists()
    manifest(stage)
    print('STAGED', stage, flush=True)

def summarize(assets, created):
    result = {}
    for path in created:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
        result[path.name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    # Checksums cover every archive in the folder, so separate runs do not drop each other's entries.
    (assets / 'SHA256SUMS.txt').write_text(''.join(digest(p) + '  ' + p.name + '\n' for p in sorted(assets.glob('*.zip'))), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)

def archive_service(stage, assets):
    assets.mkdir(parents=True, exist_ok=True)
    files = manifest(stage)
    target = assets / f'Yingche-Service-v{VERSION}-windows-x64.zip'
    if target.exists():
        raise RuntimeError('Archive already exists: ' + str(target))
    assert (stage / 'app/YingcheBridge.exe').exists() and not (stage / 'app/BeautyPlayerV060.exe').exists(), 'Not a service-only stage'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for file in files:
            z.write(file, Path(stage.name) / file.relative_to(stage))
    summarize(assets, [target])

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
    summarize(assets, [native, extension])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['stage', 'archive', 'stage-service', 'archive-service'])
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    if args.action in ('stage', 'stage-service'):
        if not args.runtime_root:
            parser.error('--runtime-root is required for ' + args.action)
        prepare(args.stage.resolve(), args.runtime_root.resolve(), service_only=args.action == 'stage-service')
    else:
        if not args.assets:
            parser.error('--assets is required for ' + args.action)
        (archive_service if args.action == 'archive-service' else archive)(args.stage.resolve(), args.assets.resolve())
