import sys,time,subprocess,json,psutil,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tests'));import control
pkg=root/'release/映澈-0.4.1-win64';out=root/'work/v041';control.qa=out/('qa-launcher-'+str(int(time.time()*1000)));control.qa.mkdir()
config_path=pkg/'edge-extension/bridge-config.json'
original_config=config_path.read_bytes()
config=json.loads(original_config);config['port']=28769;config_path.write_text(json.dumps(config),encoding='utf-8')
launcher=subprocess.Popen([str(pkg/'Yingche.exe'),'--control-dir',str(control.qa),str(root/'work/portrait-motion.mp4')],cwd=pkg,creationflags=subprocess.CREATE_NO_WINDOW)
report={}
try:
 launcher.wait(timeout=5);assert launcher.returncode==0
 s=control.wait(lambda s:s.get('workerReady') and s.get('loaded') and s.get('gpupixelReady'),30);assert s['version']=='0.4.1'
 control.send('pause',value=True);control.send('seek',seconds=2);control.wait(lambda s:s.get('faces')==1 and s.get('generation')==s.get('resultGeneration'))
 for n in range(8):
  control.send('seek',seconds=control.state()['position']);control.wait(lambda s:s.get('faces')==1 and s.get('generation')==s.get('resultGeneration'),4)
 report['repeatedSeekSamePTS']=8
 control.send('bridge',value=True);control.wait(lambda s:'已就绪' in s.get('bridgeStatus',''),25)
 ident='apamfckhomfpifcdadlphjjpbllfnpba'
 req=urllib.request.Request('http://127.0.0.1:28769/session',data=b'{}',headers={'Content-Type':'application/json','Origin':'chrome-extension://'+ident,'X-Yingche-Extension':ident},method='POST')
 with urllib.request.urlopen(req,timeout=5) as response:data=json.load(response)
 assert data['version']=='0.4.1';report['bridgeVersion']=data['version']
 processes=[]
 for proc in psutil.process_iter(['pid','exe','cmdline']):
  if str(control.qa) in (proc.info['cmdline'] or []):
   processes=[proc.info['exe'],*[c.exe() for c in proc.children(recursive=True)]];break
 report['processPaths']=processes;assert len(processes)>=3 and all(pkg in Path(p).parents or Path(p).name.lower()=='conhost.exe' for p in processes)
 report['launcher']=str(pkg/'Yingche.exe');report['passed']=True
finally:
 config_path.write_bytes(original_config)
 (out/'launcher-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');control.send('quit')
print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
