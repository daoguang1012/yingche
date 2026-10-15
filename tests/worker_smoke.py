import subprocess,json,base64,sys,time
from pathlib import Path
import cv2,numpy as np
root=Path(__file__).resolve().parents[1]
image=np.zeros((360,640,3),np.uint8)
ok,png=cv2.imencode('.png',image)
payload={'id':1,'generation':2,'pts':4.,'png':base64.b64encode(png).decode()}
p=subprocess.Popen([sys.executable,'-u',str(root/'tools/face_worker.py'),str(root/'models/face_landmarker.task')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
out,err=p.communicate(json.dumps(payload)+'\n',timeout=60)
print(err[-1200:])
lines=[json.loads(x) for x in out.splitlines() if x.startswith('{')]
assert lines[0].get('ready'),lines
assert lines[1]['faces']==[] and lines[1]['generation']==2,lines[1].keys()
assert p.returncode==0
print('WORKER_NO_FACE_OK')
