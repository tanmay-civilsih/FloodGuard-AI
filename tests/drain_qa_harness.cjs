const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const html = fs.readFileSync(process.argv[2], 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
class Element {
  constructor(name) { this.name=name; this.children=[]; this.value=''; this.textContent=''; this.listeners={}; }
  setAttribute(key, value) { this[key]=value; }
  set innerHTML(value) { throw new Error('Untrusted HTML insertion is forbidden'); }
  appendChild(child) { this.children.push(child); if(this.name==='select' && !this.value) this.value=child.value; }
  replaceChildren() { this.children=[]; if(this.name==='select') this.value=''; }
  addEventListener(event, callback) { this.listeners[event]=callback; }
}
const ids=Object.fromEntries(['products','status','map','links','details','refresh'].map(id=>[id,new Element(id==='products'?'select':id)]));
let fail=false, lateResolve=null, delay=false;
const items=[{product_id:'reference',pilot_area_id:'<img src=x onerror=alert(1)>',product_kind:'DIRECTED_GRAPH',
  evidence_scope:'REFERENCE_FIXTURE',working_crs:'EPSG:32645',fingerprint:'a'.repeat(64),
  pipeline_version:'sequence-8-drain-model-v1',artifacts:{graph:{},assessment:{}}},
  {product_id:'draft',pilot_area_id:'Ward 7',product_kind:'IMPORT_DRAFT',evidence_scope:'REAL_PILOT_PROVISIONAL',
   working_crs:'EPSG:32645',artifacts:{draft:{}}}];
const qa={features:[{id:'e',geometry:{type:'LineString',coordinates:[[0,0],[10,10]]},properties:{kind:'PIPE',from:'a',to:'b'}},
  {id:'n',geometry:{type:'Point',coordinates:[0,0]},properties:{kind:'INLET'}}]};
function payload(url) {
  if(url.includes('?')) return items;
  if(url.endsWith('/qa')) return qa;
  if(url.endsWith('/wards')) return {boundaries:[]};
  return {readiness_status:url.endsWith('/draft')?'VISUAL_ONLY':'HYDRAULIC_SCENARIO_READY'};
}
const sandbox={document:{getElementById:id=>ids[id],createElement:name=>new Element(name),createElementNS:(_,name)=>new Element(name)},
  fetch:async url=> {
    if(delay && url.includes('/reference/assessment')) return new Promise(resolve=>{lateResolve=()=>resolve({ok:true,json:async()=>payload(url)});});
    return {ok:!fail,status:fail?409:200,json:async()=>payload(url)};
  }, console};
vm.createContext(sandbox); vm.runInContext(script,sandbox);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick();
  assert.match(ids.status.textContent,/REFERENCE_FIXTURE/);
  assert(ids.map.children.some(e=>e.name==='path'),'directed edge must show an arrow');
  assert.equal(ids.links.children.length,2);
  assert.match(ids.products.children[0].textContent,/<img/,'source text must remain text');
  fail=true; await vm.runInContext('selectProduct()',sandbox);
  assert.match(ids.status.textContent,/integrity check failed/);
  assert.equal(ids.map.children.length,0); assert.equal(ids.links.children.length,0);
  fail=false; delay=true;
  const pending=vm.runInContext('selectProduct()',sandbox); await tick();
  ids.products.value='draft'; await vm.runInContext('selectProduct()',sandbox);
  assert.match(ids.status.textContent,/REAL_PILOT_PROVISIONAL.*VISUAL_ONLY/);
  lateResolve(); await pending;
  assert.match(ids.status.textContent,/REAL_PILOT_PROVISIONAL/,'late response must not replace selection');
  delay=false; fail=true; await vm.runInContext('refresh()',sandbox);
  assert.match(ids.status.textContent,/Unable to load products/);
  console.log('PASS drain QA rendering, error clearing, safe text and stale-selection guard');
})().catch(e=>{console.error(e);process.exitCode=1;});
