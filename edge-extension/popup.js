const $=id=>document.getElementById(id);
const PARAMETERS=[['smooth','磨皮',0,200],['detail','纹理保留',0,150],['white','肤色提亮',-100,200],['warm','冷暖',-100,100],['pink','红润',0,150],['slim','瘦脸 / 丰脸',-100,150],['eyes','大眼 / 小眼',-100,150],['chin','下巴',-100,100],['nose','鼻翼',-100,100],['lip','唇色',0,150],['blush','腮红',0,150],['sharp','清晰度',0,150]];
let config,tabId,timer,uploadBusy=false;
const send=async message=>{const reply=await chrome.runtime.sendMessage(message);if(reply?.error)throw Error(reply.error);return reply;};
function message(text,error=false){$('message').textContent=text;$('message').classList.toggle('error',error);}
function updateFields(){for(const key of ['enabled','compare','swapEnabled'])$(key).checked=config[key];for(const key of ['swapTarget','swapStrength','swapFeather'])$(key).value=config[key];for(const [key] of PARAMETERS){$('range-'+key).value=config.beauty[key];$('number-'+key).value=config.beauty[key];}}
function save(){clearTimeout(timer);timer=setTimeout(async()=>{try{config=(await send({type:'set-config',config,tabId})).config;updateFields();}catch(e){message(e.message,true);}},100);}
async function refresh(){if(!tabId||uploadBusy)return;try{const s=await send({type:'status',tabId});$('videoState').textContent=s.active?`${s.engineReady?'GPUPixel':'初始化中'} · ${s.version||'旧版'} · ${s.shownFaces||0} 张脸 · ${s.roundTripMs?.toFixed(0)||0} ms${config?.swapEnabled?' · 换脸 '+(s.shownSwapFaces||0)+' 张':''}${s.needsCapture?' · 需要兼容捕获':''}`:'当前页面未启用增强';if(s.error)message(s.error,true);}catch{}}
async function init(){
 const requested=Number(new URLSearchParams(location.search).get('tab'));if(requested>0)tabId=requested;else tabId=(await chrome.tabs.query({active:true,currentWindow:true}))[0]?.id;
 config=(await send({type:'config'})).config;
 for(const [key,label,min,max] of PARAMETERS){const div=document.createElement('div');div.className='parameter';div.innerHTML=`<label>${label}<input type="number" id="number-${key}" min="${min}" max="${max}"></label><input type="range" id="range-${key}" min="${min}" max="${max}">`;$('parameters').append(div);for(const kind of ['number','range'])$(kind+'-'+key).oninput=e=>{config.beauty[key]=Number(e.target.value);$(kind==='number'?'range-'+key:'number-'+key).value=e.target.value;save();};}
 for(const key of ['enabled','compare','swapEnabled'])$(key).onchange=e=>{config[key]=e.target.checked;save();};
 for(const key of ['swapTarget','swapStrength','swapFeather'])$(key).onchange=e=>{config[key]=key==='swapTarget'?e.target.value:Number(e.target.value);save();};
 updateFields();await refresh();setInterval(refresh,1000);
}
$('connect').onclick=async()=>{try{await send({type:'connect'});message('本地引擎已连接，视频和照片在本机处理。');}catch(e){message(e.message,true);}};
$('enable').onclick=async()=>{try{message('正在启动网页增强…');await send({type:'enable',tabId});message('已启用。可在网页浮窗调播放，或在这里改参数。');await refresh();}catch(e){message(e.message,true);}};
$('stop').onclick=async()=>{try{await send({type:'stop',tabId});message('已恢复原播放器');await refresh();}catch(e){message(e.message,true);}};
for(const button of document.querySelectorAll('[data-preset]'))button.onclick=()=>{config.beauty={smooth:35,detail:70,white:15,warm:0,pink:8,slim:0,eyes:0,chin:0,nose:0,lip:0,blush:0,sharp:10};if(button.dataset.preset==='clear')Object.assign(config.beauty,{smooth:70,white:50,pink:20,detail:75,slim:15,eyes:10});if(button.dataset.preset==='strong')Object.assign(config.beauty,{smooth:125,white:95,pink:35,detail:55,slim:45,eyes:35,lip:25});updateFields();save();};
$('sourceFile').onchange=async event=>{
 const file=event.target.files[0];if(!file)return;uploadBusy=true;message('正在载入源照片，首次启用换脸需要几秒…');
 try{if(file.size>30_000_000)throw Error('照片文件过大，请使用 30 MB 以内照片');const image=await createImageBitmap(file);const scale=Math.min(1,1280/Math.max(image.width,image.height));const canvas=document.createElement('canvas');canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);image.close();const png=canvas.toDataURL('image/png').split(',')[1];const result=await send({type:'source',png});$('sourceName').textContent=file.name;config.swapEnabled=true;updateFields();save();message('源照片已就绪 · '+result.provider+(result.sourceFaces>1?' · 已选最大人脸':''));}catch(e){message(e.message,true);}finally{uploadBusy=false;$('sourceFile').value='';}
};
$('clearSource').onclick=async()=>{try{await send({type:'clear-source'});config.swapEnabled=false;updateFields();save();$('sourceName').textContent='源照片已清除';message('源照片已清除');}catch(e){message(e.message,true);}};
init().catch(e=>message(e.message,true));
