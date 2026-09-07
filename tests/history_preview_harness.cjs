const fs=require("fs"),vm=require("vm"),assert=require("assert/strict");
const html=fs.readFileSync(process.argv[2],"utf8"),script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
class Element {
 constructor(id){this.id=id;this.children=[];this.value="";this.textContent="";this.listeners={};this.hidden=false;this.classList={add:()=>this.hidden=true,remove:()=>this.hidden=false};}
 set innerHTML(value){throw Error("Unsafe HTML insertion");}
 setAttribute(k,v){this[k]=v;}
 append(n){this.children.push(n);if(this.id==="events"&&!this.value)this.value=n.value;}
 replaceChildren(...nodes){this.children=[];for(const n of nodes)this.append(n);}
 addEventListener(k,f){this.listeners[k]=f;}
}
const ids=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element(m[1])]));
ids.embedded.textContent="null";
const rows=Array.from({length:3},(_,i)=>({start:"2021-09-20T0"+i+":00:00Z",end:"2021-09-20T0"+(i+1)+":00:00Z",rate_mm_h:i===1?null:10,qc:i===1?"MISSING":"VALID",accumulation_mm:i===0?10:null}));
function data(title){return {manifest:{title,windows:[],historical_event_id:title,availability:{availability_status:"UNKNOWN",acquired_at:"2026-09-07"},evidence_gaps:["<img onerror=bad>"]},request:{catchment_id:"ward",catchment_status:"STUDY_AREA",infrastructure_assumptions:["unknown"]},intervals:rows,coverage:{valid:2,total:3},map:{geometry:{type:"Polygon",coordinates:[[[0,0],[10,0],[10,10],[0,10],[0,0]]]},extraction_point:[20,20],horizontal_crs:"EPSG:32645"},source_resolution:"coarse",twin_readiness:"VISUAL_ONLY"};}
let fail=false,delay=false,late,interval=null;
const sandbox={document:{getElementById:id=>ids[id],createElement:id=>new Element(id),createElementNS:(_,id)=>new Element(id)},Intl,Date,console,encodeURIComponent,setInterval:f=>{interval=f;return 1;},clearInterval:()=>{interval=null;},fetch:async url=>{
 if(delay&&url.includes("slow"))return new Promise(resolve=>late=()=>resolve({ok:true,json:async()=>data("old")}));
 return {ok:!fail,status:fail?409:200,json:async()=>url==="/history/events"?[{historical_event_id:"first",event_key:"Real rainfall"}]:data(url.includes("new")?"new":"first")};
}};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await tick();assert.equal(ids.total.textContent,"Incomplete");assert.equal(ids.coverage.textContent,"2 / 3 h");assert.match(ids.gaps.children[0].textContent,/<img/);assert.ok(ids.map.children.length>0);
 ids.play.listeners.click();assert.equal(ids.play.textContent,"Pause");interval();assert.equal(ids.rate.textContent,"Missing");ids.play.listeners.click();assert.equal(interval,null);
 fail=true;await vm.runInContext('load("failed")',sandbox);assert.ok(ids.content.hidden);assert.match(ids.status.textContent,/409/);
 fail=false;delay=true;const pending=vm.runInContext('load("slow")',sandbox);await tick();await vm.runInContext('load("new")',sandbox);late();await pending;assert.match(ids.source.textContent,/^new/);
 console.log("PASS rainfall rendering, missing accumulation, safe evidence text, playback, failed and stale reads");
})().catch(error=>{console.error(error);process.exitCode=1;});
