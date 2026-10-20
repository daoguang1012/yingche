"""Local face analysis worker. One request/response at a time, no network access.
Native frames use bounded raw RGBA; the browser bridge uses JSON. No frame queue.
"""
import base64
import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np
import mediapipe as mp

OVAL = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
LEFT_EYE = [33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246]
RIGHT_EYE = [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398]
LIPS = [61,146,91,181,84,17,314,405,321,375,291,409,270,269,267,0,37,39,40,185]
INNER = [78,95,88,178,87,14,317,402,318,324,308,415,310,311,312,13,82,81,80,191]
BROWS = [[70,63,105,66,107,55,65,52,53,46], [336,296,334,293,300,276,283,282,295,285]]

def write(obj):
    sys.stdout.write(json.dumps(obj, separators=(',', ':')) + '\n')
    sys.stdout.flush()

def analyze(image, detector, previous, reset, locator=None, provided=None, landmarks_only=False, stability=None, states=None, now=0., paused=False):
    h, w = image.shape[:2]
    if provided is not None:
        landmarks = provided
    else:
        regions = [(0, 0, w, h)]
        if locator is not None:
            detection_scale=min(1.,640/max(w,h))
            dw,dh=round(w*detection_scale),round(h*detection_scale)
            locator.setInputSize((dw,dh))
            small=cv2.resize(image,(dw,dh)) if detection_scale<1 else image
            _, boxes = locator.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
            if boxes is not None:boxes[:,:14]/=detection_scale
            regions = []
            if boxes is not None:
                for box in sorted(boxes, key=lambda b: float(b[-1]), reverse=True)[:4]:
                    x, y, bw, bh = box[:4]
                    size = max(float(bw), float(bh)) * 1.8
                    cx, cy = float(x+bw/2), float(y+bh/2)
                    x0, y0 = max(0, int(cx-size/2)), max(0, int(cy-size/2))
                    x1, y1 = min(w, int(cx+size/2)), min(h, int(cy+size/2))
                    if x1-x0 > 20 and y1-y0 > 20: regions.append((x0,y0,x1,y1))
        landmarks = []
        for x0,y0,x1,y1 in regions:
            crop = np.ascontiguousarray(image[y0:y1,x0:x1])
            result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop))
            for face in result.face_landmarks:
                pts = np.array([((p.x*(x1-x0)+x0)/w, (p.y*(y1-y0)+y0)/h) for p in face], np.float32)
                if not any(np.linalg.norm(pts[1]-old[1]) < .04 for old in landmarks):
                    landmarks.append(pts)
    if landmarks_only:return landmarks
    faces, used = [], set()
    for pts in landmarks[:4]:
        if not np.isfinite(pts).all():
            continue
        center = pts[1]
        best, distance = None, .12
        if not reset:
            for i, old in enumerate(previous):
                if i not in used:
                    d = float(np.linalg.norm(old[1] - center))
                    if d < distance: best, distance = i, d
        if best is not None:
            # Smooth only tiny jitter. Fast movement follows the current frame.
            old = previous[best]
            delta = float(np.mean(np.linalg.norm(old - pts, axis=1)))
            alpha = .55 if delta < .004 else (.8 if delta < .014 else 1.)
            pts = old * (1 - alpha) + pts * alpha
            used.add(best)
        faces.append(pts)
    # Landmarks stay at full analysis resolution; soft colour masks need fewer pixels.
    mask_scale=min(1.,512/max(w,h));w,h=max(2,round(w*mask_scale)),max(2,round(h*mask_scale))
    mask = np.zeros((h, w, 3), np.uint8)
    ycc=cv2.cvtColor(cv2.resize(image,(w,h)),cv2.COLOR_RGB2YCrCb) if stability is not None else None
    packed = []
    def poly(channel, pts, ids, color):
        points = np.rint(pts[ids] * [w, h]).astype(np.int32)
        cv2.fillPoly(channel, [points], color, lineType=cv2.LINE_AA)
    for index,pts in enumerate(faces[:4]):
        skin = np.zeros((h,w),np.uint8)
        lip = np.zeros_like(skin)
        cheek = np.zeros_like(skin)
        poly(skin,pts,OVAL,255)
        protection = np.zeros_like(skin)
        for ids in [LEFT_EYE,RIGHT_EYE,LIPS]+BROWS:
            poly(protection,pts,ids,255)
        face_width = max(10., float(np.linalg.norm((pts[234]-pts[454])*[w,h])))
        dilation = max(3, int(face_width * .018) | 1)
        protection = cv2.dilate(protection,np.ones((dilation,dilation),np.uint8))
        skin = cv2.subtract(skin,protection)
        poly(lip,pts,LIPS,255)
        poly(lip,pts,INNER,0)
        for indices in [[50,101,205],[280,330,425]]:
            p = np.mean(pts[indices],axis=0)*[w,h]
            cv2.ellipse(cheek,tuple(p.astype(int)),(max(2,int(face_width*.13)),max(2,int(face_width*.07))),0,0,360,220,-1)
        sigma = max(1.2, face_width*.018)
        skin = cv2.GaussianBlur(skin,(0,0),sigma)
        lip = cv2.GaussianBlur(lip,(0,0),max(.6,sigma*.35))
        cheek = cv2.GaussianBlur(cheek,(0,0),sigma*1.5)
        if stability is not None:
            skin,lip,cheek,_=stability.refine(ycc,pts,skin,lip,cheek,states[index],now,paused)
        mask[:,:,0] = np.maximum(mask[:,:,0],skin)
        mask[:,:,1] = np.maximum(mask[:,:,1],lip)
        mask[:,:,2] = np.maximum(mask[:,:,2],cheek)
        # 8 pairs per face, fixed-size uniform packing.
        points = [np.mean(pts[LEFT_EYE],axis=0),np.mean(pts[RIGHT_EYE],axis=0),
                  pts[234],pts[454],pts[152],pts[1],pts[98],pts[327]]
        packed.append([[float(v) for v in p] for p in points])
    ok, encoded = cv2.imencode('.png',cv2.cvtColor(mask,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_PNG_COMPRESSION,1])
    if not ok: raise RuntimeError('Cannot encode face mask')
    return packed,base64.b64encode(encoded).decode('ascii'),faces

def decode_image(req,max_bytes=8_000_000):
    if 'rgba' in req or '_raw_rgba' in req:
        w,h=int(req['width']),int(req['height'])
        raw=req['_raw_rgba'] if '_raw_rgba' in req else base64.b64decode(req['rgba'],validate=True)
        if w<=0 or h<=0 or w*h>1_000_000 or len(raw)!=w*h*4:
            raise ValueError('Invalid raw analysis frame')
        return np.ascontiguousarray(np.frombuffer(raw,np.uint8).reshape(h,w,4)[:,:,:3])
    raw=base64.b64decode(req['png'],validate=True)
    if len(raw)>max_bytes:raise ValueError('Image too large')
    bgr=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
    if bgr is None or bgr.shape[0]*bgr.shape[1]>20_000_000:raise ValueError('Invalid image')
    return cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)

class FaceProcessor:
    def __init__(self, model):
        cv2.setNumThreads(2)
        self.model=Path(model)
        options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_buffer=self.model.read_bytes()),running_mode=mp.tasks.vision.RunningMode.IMAGE,num_faces=4,min_face_detection_confidence=.45,min_face_presence_confidence=.45)
        self.detector=mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self.locator=cv2.FaceDetectorYN.create('onnx',np.frombuffer(self.model.with_name('face_detection_yunet_2023mar.onnx').read_bytes(),np.uint8),np.empty(0,np.uint8),(640,360),.65,.3,5000)
        from face_tracking import FastFaceTracker
        self.tracker=FastFaceTracker(self.model.read_bytes(),lambda image:analyze(image,self.detector,[],True,self.locator,landmarks_only=True))
        self.previous=[];self.generation=-1;self.last_thumb=None;self.swapper=None;self.swap_async=None;self.source_ready=False
        from beauty_stability import BeautyStability
        self.stability=BeautyStability()

    def set_source(self, image):
        self.source_ready=False
        if self.swapper is None:
            from swap_engine import SwapEngine,AsyncSwap
            self.swapper=SwapEngine(self.model.parent)
            self.swap_async=AsyncSwap(self.swapper)
        self.swap_async.reset()
        result=self.swapper.set_source(image,self.locator)
        self.source_ready=True
        return {'sourceReady':True,**result}

    def process(self, req):
        start=time.perf_counter()
        if req.get('action')=='source':
            if req.get('path'):
                data=Path(req['path']).read_bytes()
                if len(data)>30_000_000:raise ValueError('源照片文件太大')
                image=decode_image({'png':base64.b64encode(data).decode()},max_bytes=30_000_000)
            else:image=decode_image(req)
            return {'id':req.get('id'),**self.set_source(image)}
        if req.get('action')=='clear-source':
            self.source_ready=False
            if self.swap_async:self.swap_async.reset()
            if self.swapper:self.swapper.clear_source()
            return {'id':req.get('id'),'sourceReady':False,'cleared':True}
        image=decode_image(req)
        if image.shape[0]*image.shape[1]>1_000_000:raise ValueError('Analysis frame too large')
        thumb=cv2.resize(image,(32,18)).astype(np.float32)
        cut=self.last_thumb is not None and np.mean(np.abs(thumb-self.last_thumb))>35
        generation=req.get('generation',0)
        stream_generation=(req.get('streamId','native'),generation)
        sample_time=float(req.get('sampleTime',time.monotonic()*1000))/1000.
        reset=stream_generation!=self.generation or cut
        if reset:self.stability.reset()
        if reset and self.swap_async:self.swap_async.reset()
        self.previous,motion=self.tracker.update(image,sample_time,reset)
        stable=bool(req.get('stableBeauty'))
        points,mask,self.previous=analyze(image,self.detector,[],True,provided=self.previous,
            stability=self.stability if stable else None,states=self.tracker.states,now=sample_time,paused=req.get('paused',False))
        self.stability.retain(self.tracker.ids)
        self.generation=stream_generation;self.last_thumb=thumb
        result={'id':req.get('id',0),'generation':generation,'pts':req.get('pts',0),'faces':points,'mask':mask,'motion':motion,'sampleTime':req.get('sampleTime',0),'trackingMode':self.tracker.mode,'flowQuality':round(self.tracker.flow_quality,3),'trackIds':self.tracker.ids}
        result['sceneCut']=bool(cut)
        result['faceSignals']=[{'flowQuality':s.get('flowQuality'),'confirmationAgeMs':round(s['confirmationAge']*1000,1)} for s in self.tracker.states]
        result['effectWeights']=[self.stability.history.get(s['id'],{}).get('strength',0.) for s in self.tracker.states] if stable else [1.]*len(points)
        if req.get('swapEnabled') and self.source_ready:
            self.swap_async.submit(image,self.previous,self.tracker.ids,req)
            rgba,info=self.swap_async.compose(image,self.previous,self.tracker.ids,req,OVAL)
            result.update(info)
            if info['swapFaces']:
                ok,png=cv2.imencode('.png',cv2.cvtColor(rgba,cv2.COLOR_RGBA2BGRA),[cv2.IMWRITE_PNG_COMPRESSION,1])
                if ok:result['swap']=base64.b64encode(png).decode()
        elif self.swap_async:
            self.swap_async.reset()
        result['ms']=round((time.perf_counter()-start)*1000,2)
        return result

    def close(self):
        if self.swap_async:self.swap_async.close()
        self.tracker.close();self.detector.close()

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--bridge':
        from bridge_server import run
        return run(Path(sys.argv[2]),Path(sys.argv[3]))
    processor=FaceProcessor(sys.argv[1]);write({'ready':True})
    stream=sys.stdin.buffer
    while line:=stream.readline(12_000_001):
        req={}
        try:
            if len(line)>12_000_000:raise ValueError('Request too large')
            req=json.loads(line)
            if 'rawBytes' in req:
                size=int(req['rawBytes']);w=int(req.get('width',0));h=int(req.get('height',0))
                if not 0<size<=4_000_000 or w<=0 or h<=0 or size!=w*h*4:raise ValueError('Invalid raw frame length')
                raw=stream.read(size)
                if len(raw)!=size:break
                req['_raw_rgba']=raw
            write(processor.process(req))
        except Exception as exc:
            processor.previous=[]
            write({'id':req.get('id',0),'generation':req.get('generation',-1),'error':str(exc),'sourceError':req.get('action')=='source'})
    processor.close()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        write({'fatal':str(exc)});sys.exit(1)
