const POPUP_VERSION='0.6.2';
const $=id=>document.getElementById(id);
const PARAMETERS=[['smooth','磨皮',0,200],['detail','纹理保留',0,150],['white','肤色提亮',-100,200],['warm','冷暖',-100,100],['pink','红润',0,150],['slim','瘦脸 / 丰脸',-100,150],['eyes','大眼 / 小眼',-100,150],['chin','下巴',-100,100],['nose','鼻翼',-100,100],['lip','唇色',0,150],['blush','腮红',0,150],['sharp','清晰度',0,150]];
const PRESETS={natural:{smooth:35,detail:70,white:15,warm:0,pink:8,slim:0,eyes:0,chin:0,nose:0,lip:0,blush:0,sharp:10}};
PRESETS.clear={...PRESETS.natural,smooth:70,white:50,pink:20,detail:75,slim:15,eyes:10};
PRESETS.strong={...PRESETS.natural,smooth:125,white:95,pink:35,detail:55,slim:45,eyes:35,lip:25};
let config,tabId,timer,uploadBusy=false,linkState='checking',bannerAuto=true;
const send=async message=>{const reply=await chrome.runtime.sendMessage(message);if(reply?.error)throw Error(reply.error);return reply;};
function message(text,error=false,auto=false){$('message').textContent=text;$('message').classList.toggle('error',error);bannerAuto=auto;}
// The pill reflects whether the local engine (background service or player) answers on the loopback port.
function link(state,text){linkState=state;$('connect').dataset.state=state;$('connect').querySelector('span').textContent=text;}
async function probe(manual){
 const before=linkState;
 try{await send({type:'connect'});link('online','已连接');if(manual||(before!=='online'&&bannerAuto))message('本地引擎已连接，视频和照片在本机处理。',false,!manual);}
 catch(e){link('offline','未连接');if(manual||before==='online'||(before!=='offline'&&bannerAuto))message(e.message,true,!manual);}
}
function markPreset(){for(const button of document.querySelectorAll('[data-preset]'))button.classList.toggle('active',Object.entries(PRESETS[button.dataset.preset]).every(([k,v])=>config.beauty[k]===v));}
function updateFields(){for(const key of ['enabled','compare','swapEnabled','vsrCompatible','interpolation'])$(key).checked=config[key];for(const key of ['swapTarget','swapStrength','swapFeather'])$(key).value=config[key];for(const [key] of PARAMETERS){$('range-'+key).value=config.beauty[key];$('number-'+key).value=config.beauty[key];}markPreset();}
function save(){clearTimeout(timer);timer=setTimeout(async()=>{try{config=(await send({type:'set-config',config,tabId})).config;updateFields();}catch(e){message(e.message,true);}},100);}
async function refresh(){if(!tabId||uploadBusy)return;try{const s=await send({type:'status',tabId});$('videoState').textContent=s.active?`${s.engineReady?'GPUPixel':'初始化中'} · ${s.version||'旧版'} · ${s.presentation==='video'?'VSR 兼容输出':'普通输出'} · ${s.shownFaces||0} 张脸 · ${s.roundTripMs?.toFixed(0)||0} ms${config?.swapEnabled?' · 换脸 '+(s.shownSwapFaces||0)+' 张':''}${s.needsCapture?' · 需要兼容捕获':''}`:'当前页面未启用增强';$('interpolationState').textContent=s.active&&config?.interpolation?`${s.interpolationReason||'等待补帧'} · 输入 ${(s.inputFps||0).toFixed(0)} → 输出 ${(s.outputFps||0).toFixed(0)} FPS · 生成 ${(s.interpolatedFps||0).toFixed(0)} FPS${s.interpolationMs?' · GPU '+s.interpolationMs.toFixed(1)+' ms':''}`:'补帧关闭';if(s.error)message(s.error,true);}catch{}}
async function init(){
 const requested=Number(new URLSearchParams(location.search).get('tab'));if(requested>0)tabId=requested;else tabId=(await chrome.tabs.query({active:true,currentWindow:true}))[0]?.id;
 const reply=await send({type:'config'});config=reply.config;
 if(reply.extensionVersion!==POPUP_VERSION){
  document.querySelectorAll('button,input,select').forEach(el=>{el.disabled=el.id!=='reloadExtension';});
  $('reloadExtension').hidden=false;
  message('扩展文件已更新，后台仍是旧版。请点击「重新加载扩展」，然后刷新视频网页。',true);
  $('videoState').textContent='更新后才能继续启用增强';link('offline','需更新');return;
 }
 for(const [key,label,min,max] of PARAMETERS){const div=document.createElement('div');div.className='parameter';div.innerHTML=`<label>${label}<input type="number" id="number-${key}" min="${min}" max="${max}"></label><input type="range" id="range-${key}" min="${min}" max="${max}">`;$('parameters').append(div);for(const kind of ['number','range'])$(kind+'-'+key).oninput=e=>{config.beauty[key]=Number(e.target.value);$(kind==='number'?'range-'+key:'number-'+key).value=e.target.value;markPreset();save();};}
 for(const key of ['enabled','compare','swapEnabled','vsrCompatible','interpolation'])$(key).onchange=e=>{config[key]=e.target.checked;save();};
 for(const key of ['swapTarget','swapStrength','swapFeather'])$(key).onchange=e=>{config[key]=key==='swapTarget'?e.target.value:Number(e.target.value);save();};
 updateFields();await Promise.all([refresh(),probe(false)]);setInterval(refresh,1000);setInterval(()=>probe(false),4000);
}
$('reloadExtension').onclick=()=>chrome.runtime.reload();
$('connect').onclick=()=>{link('checking','检测中');return probe(true);};
$('enable').onclick=async()=>{try{message('正在启动网页增强…');await send({type:'enable',tabId});link('online','已连接');message('已启用。可在网页浮窗调播放，或在这里改参数。');await refresh();}catch(e){message(e.message,true);}};
$('stop').onclick=async()=>{try{await send({type:'stop',tabId});message('已恢复原播放器');await refresh();}catch(e){message(e.message,true);}};
for(const button of document.querySelectorAll('[data-preset]'))button.onclick=()=>{config.beauty={...PRESETS[button.dataset.preset]};updateFields();save();};
$('sourceFile').onchange=async event=>{
 const file=event.target.files[0];if(!file)return;uploadBusy=true;message('正在载入源照片，首次启用换脸需要几秒…');
 try{if(file.size>30_000_000)throw Error('照片文件过大，请使用 30 MB 以内照片');const image=await createImageBitmap(file);const scale=Math.min(1,1280/Math.max(image.width,image.height));const canvas=document.createElement('canvas');canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);image.close();const png=canvas.toDataURL('image/png').split(',')[1];const result=await send({type:'source',png});$('sourceName').textContent=file.name;updateFields();save();message('源照片已就绪 · '+result.provider+(result.sourceFaces>1?' · 已选最大人脸':''));}catch(e){message(e.message,true);}finally{uploadBusy=false;$('sourceFile').value='';}
};
$('clearSource').onclick=async()=>{try{await send({type:'clear-source'});config.swapEnabled=false;updateFields();save();$('sourceName').textContent='源照片已清除';message('源照片已清除');}catch(e){message(e.message,true);}};
init().catch(e=>message(e.message,true));
