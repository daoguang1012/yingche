"""Exercise record and byte limits without modifying user settings."""
import json,subprocess,time
from pathlib import Path
import control
root=Path(__file__).resolve().parents[1];out=root/'work/v060'/('limits-'+str(time.time_ns()));out.mkdir()
beauty=dict(smooth=25,detail=70,white=10,warm=0,pink=5,slim=0,eyes=0,chin=0,nose=0,lip=0,blush=0,sharp=8)
base={'version':2,'defaults':{'beauty':beauty,'enabled':True},'media':{},'positions':{},'lastDirectory':''}
checks=[]
for name in ['records','bytes']:
    control.qa=out/name;control.qa.mkdir();config=control.qa/'settings-v2.json'
    payload=json.loads(json.dumps(base))
    if name=='records':payload['media']={f'existing-{i}':{'beauty':beauty,'enabled':True} for i in range(2000)}
    else:
        payload['defaults']['padding']=''
        current=len(json.dumps(payload,separators=(',',':')).encode('utf-8'))
        payload['defaults']['padding']='x'*(4*1024*1024-200-current)
    config.write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
    log=(control.qa/'log.txt').open('w',encoding='utf-8')
    p=subprocess.Popen([str(root/'app/BeautyPlayerV060.exe'),'--control-dir',str(control.qa)],cwd=root,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        control.wait(lambda s:s.get('workerReady'),40)
        control.send('load',path=str(root/'work/v04/intel-fixtures/head-pose-face-detection-female.mp4'));control.wait(lambda s:s.get('loaded'))
        control.send('pause',value=True);before=config.read_bytes()
        control.send('beauty',values={'smooth':26});time.sleep(1)
        s=control.state()
        if name=='records':
            assert s['pictureScope']==2 and '2000' in s['pictureStatus'],s['pictureStatus']
            assert len(json.loads(config.read_text(encoding='utf-8'))['media'])==2000
        else:
            assert '容量限制' in s['pictureStatus'],s['pictureStatus']
            assert config.read_bytes()==before
        checks.append(name);print('PASS',name,s['pictureStatus'],flush=True)
    finally:
        control.send('quit');p.wait(timeout=15);log.close()
(out/'limits-results.json').write_text(json.dumps({'passed':True,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
(root/'work/v060/latest-limits.txt').write_text(str(out),encoding='utf-8')
