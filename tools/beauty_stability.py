"""Motion-aligned masks and observed chroma; no invented detector confidence.

Color gating is a conservative heuristic, not semantic hair/occlusion segmentation.
History is discarded on cuts/generation changes, identity changes or a >160ms gap.
"""
import cv2
import numpy as np

class BeautyStability:
    def __init__(self):self.history={}
    def reset(self):self.history.clear()

    def refine(self,ycc,points,skin,lip,cheek,state,now,paused=False):
        key=state['id'];old=self.history.get(key);h,w=skin.shape
        if old and (now-old['time']>.16 or old['skin'].shape!=skin.shape):old=None
        dt=max(.001,min(.1,now-old['time'])) if old else .033
        # Stay inside the face contour; protect fine edge detail and very dark hair.
        width=max(10.,float(np.linalg.norm((points[234]-points[454])*[w,h])))
        erode=max(3,int(width*.025)|1)
        skin=cv2.erode(skin,np.ones((erode,erode),np.uint8))
        x,y,bw,bh=cv2.boundingRect(skin)
        if bw==0 or bh==0:
            self.history.pop(key,None)
            return np.zeros_like(skin),np.zeros_like(lip),np.zeros_like(cheek),0.
        roi=ycc[y:y+bh,x:x+bw].astype(np.float32);support=skin[y:y+bh,x:x+bw]
        samples=roi[(support>160)&(roi[:,:,0]>25)]
        if len(samples)<20:
            self.history.pop(key,None)
            return np.zeros_like(skin),np.zeros_like(lip),np.zeros_like(cheek),0.
        center=np.median(samples[:,1:],axis=0)
        spread=np.maximum(9.,np.median(np.abs(samples[:,1:]-center),axis=0)*2.5)
        quality=state.get('flowQuality');age=state.get('confirmationAge',0.)
        if old and quality is not None and quality>.65 and age<.05:
            alpha=1.-np.exp(-dt/.25)
            # Abrupt illumination change follows current color; never drag old skin tone.
            if np.linalg.norm(center-old['color'])<18:center=old['color']*(1-alpha)+center*alpha
        # Restrict color statistics to the face ROI, not the whole frame per person.
        distance=np.max(np.abs(roi[:,:,1:]-center)/spread,axis=2)
        gate=np.zeros((h,w),np.float32)
        gate[y:y+bh,x:x+bw]=np.clip((2.8-distance)/1.3,0.,1.)*np.clip((roi[:,:,0]-18)/25.,0.,1.)
        current=skin*gate
        if old and quality is not None and quality>.65:
            ids=[1,33,263,234,454,152]
            mat,_=cv2.estimateAffinePartial2D((old['points'][ids]*[w,h]).astype(np.float32),(points[ids]*[w,h]).astype(np.float32),method=cv2.LMEDS)
            if mat is not None and np.isfinite(mat).all():
                moved=cv2.warpAffine(old['skin'],mat,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
                # A current-frame support bound prevents history leaking onto new objects.
                current=np.minimum(current*.75+moved*.25,current*1.15)
        target=float(np.clip(1.-age/.12,0.,1.))
        if quality is not None:target*=float(np.clip((quality-.25)/.5,0.,1.))
        strength=target if paused else (old['strength'] if old else 0.)
        tau=.12 if target>strength else .035
        strength+=float(1.-np.exp(-dt/tau))*(target-strength)
        self.history[key]={'time':now,'points':points.copy(),'skin':current,'color':center,'strength':strength}
        return (np.clip(current*strength,0,255).astype(np.uint8),
                (lip*strength).astype(np.uint8),(cheek*strength*gate).astype(np.uint8),strength)

    def retain(self,ids):self.history={key:value for key,value in self.history.items() if key in ids}
