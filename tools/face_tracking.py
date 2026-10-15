"""Video landmarks with measured optical-flow continuation, never frozen-face hold."""
import cv2
import numpy as np
import mediapipe as mp

ANCHORS = [1,4,6,10,33,54,67,93,127,132,133,145,152,159,172,197,234,263,284,297,323,356,361,362,374,386,389,397,454,61,291,98,327,168,2,50,280]

class FastFaceTracker:
    def __init__(self, model_bytes, fallback):
        self.model_bytes=model_bytes; self.fallback=fallback; self.detector=None;self.next_id=1;self.ids=[]
        self.reset()

    def reset(self):
        # Keep model graphs warm across seeks. Flush VIDEO state before the next image.
        self.flush_pending=self.detector is not None
        if self.detector is None:
            options=mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_buffer=self.model_bytes),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=4,
                min_face_detection_confidence=.45,min_face_presence_confidence=.45,min_tracking_confidence=.45)
            self.detector=mp.tasks.vision.FaceLandmarker.create_from_options(options)
            self.stamp=-1
        self.gray=None;self.states=[];self.ids=[];self.last_detect=-1e9;self.last_fallback=-1e9;self.last_time=None
        self.mode='detect';self.flow_quality=0.;self.flow_qualities=[]

    @staticmethod
    def center(points):return (points[234]+points[454])*.5

    def _flow(self,gray):
        self.flow_qualities=[0.]*len(self.states)
        if self.gray is None or self.gray.shape!=gray.shape:return []
        h,w=gray.shape;results=[];qualities=[]
        for index,state in enumerate(self.states):
            points=state['points'];old=np.ascontiguousarray((points[ANCHORS]*[w,h]).astype(np.float32).reshape(-1,1,2))
            new,ok,error=cv2.calcOpticalFlowPyrLK(self.gray,gray,old,None,winSize=(25,25),maxLevel=4,
                criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,20,.01))
            if new is None:results.append(None);continue
            back,back_ok,_=cv2.calcOpticalFlowPyrLK(gray,self.gray,new,None,winSize=(25,25),maxLevel=4,
                criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,20,.01))
            if back is None:results.append(None);continue
            valid=(ok.ravel()>0)&(back_ok.ravel()>0)&(error.ravel()<32)&(np.linalg.norm(back-old,axis=2).ravel()<1.5)
            fraction=float(valid.mean());qualities.append(fraction)
            if valid.sum()<10 or fraction<.45:results.append(None);continue
            mat,inliers=cv2.estimateAffinePartial2D(old[valid,0],new[valid,0],method=cv2.RANSAC,ransacReprojThreshold=2.,maxIters=100)
            if mat is None or inliers is None or float(inliers.mean())<.6:results.append(None);continue
            scale=float(np.hypot(mat[0,0],mat[1,0]))
            if not .75<scale<1.33:results.append(None);continue
            moved=((points*[w,h])@mat[:,:2].T+mat[:,2])/[w,h]
            if not np.isfinite(moved).all() or np.linalg.norm(self.center(moved)-self.center(points))>.3:results.append(None);continue
            results.append(moved.astype(np.float32))
            self.flow_qualities[index]=fraction*float(inliers.mean())
        self.flow_quality=min(qualities,default=0.)
        return results

    def update(self,image,now,reset=False):
        gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
        if reset or self.gray is not None and self.gray.shape!=gray.shape:self.reset()
        now=float(now);stamp=max(self.stamp+1,int(now*1000))
        if self.flush_pending:
            self.detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.zeros((64,64,3),np.uint8)),stamp)
            stamp+=1;self.flush_pending=False
        self.stamp=stamp
        flow=self._flow(gray);previous=self.states;states=[]
        need_detect=not previous or len(flow)!=len(previous) or any(p is None for p in flow) or now-self.last_detect>=.030 or any(now-s['confirmed']>=.09 for s in previous)
        if need_detect:
            result=self.detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(image)),stamp)
            detected=[np.array([(p.x,p.y) for p in f],np.float32) for f in result.face_landmarks]
            self.last_detect=now;self.mode='video'
            # Large-frame/small-face recovery; full detector is not repeated on every frame.
            changed_without_track=not previous and self.gray is not None and float(np.mean(cv2.absdiff(gray,self.gray)))>5.
            recovery_due=(not detected and changed_without_track) or (not detected and now-self.last_fallback>=.18) or (len(detected)<len(previous) and now-self.last_fallback>=.09)
            discovery_due=now-self.last_fallback>=.30 and len(detected)<4
            if recovery_due or discovery_due:
                recovered=self.fallback(image);self.last_fallback=now
                self.mode='video+reacquire' if detected else 'reacquire'
                for points in recovered:
                    if not any(np.linalg.norm(self.center(points)-self.center(other))<.10 for other in detected):
                        detected.append(points)
            used=set()
            for points in detected[:4]:
                if not np.isfinite(points).all():continue
                best=None;distance=max(.04,float(np.linalg.norm(points[234]-points[454]))*.75)
                for i,p in enumerate(flow):
                    if i in used:continue
                    if p is None:p=previous[i]['points']
                    d=float(np.linalg.norm(self.center(points)-self.center(p)))
                    if d<distance:best,distance=i,d
                confirmed=now
                if best is not None:
                    used.add(best)
                    # Only smooth residual landmark jitter after compensating real image motion.
                    delta=float(np.mean(np.linalg.norm(points-flow[best],axis=1))) if flow[best] is not None else 1.
                    face_width=float(np.linalg.norm(points[234]-points[454]))
                    # A full-frame landmark hiccup must not overpower strong pixel motion.
                    # Preserve the confirmation timestamp: unconfirmed continuation remains
                    # bounded to 120ms, then reacquisition or a real no-face result wins.
                    if flow[best] is not None and self.flow_quality>=.8 and delta>max(.006,face_width*.10) and now-previous[best]['confirmed']<=.12:
                        points=flow[best];confirmed=previous[best]['confirmed'];self.mode='flow-validated'
                    elif delta<.006:points=flow[best]*.35+points*.65
                states.append({'points':points,'confirmed':confirmed,'previous':best})
            for i,p in enumerate(flow):
                if i not in used and p is not None and now-previous[i]['confirmed']<=.12:
                    states.append({'points':p,'confirmed':previous[i]['confirmed'],'previous':i})
            states=states[:4]
        else:
            self.mode='flow'
            states=[{'points':p,'confirmed':previous[i]['confirmed'],'previous':i} for i,p in enumerate(flow)
                    if p is not None and now-previous[i]['confirmed']<=.12]
        dt=now-self.last_time if self.last_time is not None else 0
        motion=[]
        for state in states:
            index=state.pop('previous');state['id']=previous[index]['id'] if index is not None else self.next_id
            state['flowQuality']=self.flow_qualities[index] if index is not None and index<len(self.flow_qualities) else None
            state['confirmationAge']=max(0.,now-state['confirmed'])
            if index is None:self.next_id+=1
            velocity=np.zeros(2,np.float32)
            if index is not None and .003<=dt<=.12:
                measured=(self.center(state['points'])-self.center(previous[index]['points']))/dt
                if np.linalg.norm(measured)<3.:
                    velocity=.75*measured+.25*np.asarray(previous[index].get('velocity',[0.,0.]))
            state['velocity']=velocity.tolist();motion.append(velocity.tolist())
        self.states=states;self.ids=[s['id'] for s in states];self.gray=gray;self.last_time=now
        return [s['points'] for s in states],motion

    def close(self):
        if self.detector:self.detector.close();self.detector=None
