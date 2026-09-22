import json,subprocess,time,sys,os
from pathlib import Path
import cv2,numpy as np,psutil
import control
root=Path(__file__).resolve().parents[1]
out=root/'work/v041';control.qa=out/('qa-smoke-'+str(int(time.time()*1000)));control.qa.mkdir(parents=True,exist_ok=True)
log=open(out/'player2.log','w',encoding='utf-8')
proc=subprocess.Popen([os.environ.get('YINGCHE_TEST_EXE',str(root/'app/BeautyPlayerV041.exe')),'--control-dir',str(control.qa),str(root/'work/portrait-motion.mp4')],cwd=os.environ.get("YINGCHE_TEST_CWD",str(root)),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
report={}
def snap(name):
    path=out/(name+'.png');control.send('snapshot',path=str(path));return cv2.imread(str(path))
try:
    control.wait(lambda s:s.get('loaded') and s.get('workerReady') and s.get('position',0)>1,25)
    control.send('pause',value=True);control.send('seek',seconds=2.)
    control.wait(lambda s:abs(s.get('position',0)-2)<.01 and s.get('resultGeneration')==s.get('generation'),15)
    time.sleep(.3);report['initial']=control.state()
    live=psutil.Process(proc.pid);report['processPaths']=[live.exe(),*[c.exe() for c in live.children(recursive=True)]]
    report['workingDirectory']=live.cwd();report['gpupixelDll']=[m.path for m in live.memory_maps() if Path(m.path).name.lower()=='gpupixel.dll']
    package=Path(live.exe()).resolve().parent.parent
    system_console=(Path(os.environ['WINDIR'])/'System32/conhost.exe').resolve()
    app_paths=[v for v in report['processPaths'] if Path(v).resolve()!=system_console]
    assert len(app_paths)>=2 and all(package in Path(v).resolve().parents for v in app_paths),report['processPaths']
    assert report['gpupixelDll'] and all(package in Path(v).resolve().parents for v in report['gpupixelDll'])
    active=snap('gpupixel-active')
    control.send('enabled',value=False);original=snap('gpupixel-original')
    control.send('enabled',value=True);control.send('beauty',values={k:0 for k in control.state()['beauty']})
    control.wait(lambda s:s.get('resultGeneration')==s.get('generation'))
    zero=snap('gpupixel-zero')
    control.send('beauty',values={**{k:0 for k in control.state()['beauty']},'sharp':150});sharp=snap('gpupixel-sharp-only')
    report['sharpOnlyMAE']=float(np.abs(original.astype(float)-sharp).mean());assert report['sharpOnlyMAE']>.05
    control.send('beauty',values={'smooth':150,'white':100,'detail':50,'sharp':30,'slim':0,'eyes':0,'chin':0,'nose':0,'lip':0,'blush':0,'pink':0,'warm':0})
    strong=snap('gpupixel-strong');time.sleep(.5)
    report['originalMean']=float(original.mean());report['activeMean']=float(active.mean());report['zeroMAE']=float(np.abs(original.astype(float)-zero).mean());report['effectMAE']=float(np.abs(original.astype(float)-strong).mean())
    control.send('beauty',values={'smooth':50,'white':25,'slim':100,'eyes':50,'lip':25,'blush':15})
    before=snap('gpupixel-paused-before');time.sleep(1);after=snap('gpupixel-paused-after');report['pausedMAE']=float(np.abs(before.astype(float)-after).mean())
    control.send('seek',seconds=25.);control.wait(lambda s:s.get('position',0)>24.9 and s.get('resultGeneration')==s.get('generation'));report['noface']=control.state();snap('gpupixel-noface')
    control.send('seek',seconds=2.);control.wait(lambda s:abs(s.get('position',0)-2)<.01 and s.get('faces',0)>0 and s.get('resultGeneration')==s.get('generation'));report['seekReturn']=control.state()
    control.send('windowshot',path=str(out/'gpupixel-ui2.png'))
    report['flatBackgroundStd']=float(original[150:470,80:180].std(axis=(0,1)).max())
    assert report['flatBackgroundStd']<1.,report['flatBackgroundStd']
    assert report['originalMean']>20 and report['activeMean']>20,report
    assert report['zeroMAE']<.8,report['zeroMAE']
    assert report['effectMAE']>1.,report['effectMAE']
    assert report['pausedMAE']<.2,report['pausedMAE']
    assert report['noface']['faces']==0
    control.send('beauty',values={k:0 for k in control.state()['beauty']})
    unmodified=snap('native-pre-swap')
    control.send('swap-source',path=str(root/'work/v02/swap-source.jpg'))
    control.wait(lambda s:s.get('swapSourceReady'),65)
    control.send('swap',value=True)
    control.wait(lambda s:s.get('swapFaces')==1 and not s.get('swapPending') and s.get('resultGeneration')==s.get('generation'),25)
    swapped=snap('native-swap-zero-beauty')
    roi=np.abs(swapped.astype(float)-unmodified).max(2)>15
    assert roi.sum()>500,int(roi.sum())
    control.send('beauty',values={'white':120})
    whitened=snap('native-swap-with-beauty')
    report['swapChangedPixels']=int(roi.sum())
    report['swapFaceBeautyDelta']=float(np.abs(whitened.astype(float)-swapped)[roi].mean())
    assert report['swapFaceBeautyDelta']>2,report['swapFaceBeautyDelta']
    control.send('swap-source',path='');control.wait(lambda s:not s.get('swapSourceReady') and s.get('swapFaces')==0)
    report['passed']=True
finally:
    (out/'native-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if proc.poll() is None:
        try:control.send('quit')
        except Exception:proc.terminate()
    print('Player exit:',proc.poll(),flush=True)
    proc.wait(timeout=8);log.close()
print(json.dumps({k:v for k,v in report.items() if not isinstance(v,dict)},indent=2))
