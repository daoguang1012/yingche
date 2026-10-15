"""Same real clips/settings for before/after; app process tree only, isolated data."""
import json, os, subprocess, sys, time, statistics, threading
from pathlib import Path
import cv2, psutil
import control

root=Path(__file__).resolve().parents[1]
label=sys.argv[1] if len(sys.argv)>1 else 'before'
exe=Path(sys.argv[2]) if len(sys.argv)>2 else root/'app/BeautyPlayerV041.exe'
out=root/'work/v060'/label;out.mkdir(parents=True,exist_ok=True)
control.qa=out/('qa-'+str(time.time_ns()));control.qa.mkdir()
log=(out/'player.log').open('w',encoding='utf-8')
proc=subprocess.Popen([str(exe),'--control-dir',str(control.qa)],cwd=root,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
report={'exe':str(exe),'cpuConvention':'100% = one logical CPU; summed owned process tree',
        'gpuConvention':'whole-device NVIDIA utilization and VRAM, includes other applications',
        'visualQuality':'not established by these counters','cases':[]}
gpu=[];stop=threading.Event()
def sample_gpu():
    while not stop.is_set():
        try:
            text=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=3)
            vals=text.strip().splitlines()[0].split(',');gpu.append((time.monotonic(),float(vals[0]),float(vals[1])))
        except (OSError,ValueError,subprocess.SubprocessError):pass
        stop.wait(1)
thread=threading.Thread(target=sample_gpu,daemon=True);thread.start()
def summary(values):
    return {'mean':round(statistics.mean(values),3),'max':round(max(values),3)} if values else None
try:
    control.wait(lambda s:s.get('workerReady') and s.get('gpupixelReady'),40)
    paths=[Path(sys.argv[3])] if len(sys.argv)>3 else [root/'work/v04/intel-fixtures'/name for name in ['head-pose-face-detection-female.mp4','head-pose-face-detection-female-and-male.mp4']]
    for path in paths:
        filename=path.name
        cap=cv2.VideoCapture(str(path));metadata={'width':cap.get(3),'height':cap.get(4),'fps':cap.get(5),'frames':cap.get(7)};cap.release()
        for enabled in [False,True]:
            control.send('load',path=str(path));control.wait(lambda s:s.get('loaded') and s.get('position',0)>0)
            control.send('enabled',value=enabled)
            control.send('beauty',values={'smooth':35,'detail':70,'white':15,'warm':0,'pink':8,'slim':0,'eyes':0,'chin':0,'nose':0,'lip':0,'blush':0,'sharp':10})
            control.send('seek',seconds=34);control.wait(lambda s:34<s.get('position',0)<36)
            control.wait(lambda s:s.get('position',0)>=35)
            owned=[psutil.Process(proc.pid),*psutil.Process(proc.pid).children(recursive=True)]
            for p in owned:p.cpu_percent()
            start=time.monotonic();first=control.state();samples=[];cpus=[];rss=[]
            while time.monotonic()-start<10:
                time.sleep(.25);samples.append(control.state());cpus.append(sum(p.cpu_percent() for p in owned if p.is_running()));rss.append(sum(p.memory_info().rss for p in owned if p.is_running())/2**20)
            last=samples[-1];elapsed=time.monotonic()-start
            audio=any(t.get('type')=='audio' and t.get('selected')=='yes' for t in last.get('tracks',[]))
            av=[abs(s['avsync'])*1000 for s in samples if audio and s.get('avsyncAvailable',True)]
            gs=[g for g in gpu if g[0]>=start]
            item={'clip':filename,'source':metadata,'beautyEnabled':enabled,'elapsed':elapsed,'positionDelta':last['position']-first['position'],
                  'renderSubmissionsPerSecond':(last['rendered']-first['rendered'])/elapsed,'dropsDelta':last['drops']-first['drops'],'decoderDropsDelta':last['decoderDrops']-first['decoderDrops'],
                  'avsyncAbsMs':summary(av),'avsyncNote':'audio/video properties' if av else 'unmeasured: no active audio or property unavailable',
                  'cpuPercent':summary(cpus),'rssMiB':summary(rss),'wholeGpuPercent':summary([g[1] for g in gs]),'wholeVramMiB':summary([g[2] for g in gs]),
                  'faceFrames':sum(s.get('faces',0)>0 for s in samples),'sampleCount':len(samples),'analysisMs':summary([s['analysisMs'] for s in samples]),'final':last}
            report['cases'].append(item);print(json.dumps({k:v for k,v in item.items() if k!='final'},ensure_ascii=False),flush=True)
            control.send('windowshot',path=str(out/(Path(filename).stem+('-beauty' if enabled else '-original')+'.png')))
    report['completed']=True
finally:
    stop.set();thread.join(timeout=4)
    if proc.poll() is None:
        try:control.send('quit')
        except Exception:proc.terminate()
    proc.wait(timeout=12);log.close()
    (out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
