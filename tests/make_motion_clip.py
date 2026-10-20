"""Generates hard-motion test clips with exact per-frame ground truth (no detector noise in the reference).

A still head-and-shoulders crop of the public-domain portrait already used by the fixtures is moved over a
textured, counter-scrolling background with known transforms: still, fast 1 Hz swings (~2500 px/s peaks),
abrupt direction reversals every 0.4 s, zoom with bob, ±15° tilt, 12 Hz shake, still. Audio carries a 440 Hz
bed with a 1 kHz beep at every segment change. Outputs work/motion/motion-{fps}.mp4 + motion-{fps}.json
(normalised left/right eye centres per frame).
Usage: python tests/make_motion_clip.py [fps ...]
"""
import json,subprocess,sys
from pathlib import Path
import cv2,numpy as np,mediapipe as mp

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/motion';OUT.mkdir(parents=True,exist_ok=True)
FFMPEG=str(ROOT/'tools/ffmpeg/ffmpeg.exe');W,H,SECONDS=1920,1080,20.
LEFT_EYE=[33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246]
RIGHT_EYE=[362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398]
SEGMENTS=[0,2,6,9,12,15,18,20]

def actor():
    detector=mp.tasks.vision.FaceLandmarker.create_from_options(mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT/'models/face_landmarker.task')),running_mode=mp.tasks.vision.RunningMode.IMAGE,num_faces=1))
    cap=cv2.VideoCapture(str(ROOT/'work/portrait-motion.mp4'));best=None
    for ms in range(0,20000,500):
        cap.set(cv2.CAP_PROP_POS_MSEC,ms);ok,frame=cap.read()
        if not ok:break
        found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))).face_landmarks
        if found:
            pts=np.array([(p.x,p.y) for p in found[0]])*[frame.shape[1],frame.shape[0]]
            margin=min(pts[:,0].min(),pts[:,1].min(),frame.shape[1]-pts[:,0].max(),frame.shape[0]-pts[:,1].max())
            if best is None or margin>best[0]:best=(margin,frame,pts)
    assert best,'no usable portrait still'
    _,frame,pts=best
    eyes=np.array([pts[LEFT_EYE].mean(0),pts[RIGHT_EYE].mean(0)]);center=eyes.mean(0);d=np.linalg.norm(eyes[0]-eyes[1])
    # Head-and-shoulders crop around the face, softly feathered so no hard rectangle edge is tracked.
    x0,y0=int(max(0,center[0]-d*3.2)),int(max(0,center[1]-d*3.4));x1,y1=int(min(frame.shape[1],center[0]+d*3.2)),int(min(frame.shape[0],center[1]+d*4.6))
    crop=frame[y0:y1,x0:x1].copy();alpha=np.zeros(crop.shape[:2],np.float32)
    cv2.ellipse(alpha,(crop.shape[1]//2,int(crop.shape[0]*.47)),(int(crop.shape[1]*.46),int(crop.shape[0]*.5)),0,0,360,1.,-1)
    alpha=cv2.GaussianBlur(alpha,(0,0),d*.35)
    return crop,alpha,eyes-[x0,y0],d

def pose(t):
    """Returns (dx, dy, scale, angle_deg) of the actor centre relative to frame centre at time t."""
    if t<2:return 0,0,1,0
    if t<6:return 420*np.sin(2*np.pi*(t-2)),0,1,0
    if t<9:
        u=(t-6)/.4;k=int(u);f=u-k;tri=(f if k%2==0 else 1-f)*2-1   # reversal every 0.4 s
        return 300*tri,40*np.sin(2*np.pi*(t-6)*.7),1,0
    if t<12:return 0,60*np.sin(2*np.pi*(t-9)*1.2),1.05+.25*np.sin(2*np.pi*(t-9)/3),0
    if t<15:return 150*np.sin(2*np.pi*(t-12)*.5),0,1,15*np.sin(2*np.pi*(t-12)*.8)
    if t<18:
        rng=np.random.default_rng(int(t*12));return float(rng.uniform(-60,60)),float(rng.uniform(-40,40)),1,float(rng.uniform(-4,4))
    return 0,0,1,0

def make(fps):
    crop,alpha,eyes,d=actor();ch,cw=crop.shape[:2]
    target=W*.13/d   # inter-eye distance ~13% of width, a typical close-up
    rng=np.random.default_rng(7);texture=cv2.GaussianBlur(rng.integers(40,200,(H,W*2,3),dtype=np.uint8),(0,0),9)
    texture=cv2.addWeighted(texture,.6,np.full_like(texture,(70,90,110)),.4,0)
    frames=int(SECONDS*fps);truth=[]
    audio=f"sine=f=440:d={SECONDS}:sample_rate=48000[a];sine=f=1000:d={SECONDS}:sample_rate=48000,volume='if(lt(mod(t\\,1000)\\,0)\\,0\\,"+'+'.join(f'between(t\\,{s}\\,{s}+0.08)' for s in SEGMENTS)+")':eval=frame[b];[a]volume=0.15[a2];[a2][b]amix=inputs=2[out]"
    cmd=[FFMPEG,'-y','-loglevel','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-filter_complex',audio,'-map','0:v','-map','[out]',
         '-c:v','h264_nvenc','-preset','p6','-rc','vbr','-cq','18','-b:v','0','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-shortest',str(OUT/f'motion-{fps}.mp4')]
    enc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for i in range(frames):
        t=i/fps;dx,dy,s,a=pose(t);scale=target*s
        M=cv2.getRotationMatrix2D((cw/2,ch/2),a,scale);M[:,2]+=[W/2+dx-cw/2,H/2+dy-ch/2]
        shift=int(t*60)%W;bg=texture[:,shift:shift+W].copy()
        warped=cv2.warpAffine(crop,M,(W,H),flags=cv2.INTER_LINEAR);mask=cv2.warpAffine(alpha,M,(W,H),flags=cv2.INTER_LINEAR)[:,:,None]
        frame=(bg*(1-mask)+warped*mask).astype(np.uint8)
        e=eyes@M[:,:2].T+M[:,2];truth.append((e/[W,H]).round(6).tolist())
        enc.stdin.write(frame.tobytes())
    enc.stdin.close();assert enc.wait()==0
    (OUT/f'motion-{fps}.json').write_text(json.dumps({'fps':fps,'width':W,'height':H,'segments':SEGMENTS,'eyes':truth}),encoding='utf-8')
    print('wrote',OUT/f'motion-{fps}.mp4',frames,'frames',flush=True)

def make_cuts(fps=30,seconds=12.,every=1.5):
    """Hard cuts between two different scenes every 1.5 s, both with fast swings; truth = cut frame indices."""
    crop,alpha,eyes,d=actor();ch,cw=crop.shape[:2];target=W*.13/d
    rng=np.random.default_rng(3)
    looks=[cv2.addWeighted(cv2.GaussianBlur(rng.integers(40,200,(H,W*2,3),dtype=np.uint8),(0,0),9),.6,np.full((H,W*2,3),c,np.uint8),.4,0) for c in [(70,90,110),(150,120,60)]]
    enc=subprocess.Popen([FFMPEG,'-y','-loglevel','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-c:v','h264_nvenc','-preset','p6','-rc','vbr','-cq','18','-b:v','0','-pix_fmt','yuv420p',str(OUT/f'cuts-{fps}.mp4')],stdin=subprocess.PIPE)
    cuts=[]
    for i in range(int(seconds*fps)):
        t=i/fps;scene=int(t//every)%2
        if i and int(t//every)!=int((i-1)/fps//every):cuts.append(i)
        dx=420*np.sin(2*np.pi*t);scale=target*(1. if scene==0 else 1.35);flip=scene==1
        src=cv2.flip(crop,1) if flip else crop;a=cv2.flip(alpha,1) if flip else alpha
        M=cv2.getRotationMatrix2D((cw/2,ch/2),0,scale);M[:,2]+=[W/2+dx-cw/2+(-250 if scene else 0),H/2-cw/2*0+(80 if scene else 0)-ch/2]
        shift=int(t*60)%W;bg=looks[scene][:,shift:shift+W].copy()
        mask=cv2.warpAffine(a,M,(W,H))[:,:,None];frame=(bg*(1-mask)+cv2.warpAffine(src,M,(W,H))*mask).astype(np.uint8)
        enc.stdin.write(frame.tobytes())
    enc.stdin.close();assert enc.wait()==0
    (OUT/f'cuts-{fps}.json').write_text(json.dumps({'fps':fps,'cuts':cuts}),encoding='utf-8');print('wrote cuts clip',cuts,flush=True)

if __name__=='__main__':
    if 'cuts' in sys.argv:make_cuts()
    else:
        for fps in [int(a) for a in sys.argv[1:]] or [30,60]:make(fps)
