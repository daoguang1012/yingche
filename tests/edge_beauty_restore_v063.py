"""Actual browser GPUPixel and frozen 0.4.1 analysis on a real public clip."""
import base64, json, subprocess, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/v063-restore'/('web-'+str(time.time_ns()));OUT.mkdir(parents=True)
CLIP=ROOT/'work/v04/intel-fixtures/head-pose-face-detection-female.mp4'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/':
            body=b'<video id="v" muted preload="auto" src="/clip.mp4"></video><canvas id="c"></canvas>'
            self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if self.path!='/clip.mp4':self.send_error(404);return
        total=CLIP.stat().st_size;start=0;end=total-1;status=200
        if self.headers.get('Range'):
            first,last=self.headers['Range'].removeprefix('bytes=').split('-',1);start=int(first);end=int(last) if last else end;status=206
        self.send_response(status);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
        self.end_headers()
        try:
            with CLIP.open('rb') as f:f.seek(start);self.wfile.write(f.read(end-start+1))
        except (BrokenPipeError,ConnectionResetError):pass

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False)
        page=browser.new_page(viewport={'width':1100,'height':850})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.wait_for_function('v.readyState>=2')
        page.evaluate('()=>{v.pause();v.currentTime=35}')
        page.wait_for_function('!v.seeking && Math.abs(v.currentTime-35)<.01')
        source=page.evaluate('()=>{const a=document.createElement("canvas");a.width=v.videoWidth;a.height=v.videoHeight;a.getContext("2d").drawImage(v,0,0);return a.toDataURL("image/png").split(",")[1]}')
        request={'id':1,'generation':1,'pts':35,'paused':True,'sampleTime':0,'png':source,'swapEnabled':False}
        run=subprocess.run([str(ROOT/'app/face_engine_v041/FaceEngine.exe'),str(ROOT/'models/face_landmarker.task')],
                           input=json.dumps(request)+'\n',text=True,capture_output=True,timeout=50,creationflags=subprocess.CREATE_NO_WINDOW)
        rows=[json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
        assert run.returncode==0 and rows[0].get('ready') and rows[1].get('faces')
        for name in ['gpupixel.js','gpupixel-engine.js','renderer.js']:
            page.add_script_tag(path=str(ROOT/'edge-extension'/name))
        result=page.evaluate('''async data=>{
            c.width=v.videoWidth;c.height=v.videoHeight;const r=new YingcheRenderer(c);await r.ready;
            data.sampleTime=performance.now();await r.analysis(data);
            const cfg={enabled:false,compare:false,swapEnabled:false,swapStrength:100,beauty:{smooth:35,detail:70,white:15,warm:0,pink:8,slim:0,eyes:0,chin:0,nose:0,lip:0,blush:0,sharp:10}};
            const read=()=>{const a=new Uint8Array(c.width*c.height*4);r.gl.readPixels(0,0,c.width,c.height,r.gl.RGBA,r.gl.UNSIGNED_BYTE,a);return a};
            r.render(v,cfg,35,1,true);const original=read();cfg.enabled=true;r.render(v,cfg,35,1,true);const beauty=read();
            let changed=0;for(let i=0;i<beauty.length;i+=4)if(Math.max(Math.abs(original[i]-beauty[i]),Math.abs(original[i+1]-beauty[i+1]),Math.abs(original[i+2]-beauty[i+2]))>1)changed++;
            const full=c.toDataURL();cfg.compare=true;r.render(v,cfg,35,1,true);const compare=read();let leftDifference=0;
            for(let y=0;y<c.height;y++)for(let x=0;x<c.width/2-2;x++)for(let k=0;k<3;k++){const i=(y*c.width+x)*4+k;leftDifference=Math.max(leftDifference,Math.abs(compare[i]-original[i]));}
            r.clear();cfg.compare=false;cfg.enabled=false;r.render(v,cfg,35,1,true);const stopped=read();let restoreDifference=0;for(let i=0;i<stopped.length;i++)restoreDifference=Math.max(restoreDifference,Math.abs(stopped[i]-original[i]));
            const result={engine:r.gpu.version,shownFaces:data.faces.length,changedPixels:changed,leftOriginalMaxDifference:leftDifference,disabledMaxDifference:restoreDifference,hasSyncRing:typeof r.ingest==='function',image:full};r.dispose();return result;
        }''',rows[1])
        (OUT/'beauty.png').write_bytes(base64.b64decode(result.pop('image').split(',')[1]))
        assert result['changedPixels']>100 and result['shownFaces']>0
        assert result['leftOriginalMaxDifference']==0 and result['disabledMaxDifference']==0 and not result['hasSyncRing']
        assert not errors,errors
        result['passed']=True;result['errors']=errors
        (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close();print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
finally:
    server.shutdown();server.server_close()
