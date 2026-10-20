"""Same-frame beauty snapshots from the real native player for visual review.

Usage: python tests/beauty_look.py LABEL [video:pts ...]
Writes work/look/LABEL-*/ with original, natural, soft and face-crop comparison sheets.
"""
import json,os,subprocess,sys,time
from pathlib import Path
import cv2,numpy as np,psutil
import control

root=Path(__file__).resolve().parents[1]
label=sys.argv[1] if len(sys.argv)>1 else 'look'
shots=[a.rsplit(':',1) for a in sys.argv[2:]] or [['work/v04/intel-fixtures/head-pose-face-detection-female.mp4','35'],['work/portrait-motion.mp4','6'],['work/v050/portrait-1080p24.mp4','4']]
out=root/'work/look'/(label+'-'+str(time.time_ns()));out.mkdir(parents=True)
control.qa=out/'qa';control.qa.mkdir()
env=os.environ.copy()
for key,suffix in [('APPDATA','roaming'),('LOCALAPPDATA','local'),('TEMP','temp'),('TMP','temp')]:
    env[key]=str(out/suffix);Path(env[key]).mkdir(exist_ok=True)
PRESETS={'natural':{'smooth':25,'detail':70,'white':10,'sharp':8,'warm':0,'pink':0,'slim':0,'eyes':0,'lip':0,'blush':0},
         'soft':{'smooth':45,'detail':60,'white':18,'sharp':6,'warm':0,'pink':6,'slim':0,'eyes':0,'lip':0,'blush':0}}
log=open(out/'player.log','w',encoding='utf-8')
proc=subprocess.Popen([str(root/'app/BeautyPlayerV060.exe'),'--control-dir',str(control.qa)],cwd=root,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
report=[]
try:
    control.wait(lambda s:s.get('workerReady'),40)
    for index,(video,pts) in enumerate(shots):
        pts=float(pts);path=(root/video).resolve()
        control.send('load',path=str(path));control.wait(lambda s:s.get('loaded') and s.get('file')==str(path).replace('\\','/'))
        control.send('pause',value=True);control.send('seek',seconds=pts)
        control.wait(lambda s:abs(s.get('position',0)-pts)<.02 and s.get('resultGeneration')==s.get('generation'),20)
        images={}
        for name in ['original','natural','soft']:
            if name=='original':control.send('enabled',value=False)
            else:control.send('enabled',value=True);control.send('beauty',values=PRESETS[name])
            time.sleep(.6)
            file=out/f'{index}-{name}.png';control.send('snapshot',path=str(file));time.sleep(.2)
            images[name]=cv2.imread(str(file))
        s=control.state();faces=s.get('facePoints') or []
        # Face crop from the brightest skin-mask area is not exposed; crop the centre third generously instead.
        h,w=images['original'].shape[:2]
        report.append({'video':video,'pts':pts,'faces':s.get('faces'),'size':[w,h]})
        sheet=np.hstack([images[n] for n in ['original','natural','soft']])
        cv2.imwrite(str(out/f'{index}-sheet.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,92])
    control.send('quit')
finally:
    try:proc.wait(timeout=15)
    except subprocess.TimeoutExpired:proc.kill()
    log.close()
(out/'look.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
