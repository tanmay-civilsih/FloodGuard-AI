const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync(process.argv[2],'utf8'),script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
class Element{
 constructor(name){this.name=name;this.children=[];this.value='';this.textContent='';this.listeners={};}
 set innerHTML(value){throw new Error('Unsafe HTML');}
 appendChild(child){this.children.push(child);if(this.name==='products'&&!this.value)this.value=child.value;}
 replaceChildren(){this.children=[];if(this.name==='products')this.value='';}
 addEventListener(name,fn){this.listeners[name]=fn;}
}
const ids=Object.fromEntries(['products','status','links','components','details','refresh'].map(id=>[id,new Element(id)]));
let fail=false,delay=false,late=null;
function manifest(real){return{twin_id:real?'real':'reference',evidence_scope:real?'REAL_PILOT_PROVISIONAL':'REFERENCE_FIXTURE',
 hydraulic_readiness:real?'VISUAL_ONLY':'HYDRAULIC_SCENARIO_READY',vertical_reference_status:'UNRESOLVED',
 visual_city_version:{status:'MISSING',missing_reason:'<script>untrusted source</script>'},
 ward_version:{status:'AVAILABLE',source:{product_id:'ward'},artifact:{sha256:'a'.repeat(64)}}};}
const sandbox={document:{getElementById:id=>ids[id],createElement:name=>new Element(name)},fetch:async url=>{
 if(delay&&url.includes('/reference/'))return new Promise(resolve=>late=()=>resolve({ok:true,json:async()=>manifest(false)}));
 return{ok:!fail,status:fail?409:200,json:async()=>url.includes('?')?[{twin_id:'reference',pilot_area_id:'Reference',evidence_scope:'REFERENCE_FIXTURE'},
 {twin_id:'real',pilot_area_id:'Ward 7',evidence_scope:'REAL_PILOT_PROVISIONAL'}]:manifest(url.includes('/real/'))};
},console};vm.createContext(sandbox);vm.runInContext(script,sandbox);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{await tick();assert.match(ids.status.textContent,/REFERENCE_FIXTURE/);assert.equal(ids.components.children.length,2);
 assert.match(ids.components.children[0].children[2].textContent,/<script>/);
 fail=true;await vm.runInContext('selectTwin()',sandbox);assert.match(ids.status.textContent,/Unable to verify/);assert.equal(ids.links.children.length,0);
 fail=false;delay=true;const pending=vm.runInContext('selectTwin()',sandbox);await tick();ids.products.value='real';await vm.runInContext('selectTwin()',sandbox);
 late();await pending;assert.match(ids.status.textContent,/REAL_PILOT_PROVISIONAL.*VISUAL_ONLY/);
 delay=false;fail=true;await vm.runInContext('refresh()',sandbox);assert.match(ids.status.textContent,/Unable to load/);assert.equal(ids.components.children.length,0);
 console.log('PASS twin manifest rendering, safe source text, failure clearing and stale selection');
})().catch(error=>{console.error(error);process.exitCode=1;});
