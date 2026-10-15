"""Local WebGPU timing and known-motion quality check; all assets stay on E:."""
import functools, json, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/v050'
HTML = '''<!doctype html><meta charset="utf-8"><title>Framegen local benchmark</title>
<style>body{background:#172420;color:#eee;font:16px sans-serif}canvas{width:32%;height:auto}</style>
<p>Previous / neural midpoint / next — local motion fixture</p><script type="module">
import {createRT} from './framegen-package/package/rt.js';
window.result = null;
try {
 const adapter=await navigator.gpu.requestAdapter({powerPreference:'high-performance'});
 if(!adapter)throw Error('No WebGPU adapter');
 const device=await adapter.requestDevice({requiredFeatures:['shader-f16','timestamp-query']});
 const errors=[];device.addEventListener('uncapturederror',e=>errors.push(e.error.message));
 const [weightsBin,weightsManifest]=await Promise.all([
  fetch('./framegen-package/package/weights/rt_v7s.bin').then(r=>r.arrayBuffer()),
  fetch('./framegen-package/package/weights/rt_v7s.json').then(r=>r.json())]);
 const W=1280,H=720;const start=performance.now();
 const rt=await createRT(device,{w:W,h:H,weightsBin,weightsManifest,textureInput:true,textureOutput:true});
 const initMs=performance.now()-start;
 const photo=new Image();photo.src='/work/v02/swap-source.jpg';await photo.decode();
 const source=offset=>{const c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d');
  x.fillStyle='#28493c';x.fillRect(0,0,W,H);x.drawImage(photo,440+offset,130,400,460);
  x.fillStyle='#ed9040';x.fillRect(150+offset,300,120,150);return c;};
 const a=source(-12),b=source(12),gt=source(0);
 const texture=()=>device.createTexture({size:[W,H],format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.STORAGE_BINDING|GPUTextureUsage.COPY_DST|GPUTextureUsage.COPY_SRC|GPUTextureUsage.RENDER_ATTACHMENT});
 const ta=texture(),tb=texture(),out=texture();
 device.queue.copyExternalImageToTexture({source:a},{texture:ta},[W,H]);
 device.queue.copyExternalImageToTexture({source:b},{texture:tb},[W,H]);
 for(let i=0;i<5;i++){rt.prepPair(ta,tb);rt.runT(.5,out);await device.queue.onSubmittedWorkDone();}
 const times=[];for(let i=0;i<40;i++){const t=performance.now();rt.prepPair(ta,tb);rt.runT(.5,out);await device.queue.onSubmittedWorkDone();times.push(performance.now()-t);}
 const profile=await rt.profileT(ta,tb,.5,out);
 const read=device.createBuffer({size:W*H*4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
 const enc=device.createCommandEncoder();enc.copyTextureToBuffer({texture:out},{buffer:read,bytesPerRow:W*4},[W,H]);device.queue.submit([enc.finish()]);
 await read.mapAsync(GPUMapMode.READ);const pixels=new Uint8ClampedArray(read.getMappedRange().slice(0));read.unmap();read.destroy();
 const mid=document.createElement('canvas');mid.width=W;mid.height=H;mid.getContext('2d').putImageData(new ImageData(pixels,W,H),0,0);
 const data=c=>c.getContext('2d').getImageData(0,0,W,H).data;
 const da=data(a),db=data(b),dg=data(gt);let neural=0,blend=0,duplicate=0,fromA=0,fromB=0,n=0;
 for(let y=100;y<630;y++)for(let x=120;x<880;x++)for(let c=0;c<3;c++){
  const i=(y*W+x)*4+c;neural+=(pixels[i]-dg[i])**2;blend+=((da[i]+db[i])/2-dg[i])**2;duplicate+=(da[i]-dg[i])**2;
  fromA+=Math.abs(pixels[i]-da[i]);fromB+=Math.abs(pixels[i]-db[i]);n++;
 }
 document.body.append(a,mid,b);times.sort((a,b)=>a-b);
 window.result={gpu:{vendor:adapter.info.vendor,architecture:adapter.info.architecture,device:adapter.info.device,description:adapter.info.description},initMs,medianMs:times[20],p95Ms:times[38],profile,quality:{neuralMSE:neural/n,blendMSE:blend/n,duplicateMSE:duplicate/n,differenceFromA:fromA/n,differenceFromB:fromB/n},errors};
 rt.destroy();[ta,tb,out].forEach(t=>t.destroy());device.destroy();
}catch(e){window.result={error:e.stack};}
</script>'''
(OUT / 'benchmark.html').write_text(HTML, encoding='utf-8')
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server=ThreadingHTTPServer(('127.0.0.1',18769),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as p:
        context=p.chromium.launch_persistent_context(str(OUT / ('bench-profile-'+str(time.time_ns()))),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False,viewport={'width':1500,'height':680},args=['--window-size=1540,760'])
        page=context.new_page();page.goto('http://127.0.0.1:18769/work/v050/benchmark.html')
        page.wait_for_function('window.result!==null',timeout=120000)
        result=page.evaluate('window.result');print(json.dumps(result,ensure_ascii=False),flush=True)
        (OUT/'framegen-benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        page.screenshot(path=str(OUT/'framegen-midpoint.png'));context.close()
        assert not result.get('error'), result
        assert not result['errors'],result
        assert result['medianMs']<15,result
        assert result['quality']['neuralMSE']<result['quality']['blendMSE']*.8,result
finally:
    server.shutdown();server.server_close()
