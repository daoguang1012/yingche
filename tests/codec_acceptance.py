import json,time,os
from control import *
reports=[]
for name in ['h264-1080p60.mp4','hevc.mkv','av1.mkv','vp9.webm','legacy.wmv','legacy.flv','legacy.mpg']:
 send('load',path=str(root/'work'/name))
 s=wait(lambda s:s.get('loaded') and s.get('duration',0)>7)
 send('pause',value=True);send('seek',seconds=1)
 s=wait(lambda s:abs(s.get('position',0)-1)<.2 and s.get('faces',0)>0)
 send('pause',value=False)
 time.sleep(3)
 s=state()
 assert s['position']>3.5,(name,s['position'])
 item={'file':name,'hwdec':s['hwdec'],'faces':s['faces'],'analysisMs':s['analysisMs'],'drops':s['drops'],'decoderDrops':s['decoderDrops'],'avsync':s['avsync'],'tracks':[{'type':x.get('type'),'codec':x.get('codec')} for x in s['tracks']]}
 reports.append(item);print(json.dumps(item),flush=True)
send('pause',value=True)
Path(os.environ.get('YINGCHE_CODEC_REPORT',str(root/'work/codec-acceptance.json'))).write_text(json.dumps(reports,indent=2),encoding='utf-8')
print('CODEC_ACCEPTANCE_OK')
