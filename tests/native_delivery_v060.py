"""Installed launcher, Unicode CLI, resume, empty media, closing two windows."""
import json,subprocess,time,psutil,shutil,ctypes
from pathlib import Path
from pywinauto import Application
import control
root=Path(__file__).resolve().parents[1];out=root/'work/v060'/('delivery-'+str(time.time_ns()));out.mkdir()
control.qa=out/'qa';control.qa.mkdir()
clip=out/'中文名 实播.mp4';shutil.copyfile(root/'work/v04/intel-fixtures/head-pose-face-detection-female.mp4',clip)
checks=[];native=None;report={}
def start():
    global native
    for name in ['command.json','state.json']:(control.qa/name).unlink(missing_ok=True)
    launch=subprocess.Popen([str(root/'Yingche.exe'),'--control-dir',str(control.qa),str(clip)],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
    launch.wait(timeout=5);assert launch.returncode==0
    control.wait(lambda s:s.get('loaded') and s.get('workerReady') and s.get('gpupixelReady'),40)
    found=[]
    for p in psutil.process_iter(['pid','cmdline','exe']):
        if str(control.qa) in (p.info['cmdline'] or []) and Path(p.info['exe']).name=='BeautyPlayerV060.exe':found.append(p)
    assert len(found)==1;native=found[0]
def close():
    global native
    if native and native.is_running():
        children=native.children(recursive=True);control.send('quit');native.wait(timeout=15)
        _,alive=psutil.wait_procs(children,timeout=4);assert not alive
    native=None
def record(name):checks.append(name);print('PASS',name,flush=True)
try:
    start();assert control.state()['version']=='0.6.0';record('installed launcher opens version 0.6.0 with Unicode filename')
    control.send('pause',value=True);control.send('seek',seconds=9.5)
    control.wait(lambda s:abs(s.get('position',0)-9.5)<.02)
    control.send('beauty',values={'smooth':28,'white':16});time.sleep(.25);close();start()
    control.wait(lambda s:9.4<=s.get('position',0)<=11 and s['beauty']['smooth']==28);control.send('pause',value=True)
    record('installed launcher restores position and per-video picture')
    empty=out/'unreadable-media.mp4';empty.write_bytes(b'')
    control.send('load',path=str(empty));control.wait(lambda s:s.get('mediaKey')=='' and s.get('pictureScope')==2)
    record('failed media identification uses temporary picture scope')
    control.send('load',path=str(clip));control.wait(lambda s:s.get('loaded'));control.send('pause',value=True)
    if len(control.state()['screens'])>=2:
        control.send('separate');control.wait(lambda s:s.get('separated'))
        control.send('pause',value=False);time.sleep(.4)
        children=native.children(recursive=True);app=Application(backend='uia').connect(process=native.pid)
        window=app.window(title_re='中文名 实播.*');hwnd=window.handle
        ctypes.windll.user32.PostMessageW(hwnd,0x0010,0,0)
        native.wait(timeout=15);_,alive=psutil.wait_procs(children,timeout=4);assert not alive
        record('closing separated video window ends owned worker and both windows');native=None
    report={'passed':True,'checks':checks}
finally:
    close();(out/'delivery-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'work/v060/latest-delivery.txt').write_text(str(out),encoding='utf-8')
