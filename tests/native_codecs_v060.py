"""Run existing codec assertions in isolated data; synthetic codec fixtures only."""
import os,runpy,subprocess,time,json
from pathlib import Path
import control
root=Path(__file__).resolve().parents[1];out=root/'work/v060'/('codecs-'+str(time.time_ns()));out.mkdir()
control.qa=out/'qa';control.qa.mkdir();os.environ['YINGCHE_CODEC_REPORT']=str(out/'codecs.json')
log=(out/'player.log').open('w',encoding='utf-8')
proc=subprocess.Popen([str(root/'app/BeautyPlayerV060.exe'),'--control-dir',str(control.qa)],cwd=root,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
try:
    control.wait(lambda s:s.get('workerReady') and s.get('gpupixelReady'),40)
    runpy.run_path(str(root/'tests/codec_acceptance.py'))
finally:
    control.send('quit');proc.wait(timeout=15);log.close()
    (root/'work/v060/latest-codecs.txt').write_text(str(out),encoding='utf-8')
