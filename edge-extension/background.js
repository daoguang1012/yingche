const EXTENSION_VERSION='0.6.0';
const BASE='http://127.0.0.1:18766';
function requireCurrentBridge(data){if(data.version!=='0.4.1')throw Error('本地引擎版本不符：请运行映澈后台服务，或在播放器重新启用 Edge 连接（需要 0.4.1 桥接协议）');return data;}
const DEFAULT={interpolation:false,vsrCompatible:true,enabled:true,compare:false,swapEnabled:false,swapTarget:'largest',swapStrength:100,swapFeather:35,beauty:{smooth:35,detail:70,white:15,warm:0,pink:8,slim:0,eyes:0,chin:0,nose:0,lip:0,blush:0,sharp:10}};
const RANGES={smooth:[0,200],detail:[0,150],white:[-100,200],warm:[-100,100],pink:[0,150],slim:[-100,150],eyes:[-100,150],chin:[-100,100],nose:[-100,100],lip:[0,150],blush:[0,150],sharp:[0,150]};
let token=null,connecting=null;
function sanitize(value={}){const c=structuredClone(DEFAULT);for(const key of ['enabled','compare','swapEnabled','vsrCompatible','interpolation'])if(typeof value[key]==='boolean')c[key]=value[key];for(const key of ['swapStrength','swapFeather'])if(Number.isFinite(value[key]))c[key]=Math.min(100,Math.max(0,value[key]));if(['largest','all','0','1','2','3'].includes(value.swapTarget))c.swapTarget=value.swapTarget;for(const [k,[lo,hi]] of Object.entries(RANGES)){const v=value.beauty?.[k];if(Number.isFinite(v))c.beauty[k]=Math.max(lo,Math.min(hi,v));}return c;}
let configMigration=null;
async function config(){
 if(!configMigration)configMigration=(async()=>{
  const stored=await chrome.storage.local.get(['config','stableDefaultsVersion']);
  if(stored.stableDefaultsVersion!==1){
   const c=sanitize(stored.config);c.interpolation=false;c.swapEnabled=false;
   await chrome.storage.local.set({...(stored.config?{configBefore060:stored.config}:{}),config:c,stableDefaultsVersion:1});
  }
 })().catch(error=>{configMigration=null;throw error;});
 await configMigration;return sanitize((await chrome.storage.local.get('config')).config);
}
async function call(path,payload,retry=true){
 if(path!='/session'&&!token){if(!connecting)connecting=call('/session',{},false).then(r=>{requireCurrentBridge(r);token=r.token;return r;}).finally(()=>{connecting=null;});await connecting;}
 let response;
 try{response=await fetch(BASE+path,{method:'POST',headers:{'Content-Type':'application/json','X-Yingche-Extension':chrome.runtime.id,...(token?{'Authorization':'Bearer '+token}:{})},body:JSON.stringify(payload),signal:AbortSignal.timeout(path==='/source'?60000:8000),cache:'no-store'});}catch(e){throw Error('未检测到本地引擎：请运行映澈后台服务 YingcheService.exe，或在播放器「换脸」页启用 Edge 连接');}
 const value=await response.json();if(response.status===401&&retry){token=null;return call(path,payload,false);}if(!response.ok)throw Error(value.error||'本地处理失败');return value;
}
async function run(message,sender){
 if(sender.id!==chrome.runtime.id)throw Error('Invalid sender');
 if(message.type==='config'){const c=await config();return {config:c,extensionVersion:EXTENSION_VERSION};}
 if(message.type==='set-config'){await config();const c=sanitize(message.config);await chrome.storage.local.set({config:c});if(Number.isInteger(message.tabId)){try{await chrome.tabs.sendMessage(message.tabId,{type:'yingche-config',config:c});}catch{}}return {config:c};}
 if(message.type==='connect'){const data=requireCurrentBridge(await call('/session',{}));token=data.token;return {ok:true,sourceReady:data.sourceReady};}
 if(message.type==='source'){const result=await call('/source',{png:message.png});return result;}
 if(message.type==='clear-source')return call('/clear-source',{});
 if(message.type==='analyze')return call('/analyze',{...message.payload,streamId:String(sender.tab?.id||0)});
 if(message.type==='enable'){
  const tab=await chrome.tabs.get(message.tabId);if(!/^https?:/.test(tab.url||''))throw Error('请在普通网页的视频页面启用扩展');
  const checks=await chrome.scripting.executeScript({target:{tabId:message.tabId},func:()=>({version:globalThis.__yingcheController?.version,overlay:!!document.getElementById('yingche-video-layer')})});
  const existing=checks[0]?.result;
  if(existing?.version&&existing.version!==EXTENSION_VERSION)throw Error('页面仍有旧版增强，请刷新视频页面后重新启用');
  requireCurrentBridge(await call('/session',{}));await chrome.scripting.executeScript({target:{tabId:message.tabId},files:['gpupixel.js','gpupixel-engine.js','renderer.js','vendor/framegen/rt.js','interpolation.js','content.js']});
  const previous=(await chrome.storage.session.get('activeVideoTab')).activeVideoTab;
  if(previous&&previous!==message.tabId){try{await chrome.tabs.sendMessage(previous,{type:'yingche-stop'});}catch{}}
  const result=await chrome.tabs.sendMessage(message.tabId,{type:'yingche-start',config:await config()});
  if(result.active)await chrome.storage.session.set({activeVideoTab:message.tabId});
  return result;
 }
 if(message.type==='stop')return chrome.tabs.sendMessage(message.tabId,{type:'yingche-stop'});
 if(message.type==='status'){try{return await chrome.tabs.sendMessage(message.tabId,{type:'yingche-status'});}catch{return {active:false};}}
 throw Error('Unknown message');
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{run(message,sender).then(reply).catch(e=>reply({error:e.message}));return true;});
