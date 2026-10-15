import subprocess,time,runpy,socket,shutil,json,sys,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
test_ext=root/'work/v050/test-extension';shutil.copytree(root/'work/v050/edge-extension',test_ext,dirs_exist_ok=True)
for name in ['background.js','manifest.json','bridge-config.json']:
 p=test_ext/name;p.write_text(p.read_text(encoding='utf-8').replace('18766','29766'),encoding='utf-8')
log=open(root/'work/v050/bridge-test.log','w',encoding='utf-8')
proc=subprocess.Popen([str(root/'app/face_engine_v041/FaceEngine.exe'),'--bridge',str(root/'models/face_landmarker.task'),str(test_ext/'bridge-config.json')],cwd=root,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
try:
    for _ in range(150):
        assert proc.poll() is None,'Bridge process exited'
        try:
            with socket.create_connection(('127.0.0.1',29766),timeout=.2):break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('Bridge did not listen')
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:probe.bind(('127.0.0.1',29766))
        except OSError:print('EXCLUSIVE_BRIDGE_PORT_OK',flush=True)
        else:raise AssertionError('Bridge port accepted another listener')
    req=urllib.request.Request('http://127.0.0.1:29766/session',data=b'{}',headers={'Content-Type':'application/json','X-Yingche-Extension':'apamfckhomfpifcdadlphjjpbllfnpba'})
    session=json.loads(urllib.request.urlopen(req).read());assert session['version']=='0.4.1';print('ISOLATED_BRIDGE',session['version'],proc.pid,flush=True)
    req=urllib.request.Request('http://127.0.0.1:29766/analyze',data=b'{"jpeg":""}',headers={'Content-Type':'application/json','X-Yingche-Extension':'apamfckhomfpifcdadlphjjpbllfnpba','Authorization':'Bearer '+session['token']})
    try:urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        message=e.read().decode();print('COMPRESSED_DECODER_REJECTION',message,flush=True);assert 'RGBA frame required' not in message
    runpy.run_path(str(root/'tests'/(sys.argv[1] if len(sys.argv)>1 else 'edge_interpolation_v050.py')),run_name='__main__')
finally:proc.terminate();proc.wait(timeout=8);log.close()
