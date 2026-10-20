"""How far the native effect geometry trails a moving face, synchronised display off vs on.

Uses the generated clips from tests/make_motion_clip.py, whose per-frame eye positions are exact.
Each 10 Hz state sample records the pts of the frame actually shown and the eye centres the shader drew;
error is the distance to the true eyes in that frame, as a fraction of the true inter-eye distance.
Usage: python tests/native_drift.py [fps ...] [--swap]
"""
import json,os,subprocess,sys,time,statistics
from pathlib import Path
import numpy as np
import control

root=Path(__file__).resolve().parents[1]
fpss=[int(a) for a in sys.argv[1:] if a.isdigit()] or [30,60]
swap='--swap' in sys.argv
out=root/'work/drift'/('drift-'+str(time.time_ns()));out.mkdir(parents=True)
control.qa=out/'qa';control.qa.mkdir()
env=os.environ.copy()
for key,suffix in [('APPDATA','roaming'),('LOCALAPPDATA','local'),('TEMP','temp'),('TMP','temp')]:
    env[key]=str(out/suffix);Path(env[key]).mkdir(exist_ok=True)
PHASES=['still','swing','reversal','zoom','tilt','shake','still2']
log=open(out/'player.log','w',encoding='utf-8')
proc=subprocess.Popen([str(root/'app/BeautyPlayerV060.exe'),'--control-dir',str(control.qa)],cwd=root,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
runs=[]
try:
    control.wait(lambda s:s.get('workerReady'),40)
    control.send('enabled',value=True);control.send('beauty',values={'smooth':40,'white':10,'detail':60,'sharp':8,'slim':60,'eyes':40})
    if swap:
        control.send('swap-source',path=str(root/'work/motion/source.png'));control.wait(lambda s:s.get('swapSourceReady'),90)
        control.send('swap',value=True,target='largest',feather=35,strength=100)
    for fps in fpss:
        path=(root/f'work/motion/motion-{fps}.mp4').resolve()
        control.send('load',path=str(path));control.wait(lambda s:s.get('loaded') and s.get('file')==str(path).replace('\\','/'))
        for sync in [False,True]:
            control.send('sync',value=sync);control.send('pause',value=True);control.send('seek',seconds=0)
            control.wait(lambda s:abs(s.get('position',0))<.05,20);time.sleep(.8)
            before=control.state();control.send('pause',value=False)
            samples=[];end=time.monotonic()+19.5
            while time.monotonic()<end:
                time.sleep(.1);s=control.state()
                samples.append({k:s.get(k) for k in ['displayPts','drawnEyes','faces','trackingWeight','syncActive','syncDelayMs','audioDelayMs','displayLagMs','roundTripMs','position','avsync','drops','decoderDrops','swapFaces']})
            runs.append({'fps':fps,'sync':sync,'samples':samples,'dropsBefore':before.get('drops') or 0})
    control.send('pause',value=True);control.send('quit')
finally:
    try:proc.wait(timeout=15);print('player exit code',proc.returncode,flush=True)
    except subprocess.TimeoutExpired:print('PLAYER DID NOT EXIT',flush=True);proc.kill()
    log.close()
report=[]
for run in runs:
    truth=json.loads((root/f"work/motion/motion-{run['fps']}.json").read_text(encoding='utf-8'));seg=truth['segments']
    byphase={p:[] for p in PHASES};missing=0
    for s in run['samples']:
        if s['displayPts'] is None:continue
        i=min(len(truth['eyes'])-1,max(0,round(s['displayPts']*run['fps'])))
        t=i/run['fps'];phase=PHASES[min(len(PHASES)-1,max(k for k in range(len(seg)-1) if seg[k]<=t))]
        true=np.array(truth['eyes'][i])*[truth['width'],truth['height']]
        if not s['faces'] or (s['trackingWeight'] or 0)<.5:missing+=1;continue
        drawn=np.array(s['drawnEyes'])*[truth['width'],truth['height']]
        byphase[phase].append(float(np.linalg.norm(drawn-true,axis=1).mean()/np.linalg.norm(true[0]-true[1])*100))
    allerr=[e for v in byphase.values() for e in v];last=run['samples'][-1]
    item={'fps':run['fps'],'sync':run['sync'],'n':len(allerr),'effectMissing':missing,
          'medianPct':round(statistics.median(allerr),1),'p90Pct':round(sorted(allerr)[int(len(allerr)*.9)],1),'maxPct':round(max(allerr),1),
          'phaseMedianPct':{p:round(statistics.median(v),1) for p,v in byphase.items() if v},
          'syncDelayMs':last['syncDelayMs'],'audioDelayMs':last['audioDelayMs'],'displayLagMs':last['displayLagMs'],
          'addedDrops':(last['drops'] or 0)-run['dropsBefore'],'maxAbsAvsyncMs':round(max(abs(x['avsync'] or 0) for x in run['samples'])*1000,1)}
    report.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
(out/'drift.json').write_text(json.dumps({'report':report,'runs':runs},ensure_ascii=False,indent=1),encoding='utf-8')
print(out)
