"""Real native UI lifecycle + isolated settings and same-frame pixel assertions.
Fixtures from Intel CC BY 4.0; blank/synthetic clip used only for no-face contracts.
"""
import ctypes, hashlib, json, os, shutil, subprocess, time, sys
from pathlib import Path
import cv2, numpy as np, psutil
from pywinauto import Application
import control

root=Path(__file__).resolve().parents[1];out=root/'work/v060'/('acceptance-'+str(time.time_ns()));out.mkdir(parents=True)
control.qa=out/'qa';control.qa.mkdir()
env=os.environ.copy()
for key,suffix in [('APPDATA','roaming'),('LOCALAPPDATA','local'),('TEMP','temp'),('TMP','temp')]:
    env[key]=str(out/suffix);Path(env[key]).mkdir(exist_ok=True)
legacy={'version':1,'beauty':{'smooth':190,'white':15},'positions':{},'lastDirectory':''}
(control.qa/'settings.json').write_text(json.dumps(legacy),encoding='utf-8');legacy_hash=hashlib.sha256((control.qa/'settings.json').read_bytes()).hexdigest()
fixtures=root/'work/v04/intel-fixtures'
for folder,name in [('one','head-pose-face-detection-female.mp4'),('two','head-pose-face-detection-female-and-male.mp4')]:
    (out/folder).mkdir();shutil.copyfile(fixtures/name,out/folder/'same-name.mp4')
a=out/'one/same-name.mp4';b=out/'two/same-name.mp4'
report={'checks':{},'physicalUnplug':'not tested','visualQuality':'review saved real-frame images separately','out':str(out)}
proc=None;log=None
def start():
    global proc,log
    log=(out/('player-'+str(time.time_ns())+'.log')).open('w',encoding='utf-8')
    # Clear opt-in commands; never replay old commands in a fresh process.
    for file in ['command.json','state.json']:
        path=control.qa/file
        if path.exists():path.unlink()
    proc=subprocess.Popen([str(root/'app/BeautyPlayerV060.exe'),'--control-dir',str(control.qa)],cwd=root,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    control.wait(lambda s:s.get('workerReady') and s.get('version')=='0.6.0',40)
def close():
    global proc
    if proc is None:return
    children=psutil.Process(proc.pid).children(recursive=True) if proc.poll() is None else []
    if proc.poll() is None:
        try:control.send('quit')
        except Exception:proc.terminate()
    proc.wait(timeout=15);log.close()
    gone,alive=psutil.wait_procs(children,timeout=4)
    assert not alive,[(p.pid,p.name()) for p in alive]
    assert proc.returncode==0,proc.returncode
    proc=None
def load(path,pts=35):
    control.send('load',path=str(path));control.wait(lambda s:s.get('loaded') and s.get('file')==str(path).replace('\\','/'))
    control.send('pause',value=True);control.send('seek',seconds=pts)
    return control.wait(lambda s:abs(s.get('position',0)-pts)<.01 and s.get('resultGeneration')==s.get('generation'),20)
def snap(name):
    path=out/(name+'.png');control.send('snapshot',path=str(path));return cv2.imread(str(path))
def check(name,value):
    assert value,name;report['checks'][name]=True
    s=control.state();report.setdefault('trace',[]).append({'check':name,**{k:s.get(k) for k in ['position','paused','speed','generation']}})
    print('PASS',name, 'pts',s.get('position'),flush=True)
try:
    start();check('legacy clamps safely, old config preserved',control.state()['beauty']['smooth']==65)
    s=load(a);key_a=s['mediaKey'];check('content identity created',len(key_a)==64)
    control.send('beauty',values={'smooth':33,'white':14,'detail':70,'sharp':8});time.sleep(.25)
    s=load(b);check('same filename, different content stays separate',s['mediaKey']!=key_a and s['beauty']['smooth']==65)
    control.send('beauty',values={'smooth':20,'white':6})
    moved=out/'moved.mp4';shutil.move(a,moved);a=moved
    s=load(a);check('move/rename restores own picture',s['mediaKey']==key_a and s['beauty']['smooth']==33)
    control.send('scope',value=2);control.send('beauty',values={'smooth':4});control.send('enabled',value=False)
    control.send('scope',value=0);check('temporary preview discarded',control.state()['beauty']['smooth']==33 and control.state()['enabled'])
    control.send('hold-original',value=True);original=snap('real-original');control.send('hold-original',value=False)
    time.sleep(.25);active=snap('real-natural');report['meanPixelChange']=float(np.abs(active.astype(float)-original).mean())
    check('beauty changes real face pixels',report['meanPixelChange']>.01)
    # Full frame off and held original must be identical for a paused frame.
    control.send('enabled',value=False);disabled=snap('real-disabled')
    check('hold original equals bypass',float(np.abs(original.astype(float)-disabled).max())==0)
    control.send('enabled',value=True);control.wait(lambda s:s.get('faces',0)>0);time.sleep(.25)
    control.send('compare',value=True);split=snap('real-split')
    check('split uses same original frame',float(np.abs(split[:,:split.shape[1]//2-2].astype(float)-original[:,:original.shape[1]//2-2]).max())==0)
    control.send('compare',value=False)
    control.send('beauty',values={k:0 for k in control.state()['beauty']});control.send('test-stall',ms=350)
    control.wait(lambda s:not s.get('beautyTransitionPending',True));zero=snap('real-zero-after-gui-delay')
    check('paused transition reaches exact zero after GUI delay',np.array_equal(zero,original))
    control.send('beauty',values={'smooth':33,'white':14,'detail':70,'sharp':8})
    # Drive the actual key event path and focus-loss event on only this test app.
    app=Application(backend='uia').connect(process=proc.pid);window=app.top_window();window.set_focus()
    hwnd=window.handle
    ctypes.windll.user32.PostMessageW(hwnd,0x100,ord('R'),0)
    control.wait(lambda s:s.get('originalPreview'))
    ctypes.windll.user32.PostMessageW(hwnd,0x101,ord('R'),0)
    control.wait(lambda s:not s.get('originalPreview'));check('R release restores',True)
    from pywinauto.keyboard import send_keys
    window.set_focus();send_keys('{r down}');control.wait(lambda s:s.get('originalPreview'))
    try:
        send_keys('{VK_SHIFT down}{r up}');control.wait(lambda s:not s.get('originalPreview'))
    finally:send_keys('{VK_SHIFT up}{r up}')
    check('R release with Shift restores',True)
    control.send('hold-original',value=True)
    # A native deactivation message exercises Qt's focus-loss path without touching other apps.
    ctypes.windll.user32.PostMessageW(hwnd,0x0006,0,0)
    control.wait(lambda s:not s.get('originalPreview'));check('focus loss clears hold',True)
    report['screens']=control.state()['screens']
    load(a)
    if len(report['screens'])>=2:
        for cycle in range(3):
            control.send('separate');s=control.wait(lambda s:s.get('separated') and s.get('fullscreen'))
            check('different attached displays '+str(cycle),s['displayScreen']!=s['controlsScreen'])
            report['separatedState']=s
            if cycle==0:
                control.send('pause',value=False);start_pos=control.state()['position']
                control.wait(lambda s:s.get('position',0)>start_pos+2.)
                display_window=app.window(title_re='.* — 映澈')
                display_window.capture_as_image().save(out/'physical-display-capture.png')
                control.send('pause',value=True)
            # Render on the actual current secondary screen, not a simulated viewport.
            image=snap('display-'+str(cycle));check('secondary renders nonblack '+str(cycle),float(image.mean())>10)
            control.send('controlshot',path=str(out/('controls-'+str(cycle)+'.png')))
            control.send('fullscreen');control.wait(lambda s:not s.get('fullscreen'));control.send('fullscreen')
            if cycle==0:control.send('close-controls')
            elif cycle==1:control.send('screen-loss-contract')
            else:control.send('separate')
            control.wait(lambda s:not s.get('separated'));image=snap('reunited-'+str(cycle))
            check('reunited renders '+str(cycle),image.mean()>10)
    else:report['dualDisplay']='pending: only one attached display'
    speeds=[]
    for value in [.5,1.,2.]:
        control.send('speed',value=value);control.send('pause',value=False);s=control.state();t=time.monotonic();time.sleep(1.2)
        observed=(control.state()['position']-s['position'])/(time.monotonic()-t);speeds.append({'requested':value,'observed':observed})
        check('playback speed '+str(value),abs(observed-value)<.35)
        control.send('pause',value=True)
    report['speeds']=speeds
    load(root/'work/portrait-motion.mp4',25);control.wait(lambda s:s.get('faces')==0)
    on=snap('synthetic-noface-on');control.send('enabled',value=False);off=snap('synthetic-noface-off')
    check('no-face output exactly original',np.array_equal(on,off))
    load(a);control.send('enabled',value=True);control.send('beauty',values={'smooth':29,'warm':4})
    close();start();s=load(a);check('settings restore after close/reopen',s['beauty']['smooth']==29 and s['beauty']['warm']==4)
    control.send('reset-picture');check('reset single video inherits global',control.state()['beauty']['smooth']==65)
    check('swap starts disabled',not control.state()['swapEnabled'])
    check('legacy file bytes untouched',hashlib.sha256((control.qa/'settings.json').read_bytes()).hexdigest()==legacy_hash)
    control.send('windowshot',path=str(out/'final-ui.png'))
    close()
    # Structurally invalid and future settings must stay byte-for-byte recoverable.
    for name,payload in [('bad-shape',{'version':2,'defaults':[],'media':[]}),('future',{'version':99}),('broken',None)]:
        control.qa=out/name;control.qa.mkdir()
        config=control.qa/'settings-v2.json';config.write_text(json.dumps(payload) if payload else '{broken',encoding='utf-8');before=config.read_bytes()
        start();s=load(a);check(name+' visible no-save state',not s['settingsWritable'] and '不保存' in s['pictureStatus'])
        control.send('beauty',values={'smooth':8});check(name+' warning survives adjustment','不保存' in control.state()['pictureStatus'])
        close();check(name+' preserves config',config.read_bytes()==before)
    report['passed']=True
finally:
    (out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'work/v060/latest-acceptance.txt').write_text(str(out),encoding='utf-8')
    close()
