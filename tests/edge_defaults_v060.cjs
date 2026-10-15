const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'edge-extension/background.js'),'utf8');
function worker(storage){
 const ctx=vm.createContext({structuredClone,chrome:{runtime:{id:'test',onMessage:{addListener(){}}},storage:{local:{
  async get(keys){return Object.fromEntries((Array.isArray(keys)?keys:[keys]).map(k=>[k,storage[k]]));},
  async set(value){Object.assign(storage,structuredClone(value));}
 }}}});vm.runInContext(source,ctx);return ctx;
}
(async()=>{
 const old={interpolation:true,swapEnabled:true,vsrCompatible:false,beauty:{smooth:51,warm:7},swapTarget:'2',swapStrength:63};
 const storage={config:structuredClone(old)},ctx=worker(storage);
 const configs=await Promise.all([vm.runInContext('config()',ctx),vm.runInContext('config()',ctx)]);
 for(const c of configs){assert.equal(c.interpolation,false);assert.equal(c.swapEnabled,false);assert.equal(c.vsrCompatible,false);assert.equal(c.beauty.smooth,51);assert.equal(c.swapTarget,'2');}
 assert.deepEqual(storage.configBefore060,old);
 await vm.runInContext("run({type:'set-config',config:{...DEFAULT,interpolation:true,swapEnabled:true}},{id:'test'})",ctx);
 const reopened=await vm.runInContext('config()',worker(storage));assert.equal(reopened.interpolation,true);assert.equal(reopened.swapEnabled,true);
 const fresh=await vm.runInContext('config()',worker({}));assert.equal(fresh.interpolation,false);assert.equal(fresh.swapEnabled,false);
 console.log('PASS defaults off, one-time migration preserves full old config, explicit opt-in survives worker restart, VSR choice unchanged');
})().catch(error=>{console.error(error);process.exitCode=1;});
