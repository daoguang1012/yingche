from pathlib import Path
import cv2,numpy as np,subprocess,wave
root=Path(__file__).resolve().parents[1]
work=root/'work'
portrait=cv2.imread(str(work/'portrait.jpg'))
assert portrait is not None
h,w=portrait.shape[:2]
portrait=cv2.resize(portrait,(int(w*680/h),680))
writer=cv2.VideoWriter(str(work/'portrait-motion.avi'),cv2.VideoWriter_fourcc(*'MJPG'),30,(1280,720))
assert writer.isOpened()
for frame_no in range(900):
    frame=np.full((720,1280,3),(35,31,27),np.uint8)
    if frame_no<600:
        x=440+int(70*np.sin(frame_no/90))
        y=20
        frame[y:y+portrait.shape[0],x:x+portrait.shape[1]]=portrait
        if 300<frame_no<400:
            frame[330:440,x+60:x+180]=35
    cv2.putText(frame,'BEAUTY PLAYER / PUBLIC TEST SAMPLE',(35,50),cv2.FONT_HERSHEY_SIMPLEX,.7,(145,190,175),1,cv2.LINE_AA)
    cv2.putText(frame,f'{frame_no/30:05.1f}s / {frame_no:04}',(35,670),cv2.FONT_HERSHEY_SIMPLEX,.8,(240,240,240),2)
    writer.write(frame)
writer.release()
sample_rate=48000
audio=np.zeros(sample_rate*30,np.float32)
for second in range(30):
    n=int(sample_rate*.1)
    t=np.arange(n)/sample_rate
    audio[second*sample_rate:second*sample_rate+n]=.13*np.sin(2*np.pi*440*t)*np.sin(np.pi*np.arange(n)/n)
with wave.open(str(work/'ticks.wav'),'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(sample_rate);wav.writeframes((audio*32767).astype(np.int16).tobytes())
ffmpeg=str(root/'tools/ffmpeg/ffmpeg.exe')
cmd=[ffmpeg,'-hide_banner','-y','-i',str(work/'portrait-motion.avi'),'-i',str(work/'ticks.wav'),'-c:v','h264_nvenc','-b:v','5M','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(work/'portrait-motion.mp4')]
p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
print(p.stderr[-1600:]);assert p.returncode==0
for ext in ['mkv','mov','ts']:
    p=subprocess.run([ffmpeg,'-hide_banner','-y','-i',str(work/'portrait-motion.mp4'),'-c','copy',str(work/f'portrait-motion.{ext}')],capture_output=True,text=True,timeout=60)
    assert p.returncode==0,p.stderr
(work/'sample.srt').write_text('1\n00:00:01,000 --> 00:00:06,000\n映澈 字幕测试 / Subtitle test\n\n2\n00:00:08,000 --> 00:00:15,000\n时间线、倍速与声音同步测试\n',encoding='utf-8')
print('SAMPLES_OK')
