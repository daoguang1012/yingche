"""Deep-Live-Cam headless integration with an independent, bounded swap worker.
Inference/alignment: InsightFace as used by DLC. Paste-back/GPEN: actual DLC core.
No video frames or source identity are sent off this machine.
"""
from pathlib import Path
import contextlib,threading,time,sys
import cv2
import numpy as np
from insightface_runtime.app.common import Face
from insightface_runtime.model_zoo.inswapper import INSwapper
from insightface_runtime.model_zoo.arcface_onnx import ArcFaceONNX
from insightface_runtime.model_zoo.retinaface import RetinaFace
from dlc_core import _fast_paste_back,_get_soft_alpha,enhance_face_onnx,apply_color_transfer
ANCHORS=[1,4,6,33,133,263,362,61,291,50,280,168,98,327]
ENGINE='Deep-Live-Cam / d759e31 / INSwapper + GPEN-256'

class SwapEngine:
 def __init__(self,model_dir):
  import onnxruntime as ort
  self.root=Path(model_dir);self.lock=threading.Lock();self.source=None
  options=ort.SessionOptions();options.enable_mem_pattern=False
  options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.intra_op_num_threads=2;options.log_severity_level=3
  providers=['DmlExecutionProvider','CPUExecutionProvider'] if 'DmlExecutionProvider' in ort.get_available_providers() else ['CPUExecutionProvider']
  def session(name):
   path=self.root/name
   if not path.is_file():raise ValueError('换脸模型缺失：'+name)
   return ort.InferenceSession(path.read_bytes(),sess_options=options,providers=providers)
  # Third-party constructors print diagnostics; stdout is reserved for the host protocol.
  with contextlib.redirect_stdout(sys.stderr):
   self.detector=RetinaFace(model_file=str(self.root/'det_10g.onnx'),session=session('det_10g.onnx'))
   self.detector.prepare(ctx_id=0,input_size=(640,640),det_thresh=.55)
   self.recognizer=ArcFaceONNX(model_file=str(self.root/'arcface_w600k_r50.onnx'),session=session('arcface_w600k_r50.onnx'))
   self.swapper=INSwapper(model_file=str(self.root/'inswapper_128_fp16.onnx'),session=session('inswapper_128_fp16.onnx'))
  self.enhancer=session('GPEN-BFR-256.onnx')
  self.provider='DirectML GPU' if self.swapper.session.get_providers()[0]=='DmlExecutionProvider' else 'CPU'
 def detect(self,bgr):
  boxes,kps=self.detector.detect(bgr,max_num=4,metric='default')
  return [Face(bbox=b[:4],kps=kps[i],det_score=float(b[4])) for i,b in enumerate(boxes)]
 def set_source(self,image,locator=None):
  with self.lock:
   self.source=None
   scale=min(1.,1280/max(image.shape[:2]))
   bgr=cv2.cvtColor(cv2.resize(image,(round(image.shape[1]*scale),round(image.shape[0]*scale))),cv2.COLOR_RGB2BGR)
   faces=self.detect(bgr)
   if not faces:raise ValueError('照片里未检测到清晰人脸，请换一张正面照片')
   source=max(faces,key=lambda f:float(np.prod(f.bbox[2:]-f.bbox[:2])))
   self.recognizer.get(bgr,source)
   if source.normed_embedding is None or not np.isfinite(source.normed_embedding).all():raise ValueError('源照片特征无效')
   self.source=source
   return {'provider':self.provider,'sourceFaces':len(faces),'swapEngine':ENGINE}
 def clear_source(self):
  with self.lock:self.source=None
 def infer(self,image,faces,ids,selected):
  h,w=image.shape[:2];bgr=cv2.cvtColor(image,cv2.COLOR_RGB2BGR);patches=[]
  with self.lock:
   if self.source is None:return []
   detected=self.detect(bgr);used=set()
   for pts,track_id in zip(faces,ids):
    if track_id not in selected:continue
    center=pts[1]*[w,h]
    matches=[(float(np.linalg.norm(f.kps[2]-center)),j,f) for j,f in enumerate(detected) if j not in used]
    if not matches:continue
    distance,j,face=min(matches,key=lambda item:item[0]);fw=float(np.linalg.norm((pts[234]-pts[454])*[w,h]))
    if distance>max(12.,fw*.35):continue
    used.add(j)
    fake,matrix=self.swapper.get(bgr,face,self.source,paste_back=False)
    if fake is None or not np.isfinite(fake).all():continue
    # Restore details using DLC's actual GPEN pipeline at 256 px.
    fake=cv2.resize(fake,(256,256),interpolation=cv2.INTER_CUBIC)
    kps=(face.kps@matrix[:,:2].T+matrix[:,2])*2
    restored=enhance_face_onnx(fake,Face(kps=kps),self.enhancer,256)
    # Preserve some swap texture rather than replacing every detail with restoration.
    fake=cv2.addWeighted(fake,.25,restored,.75,0)
    matrix=matrix*2
    crop=cv2.warpAffine(bgr,matrix,(256,256),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
    fake=cv2.addWeighted(fake,.7,apply_color_transfer(fake,crop),.3,0)
    patches.append({'id':track_id,'fake':fake,'matrix':matrix,'points':pts.copy()})
  return patches

def image_shape(job):return job['image'].shape

class AsyncSwap:
 def __init__(self,engine):
  self.engine=engine;self.cv=threading.Condition();self.pending=None;self.running=None;self.result=None
  self.epoch=0;self.closed=False;self.last_key=None;self.target_id=None;self.target_mode=None;self.error=''
  self.thread=threading.Thread(target=self._loop,name='DLC-swap',daemon=True);self.thread.start()
 def reset(self):
  with self.cv:
   self.epoch+=1;self.pending=None;self.result=None;self.last_key=None;self.target_id=None;self.target_mode=None;self.error=''
 def submit(self,image,faces,ids,req):
  mode=req.get('swapTarget','largest')
  if not faces:return
  if mode!=self.target_mode:self.target_id=None;self.target_mode=mode
  if mode=='all':selected=list(ids)
  else:
   if self.target_id not in ids:
    order=sorted(range(len(faces)),key=lambda i:float(faces[i][1,0]))
    if mode=='largest':index=max(order,key=lambda i:float(np.ptp(faces[i][:,0])*np.ptp(faces[i][:,1])))
    else:
     try:index=order[int(mode)]
     except (ValueError,IndexError):index=None
    self.target_id=ids[index] if index is not None else None
   selected=[self.target_id] if self.target_id is not None else []
  key=(self.epoch,req.get('pts'),mode,tuple(selected),float(req.get('swapFeather',35)))
  with self.cv:
   if key==self.last_key:return
   self.last_key=key
   self.pending={'image':image,'faces':[p.copy() for p in faces],'ids':list(ids),'selected':selected,
     'epoch':self.epoch,'key':key,'sampleTime':req.get('sampleTime',0),'pts':req.get('pts',0)}
   self.cv.notify()
 def _loop(self):
  while True:
   with self.cv:
    self.cv.wait_for(lambda:self.closed or self.pending is not None)
    if self.closed:return
    job=self.pending;self.pending=None;self.running=job['key']
   start=time.perf_counter();error=''
   try:patches=self.engine.infer(job['image'],job['faces'],job['ids'],job['selected'])
   except Exception as exc:patches=[];error=str(exc)
   with self.cv:
    self.running=None
    if job['epoch']==self.epoch:
     previous=self.result
     # A missed secondary detector must not erase a still-tracked face for one frame.
     # Keep its original timestamp; compose reprojects to current landmarks and
     # independently rejects old, mismatched or geometrically inconsistent patches.
     reuse=not patches and not error and previous is not None and previous['patches'] and image_shape(job)==image_shape(previous) and 0<=job['sampleTime']-previous['sampleTime']<=260 and all(p['id'] in job['ids'] and p['id'] in job['selected'] for p in previous['patches'])
     self.result={**previous,'reused':True} if reuse else {**job,'patches':patches,'ms':(time.perf_counter()-start)*1000,'reused':False}
     self.error=error
 def compose(self,image,faces,ids,req,oval):
  h,w=image.shape[:2];output=np.zeros((h,w,4),np.uint8)
  with self.cv:
   result=self.result;error=self.error;busy=self.pending is not None or self.running is not None
  info={'swapEngine':ENGINE,'swapMs':round(result['ms'],2) if result else 0,'swapPending':busy,
    'swapError':error,'swapAgeMs':0,'swapFaces':0,'swapState':'pending' if result is None else 'no-patch','swapReused':bool(result and result.get('reused')),'provider':self.engine.provider}
  if result is None or error:return output,info
  if image.shape!=result['image'].shape:return output,info
  age=0. if req.get('paused') and abs(req.get('pts',0)-result['pts'])<.002 else max(0.,req.get('sampleTime',0)-result['sampleTime'])
  info['swapAgeMs']=round(age,2)
  # A stale or geometrically inconsistent patch must never float over a different face.
  if age>260:info['swapState']='expired';return output,info
  freshness=float(np.clip((260-age)/100,0,1))
  for patch in result['patches']:
   if patch['id'] not in ids:info['swapState']='track-mismatch';continue
   pts=faces[ids.index(patch['id'])];old=patch['points']
   src=np.float32(old[ANCHORS]*[w,h]);dst=np.float32(pts[ANCHORS]*[w,h])
   motion,inliers=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=100)
   if motion is None or inliers is None or inliers.mean()<.6:info['swapState']='alignment-rejected';continue
   face_width=float(np.linalg.norm((pts[234]-pts[454])*[w,h]))
   residual=np.median(np.linalg.norm(src@motion[:,:2].T+motion[:,2]-dst,axis=1))
   if residual>max(2.5,face_width*.055):info['swapState']='pose-changed';continue
   inv_motion=np.vstack([cv2.invertAffineTransform(motion),[0,0,1]])
   matrix=(np.vstack([patch['matrix'],[0,0,1]])@inv_motion)[:2].astype(np.float32)
   fake=patch['fake'];size=fake.shape[0]
   # Work only inside the projected face ROI; tracking remains 960px while
   # mask blur and colour conversion no longer scan the whole video per face.
   inverse=cv2.invertAffineTransform(matrix)
   corners=np.float32([[0,0],[size,0],[size,size],[0,size]])@inverse[:,:2].T+inverse[:,2]
   x0,y0=np.maximum(0,np.floor(corners.min(0)).astype(int)-3)
   x1,y1=np.minimum([w,h],np.ceil(corners.max(0)).astype(int)+3)
   if x1<=x0 or y1<=y0:continue
   rw,rh=int(x1-x0),int(y1-y0);local=matrix.copy();local[:,2]+=matrix[:,:2]@np.float32([x0,y0])
   # DLC paste-back on black yields premultiplied colour. Convert to RGBA
   # for the host compositor without changing the upstream blend kernel.
   premul=_fast_paste_back(np.zeros((rh,rw,3),np.uint8),fake,fake,local)
   alpha=cv2.warpAffine(_get_soft_alpha(size),cv2.invertAffineTransform(local),(rw,rh),flags=cv2.INTER_LINEAR)
   rgb=cv2.cvtColor(premul,cv2.COLOR_BGR2RGB).astype(np.float32)*255/np.maximum(alpha[:,:,None],1)
   region=np.zeros((rh,rw),np.uint8)
   poly=np.rint(pts[oval]*[w,h]-[x0,y0]).astype(np.int32)
   cv2.fillConvexPoly(region,cv2.convexHull(poly),255)
   feather=float(np.clip(req.get('swapFeather',35),0,100))
   sigma=max(1.,face_width*(.006+feather*.00022))
   region=cv2.GaussianBlur(region,(0,0),sigma)
   brow=float(np.mean(pts[[70,63,105,66,107,336,296,334,293,300],1]))*h
   forehead=np.clip((np.arange(y0,y1)[:,None]-(brow-face_width*.10))/max(face_width*.11,1),0,1)
   alpha=(np.minimum(alpha,region)*forehead*freshness).astype(np.uint8)
   target=output[y0:y1,x0:x1];use=alpha>target[:,:,3]
   target[use,:3]=np.clip(rgb[use],0,255).astype(np.uint8);target[use,3]=alpha[use]
   info['swapFaces']+=1;info['swapState']='rendered'
  return output,info
 def close(self):
  with self.cv:self.closed=True;self.pending=None;self.cv.notify()
  self.thread.join(timeout=10)
