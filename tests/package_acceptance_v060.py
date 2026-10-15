"""Run only against an isolated COPY of the public package, never an active install."""
import argparse
import base64
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
import cv2
import numpy as np
import psutil
import control

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--clip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--missing-models', action='store_true')
    parser.add_argument('--bridge-port', type=int, default=29966)
    args = parser.parse_args()
    package, output = args.package.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    control.qa = output / 'control'; control.qa.mkdir()
    env = dict(os.environ)
    for key in ['APPDATA', 'LOCALAPPDATA']:
        path = output / key.lower(); path.mkdir(); env[key] = str(path)
    native = None
    checks = []
    report = {'version': '0.6.0', 'missingModelsCase': args.missing_models, 'passed': False, 'checks': checks}
    log = (output / 'player.log').open('w', encoding='utf-8')
    config_path = package / 'edge-extension/bridge-config.json'
    config_before = config_path.read_bytes()
    try:
        if args.missing_models:
            assert not (package / 'models/face_landmarker.task').exists()
        else:
            config = json.loads(config_before)
            config['port'] = args.bridge_port
            config_path.write_text(json.dumps(config), encoding='utf-8')
        launch = subprocess.Popen([str(package / 'Yingche.exe'), '--control-dir', str(control.qa), str(args.clip.resolve())],
                                  cwd=package, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        launch.wait(timeout=10); assert launch.returncode == 0
        control.wait(lambda s: s.get('loaded') and s.get('gpupixelReady'), 40)
        owned = []
        for p in psutil.process_iter(['pid', 'exe', 'cmdline']):
            if p.info['exe'] and Path(p.info['exe']).resolve() == package / 'app/BeautyPlayerV060.exe' and str(control.qa) in (p.info['cmdline'] or []):
                owned.append(p)
        assert len(owned) == 1
        native = owned[0]
        assert control.state()['version'] == '0.6.0'
        checks.append('packaged launcher and native 0.6.0 start from the isolated package')
        start = control.state()['position']; time.sleep(1.2)
        assert control.state()['position'] > start + .5
        checks.append('video clock advances')
        control.send('pause', value=True)
        control.send('seek', seconds=34)
        control.wait(lambda s: abs(s.get('position', 0)-34) < .05)
        if args.missing_models:
            time.sleep(.4)
            state = control.state()
            assert not state.get('workerReady') and state['trackingWeight'] == 0
            for name, enabled in [('beauty', True), ('original', False)]:
                control.send('enabled', value=enabled); time.sleep(.25)
                control.send('snapshot', path=str(output / (name + '.png')))
            a = cv2.imread(str(output / 'beauty.png'))
            b = cv2.imread(str(output / 'original.png'))
            assert a is not None and b is not None and np.array_equal(a, b)
            assert not (package / 'models/face_landmarker.task').exists()
            report['status'] = state.get('analysisStatus')
            checks.append('without face models the picture equals original and no automatic download occurs')
        else:
            control.wait(lambda s: s.get('workerReady') and s.get('faces', 0) > 0, 30)
            time.sleep(.8)
            for name, enabled in [('beauty', True), ('original', False)]:
                control.send('enabled', value=enabled); time.sleep(.3)
                control.send('snapshot', path=str(output / (name + '.png')))
            a = cv2.imread(str(output / 'beauty.png')).astype(np.int16)
            b = cv2.imread(str(output / 'original.png')).astype(np.int16)
            changed = int(np.count_nonzero(np.max(np.abs(a-b), axis=2) > 1))
            assert changed > 100
            report['changedPixels'] = changed
            control.send('enabled', value=True)
            checks.append('installed tracking models enable actual native beauty pixels')
            control.send('bridge', value=True)
            control.wait(lambda s: '已就绪' in s.get('bridgeStatus', ''), 35)
            extension = json.loads(config_before)['extensionId']
            headers = {'Content-Type': 'application/json', 'X-Yingche-Extension': extension,
                       'Origin': 'chrome-extension://' + extension}
            def post(path, body):
                req = urllib.request.Request('http://127.0.0.1:' + str(args.bridge_port) + path,
                                             data=json.dumps(body).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    return json.load(response)
            session = post('/session', {})
            assert session['version'] == '0.4.1'
            headers['Authorization'] = 'Bearer ' + session['token']
            cap = cv2.VideoCapture(str(args.clip)); cap.set(cv2.CAP_PROP_POS_MSEC, 34000)
            ok, frame = cap.read(); cap.release(); assert ok
            ok, encoded = cv2.imencode('.jpg', frame); assert ok
            result = post('/analyze', {'id': 1, 'generation': 1, 'streamId': 'package-check', 'pts': 34,
                                      'sampleTime': time.monotonic()*1000, 'paused': True, 'jpeg': base64.b64encode(encoded).decode(), 'swapEnabled': False})
            assert len(result.get('faces', [])) > 0 and result.get('mask')
            report['bridgeFaces'] = len(result['faces'])
            checks.append('packaged legacy bridge accepts an extension session and analyzes a real frame')
            children = native.children(recursive=True)
            paths = [Path(p.exe()).resolve() for p in children]
            for version in ['face_engine_v041', 'face_engine_v060']:
                assert any(p == package / 'app' / version / 'FaceEngine.exe' for p in paths)
            checks.append('both face engines run from the isolated package')
            if len(control.state().get('screens', [])) > 1:
                control.send('separate'); control.wait(lambda s: s.get('separated'))
                control.send('separate'); control.wait(lambda s: not s.get('separated'))
                checks.append('dual-window separation and reunion work from the package')
            control.send('beauty', values={'smooth': 28, 'white': 16})
            time.sleep(.85)
            assert (control.qa / 'settings-v2.json').exists()
            checks.append('isolated per-media settings save')
        control.send('windowshot', path=str(output / 'window.png'))
        children = native.children(recursive=True)
        control.send('quit'); native.wait(timeout=15)
        _, alive = psutil.wait_procs(children, timeout=5); assert not alive
        native = None
        checks.append('normal exit cleans both owned engines')
        report['passed'] = True
    finally:
        config_path.write_bytes(config_before)
        if native and native.is_running():
            children = native.children(recursive=True)
            try: control.send('quit'); native.wait(timeout=10)
            except Exception:
                # Only the exact isolated process tree established above.
                for p in children:
                    if p.is_running(): p.terminate()
                native.terminate(); native.wait(timeout=10)
        log.close()
        (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
