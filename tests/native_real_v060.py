"""Real fixture playback, attached secondary screen, and owned worker failure.

Counters and saved frame pairs are evidence, not automatic perceptual approval.
"""
import json,os,subprocess,time,statistics
from pathlib import Path
import psutil,cv2,numpy as np
import control
root=Path(__file__).resolve().parents[1];out=root/'work/v060'/('real-'+str(time.time_ns()));out.mkdir()
control.qa=out/'qa';control.qa.mkdir()
log=(out/'player.log').open('w',encoding='utf-8')
proc=subprocess.Popen([str(root/'app/BeautyPlayerV060.exe'),'--control-dir',str(control.qa)],cwd=root,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
report={'cases':[],'checks':{},'visualQuality':'saved real frame pairs require visual/manual review','physicalUnplug':'not tested'}
driver=root/'work/v060/real-fixtures/driver-action-recognition.mp4'
walking=root/'work/v060/real-fixtures/face-demographics-walking.mp4'
pose=root/'work/v04/intel-fixtures/head-pose-face-detection-female.mp4'
suspended=[]
def check(name,ok):
    assert ok,name
    report['checks'][name]=True;print('PASS',name,flush=True)
def load(path,pts):
    control.send('load',path=str(path));control.wait(lambda s:s.get('loaded') and s.get('file')==str(path).replace('\\','/'))
    control.send('pause',value=True);control.send('seek',seconds=pts)
    control.wait(lambda s:abs(s.get('position',0)-pts)<.09 and s.get('resultGeneration')==s.get('generation'),20)
def pair(name,pts):
    control.send('pause',value=True);control.send('seek',seconds=pts)
    control.wait(lambda s:abs(s.get('position',0)-pts)<.09 and s.get('resultGeneration')==s.get('generation'))
    time.sleep(.25);control.send('hold-original',value=True)
    control.send('snapshot',path=str(out/(name+'-original.png')))
    control.send('hold-original',value=False);control.send('snapshot',path=str(out/(name+'-beauty.png')))
    (out/(name+'-state.json')).write_text(json.dumps(control.state(),ensure_ascii=False,indent=2),encoding='utf-8')
def play(name,path,pts,seconds):
    load(path,pts);control.send('pause',value=False)
    control.wait(lambda s:s.get('position',0)>pts+.3)
    first=control.state();start=time.monotonic();samples=[]
    owned=[psutil.Process(proc.pid),*psutil.Process(proc.pid).children(recursive=True)]
    for p in owned:p.cpu_percent()
    cpu=[];rss=[]
    while time.monotonic()-start<seconds:
        time.sleep(.1);samples.append(control.state());cpu.append(sum(p.cpu_percent() for p in owned if p.is_running()));rss.append(sum(p.memory_info().rss for p in owned if p.is_running())/2**20)
    last=samples[-1];elapsed=time.monotonic()-start
    item={'name':name,'seconds':elapsed,'positionDelta':last['position']-first['position'],'renderSubmissionsPerSecond':(last['rendered']-first['rendered'])/elapsed,
          'dropDelta':last['drops']-first['drops'],'decoderDropDelta':last['decoderDrops']-first['decoderDrops'],'cutsDelta':last['detectedCuts']-first['detectedCuts'],
          'faceSampleFraction':sum(s.get('faces',0)>0 for s in samples)/len(samples),'cpuMean':statistics.mean(cpu),'rssMiBMean':statistics.mean(rss),
          'cutReadbackMeanMs':last['cutReadbackMeanMs'],'cutReadbackMaxMs':last['cutReadbackMaxMs'],'last':last}
    report['cases'].append(item);print(json.dumps({k:v for k,v in item.items() if k!='last'},ensure_ascii=False),flush=True)
    check(name+' playback advances',item['positionDelta']>seconds*.85)
    control.send('pause',value=True);return item
try:
    control.wait(lambda s:s.get('workerReady') and s.get('gpupixelReady'),40)
    play('real phone occlusion and dark cabin',driver,35,8);pair('phone-occlusion',38)
    play('real hand over face',driver,109,8);pair('hand-occlusion',113.8)
    cut=play('real edit at 141.033 seconds',driver,139,5)
    check('real cut invalidates history',cut['cutsDelta']>=1)
    pair('after-cut',141.2)
    play('real entry and exit',walking,0,12);pair('entry',12)
    load(driver,35)
    if len(control.state()['screens'])>=2:
        control.send('separate');control.wait(lambda s:s.get('separated') and s.get('fullscreen'))
        screen=play('physical secondary screen 1080p30 source',driver,35,10)
        s=screen['last'];check('actual secondary display with different DPI',s['displayScreen']!=s['controlsScreen'] and s['displayDpr']>1)
        report['physicalDisplay']=s['screens'];control.send('controlshot',path=str(out/'physical-controls.png'))
        control.send('snapshot',path=str(out/'physical-display-frame.png'));control.send('close-controls')
        control.wait(lambda s:not s.get('separated') and s.get('paused'))
    load(pose,35);control.send('pause',value=False);control.wait(lambda s:s.get('faces',0)>0 and s.get('trackingWeight',0)>.5)
    # Bound the fault to child processes of this exact launched native instance.
    children=psutil.Process(proc.pid).children(recursive=True)
    workers=[p for p in children if p.name().lower()=='faceengine.exe' and Path(p.exe()).resolve().parent==root/'app/face_engine_v060']
    assert workers,[(p.pid,p.name()) for p in children]
    for p in workers:p.suspend();suspended.append(p)
    start_pos=control.state()['position'];time.sleep(.55);s=control.state()
    check('stale analysis fades to original visibly labelled',s['trackingWeight']==0 and '原片' in s['analysisStatus'])
    check('stalled analysis does not stall playback',s['position']>start_pos+.25)
    report['staleState']=s
    for p in suspended:p.resume()
    suspended=[];control.wait(lambda s:s.get('trackingWeight',0)>.3 and '人像' in s.get('analysisStatus',''),10)
    check('fresh analysis recovers',True)
    for p in reversed(workers):
        if p.is_running():p.kill()
    control.wait(lambda s:not s.get('workerReady'),10);start_pos=control.state()['position'];time.sleep(1.2);s=control.state()
    check('worker exit keeps original video playing',s['position']>start_pos+.8 and s['faces']==0)
    report['workerExitState']=s
    report['passed']=True
finally:
    for p in suspended:
        if p.is_running():p.resume()
    if proc.poll() is None:
        try:control.send('quit')
        except Exception:proc.terminate()
    proc.wait(timeout=15);log.close()
    (out/'real-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'work/v060/latest-real.txt').write_text(str(out),encoding='utf-8')
