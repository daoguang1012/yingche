"""Realtime head-pose integration on Intel CC-BY-4.0 public clips (12 FPS).
These counts are a functional continuity check, not a labelled accuracy benchmark.
"""
from pathlib import Path
import sys,time,json,cv2,numpy as np,base64,contextlib
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'tools'));out=r/'work/v041'
from face_worker import FaceProcessor
p=FaceProcessor(r/'models/face_landmarker.task')
p.set_source(cv2.cvtColor(cv2.imread(str(r/'work/v02/swap-source.jpg')),cv2.COLOR_BGR2RGB))
reports=[];contacts=[]
try:
 for clip,start_sec,seconds,target,expected in [('head-pose-face-detection-female.mp4',35,12,'largest',1),('head-pose-face-detection-female-and-male.mp4',35,12,'all',2)]:
  cap=cv2.VideoCapture(str(r/'work/v04/intel-fixtures'/clip));fps=cap.get(cv2.CAP_PROP_FPS);cap.set(cv2.CAP_PROP_POS_MSEC,start_sec*1000)
  writer=cv2.VideoWriter(str(out/('dlc-'+str(expected)+'-face.avi')),cv2.VideoWriter_fourcc(*'MJPG'),fps,(1280,360))
  assert writer.isOpened()
  rows=[];origin=time.perf_counter()
  try:
   for i in range(round(seconds*fps)):
    ok,frame=cap.read()
    if not ok:break
    due=origin+i/fps
    if due>time.perf_counter():time.sleep(due-time.perf_counter())
    frame=cv2.resize(frame,(960,540));rgba=cv2.cvtColor(frame,cv2.COLOR_BGR2RGBA)
    req={'id':i,'generation':expected,'pts':start_sec+i/fps,'sampleTime':time.monotonic()*1000,'width':960,'height':540,'_raw_rgba':rgba.tobytes(),'swapEnabled':True,'swapTarget':target,'swapFeather':35}
    result=p.process(req);assert not result.get('swapError'),result.get('swapError')
    row={k:result.get(k) for k in ['ms','swapMs','swapAgeMs','swapFaces','flowQuality','trackingMode','trackIds']};row.update(frame=i,faces=len(result['faces']));rows.append(row)
    comp=frame.copy()
    if result.get('swap'):
     layer=cv2.imdecode(np.frombuffer(base64.b64decode(result['swap']),np.uint8),cv2.IMREAD_UNCHANGED);alpha=layer[:,:,3:4]/255;comp=np.uint8(layer[:,:,:3]*alpha+frame*(1-alpha))
    a=cv2.resize(frame,(640,360));b=cv2.resize(comp,(640,360))
    cv2.putText(a,'ORIGINAL / Intel CC-BY-4.0',(8,23),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
    cv2.putText(b,'AI FACE SWAP / DLC / '+str(round(start_sec+i/fps,1))+'s',(8,23),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
    joined=np.concatenate([a,b],axis=1);writer.write(joined)
    if i%round(fps*5)==round(fps):contacts.append(cv2.resize(joined,(960,270)))
   steady=rows[12:]
   report={'clip':clip,'fps':fps,'frames':len(rows),'expectedFaces':expected,'startSeconds':start_sec,
    'medianTrackingMs':float(np.median([x['ms'] for x in steady])),'p95TrackingMs':float(np.percentile([x['ms'] for x in steady],95)),
    'medianSwapMs':float(np.median([x['swapMs'] for x in steady])),'p95SwapMs':float(np.percentile([x['swapMs'] for x in steady],95)),
    'trackedExpectedFrames':sum(x['faces']==expected for x in steady),'swappedExpectedFrames':sum(x['swapFaces']==expected for x in steady),
    'steadyFrames':len(steady),'rows':rows}
   reports.append(report);print(json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
  finally:cap.release();writer.release()
 (out/'dlc-pose-acceptance.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
 if contacts:cv2.imwrite(str(out/'dlc-pose-contact-sheet.png'),np.concatenate(contacts))
finally:p.close()

