"""Self-contained, read-only rainfall preview; escaped evidence and no external assets."""

import json
from typing import Any


def render_preview(data: dict[str, Any] | None = None) -> str:
    embedded = (
        json.dumps(data, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return PAGE.replace("__EMBEDDED_DATA__", embedded)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FloodGuard · Historical rainfall</title>
<style>
:root{color-scheme:dark;--bg:#0b1523;--panel:#121f31;--line:#2c3b50;--text:#eef3f7;--muted:#a9bbce;--mint:#71e6c4;--amber:#ffcd80}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,sans-serif}
main{max-width:1240px;margin:auto;padding:34px 30px 60px}header{display:flex;justify-content:space-between;align-items:center;gap:20px}
.brand{letter-spacing:2px;font-weight:750;font-size:15px}.badge{border:1px solid #526049;border-radius:30px;padding:5px 14px;color:var(--amber);font-size:12px;letter-spacing:1px}
.eyebrow{font-size:12px;letter-spacing:2px;color:var(--mint);margin-top:42px}h1{font-size:clamp(28px,4vw,43px);line-height:1.2;margin:10px 0 14px;letter-spacing:-1px}
.muted{color:var(--muted)}.intro{max-width:850px;margin-bottom:25px}.notice{border-left:3px solid var(--amber);padding:10px 16px;background:#242830;color:#f2d5a5}
.toolbar{display:flex;align-items:center;gap:14px;margin:24px 0}.toolbar label{flex-shrink:0}
select,button{font:inherit;color:var(--text);background:var(--panel);border:1px solid #43546e;border-radius:8px;padding:9px 14px}
select{max-width:100%;flex:1}button{cursor:pointer}button:hover{border-color:var(--mint)}button:disabled{opacity:.5;cursor:default}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--mint);outline-offset:4px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}.metric,.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px}
.metric strong{display:block;font-size:25px;font-weight:600;margin:5px 0}.small{font-size:12px;color:var(--muted)}
.columns{display:grid;grid-template-columns:1fr 1.25fr;gap:18px}.card h2{font-size:16px;margin:0 0 4px;font-weight:600}
svg{width:100%;display:block;margin-top:14px;overflow:visible}.chart{height:190px}.map{height:270px;background:#102638;border-radius:8px}
.legend{display:flex;gap:18px;font-size:12px;color:var(--muted);margin-top:12px}.mint{color:var(--mint)}.amber{color:var(--amber)}
.timeline{display:flex;gap:18px;align-items:center;margin-top:20px}input[type=range]{flex:1;accent-color:var(--mint);min-width:50px}
.time{font-variant-numeric:tabular-nums;margin-top:12px;color:var(--mint)}.evidence{margin-top:20px}.evidence p{margin:8px 0}
details{margin-top:18px;border-top:1px solid var(--line);padding-top:15px}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--muted);font-size:12px}
#status{min-height:24px;color:var(--amber)}.hidden{display:none!important}a{color:var(--mint)}
@media(max-width:780px){main{padding:22px 16px}.columns{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}header{align-items:flex-start}.toolbar{flex-wrap:wrap}.toolbar label{width:100%}}
</style></head><body><main>
<header><div class="brand">FLOODGUARD / DATA EXPLORER</div><span class="badge">HISTORICAL REPLAY</span></header>
<div class="eyebrow">KOLKATA · RAINFALL EVIDENCE</div>
<h1>A rainfall event, hour by hour.</h1>
<p class="intro muted">Explore an archived precipitation estimate, its timing and its source coverage. Every replay window links to retained data and an immutable forcing package.</p>
<p class="notice">Rainfall preview only. Coarse reanalysis estimate; not rain-gauge or radar measurements, simulated flood depth, or a live forecast.</p>
<div class="toolbar"><label for="events">Retained event</label><select id="events" aria-label="Select retained historical event"><option>Loading events…</option></select></div>
<div id="status" role="status" aria-live="polite">Loading verified evidence…</div>
<section id="content" class="hidden">
<div class="metrics">
<div class="metric"><span class="small">EVENT RAINFALL</span><strong id="total"></strong><span class="small">Integrated hourly estimate</span></div>
<div class="metric"><span class="small">CURRENT INTERVAL</span><strong id="rate"></strong><span class="small" id="qc"></span></div>
<div class="metric"><span class="small">VALID COVERAGE</span><strong id="coverage"></strong><span class="small">Missing intervals stay missing</span></div>
<div class="metric"><span class="small">TWIN STATUS</span><strong id="twin" style="font-size:18px"></strong><span class="small">No hydraulic state initialized</span></div>
</div>
<div class="columns">
<section class="card"><h2>Study area &amp; extraction point</h2><p class="small" id="map-label"></p>
<svg id="map" class="map" viewBox="0 0 440 270" role="img" aria-label="Retained twin study-area outline and requested weather extraction point"></svg>
<div class="legend"><span class="mint">━ Study-area boundary</span><span class="amber">● Weather extraction point</span></div>
<p class="small" id="resolution"></p><p class="small">Uniform regional application is an explicit assumption. This outline is not a rainfall measurement footprint or a verified connected drainage catchment.</p></section>
<section class="card"><h2>Interval rainfall</h2><span class="small">Average rate · mm/h · UTC hour start</span>
<svg id="rain" class="chart" viewBox="0 0 560 190" role="img" aria-label="Hourly rainfall rate chart"></svg>
<h2 style="margin-top:18px">Accumulated rainfall</h2><span class="small">Integrated from event start · mm · breaks when coverage is incomplete</span>
<svg id="accumulation" class="chart" viewBox="0 0 560 190" role="img" aria-label="Accumulated rainfall chart"></svg></section>
</div>
<div class="card evidence"><h2>Replay time</h2><div class="timeline"><button id="play" type="button">Play</button>
<input id="time" type="range" min="0" max="0" value="0" aria-label="Selected rainfall interval"></div>
<div class="time" id="timestamp"></div><p class="small" id="local-time"></p><p id="window" class="small"></p></div>
<div class="card evidence"><h2>Evidence &amp; limits</h2><p id="source"></p><p class="small" id="availability"></p>
<ul id="gaps"></ul><p class="small" id="assumptions"></p>
<details><summary>Inspect immutable event and source identities</summary><pre id="provenance"></pre></details>
<p class="small">Source: <a href="https://power.larc.nasa.gov/docs/services/api/temporal/hourly/" target="_blank" rel="noopener">NASA POWER</a> / GMAO MERRA-2. No model execution or data acquisition is triggered by this page.</p></div>
</section></main>
<script id="embedded" type="application/json">__EMBEDDED_DATA__</script>
<script>
"use strict";
const $=id=>document.getElementById(id), ns="http://www.w3.org/2000/svg";
let current=null, timer=null, generation=0;
function node(tag,attrs,text){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
function stop(){if(timer!==null)clearInterval(timer);timer=null;$("play").textContent="Play";}
function tickLabels(svg,maximum,count){for(let j=0;j<=3;j++){const y=155-j*44;svg.append(node("line",{x1:40,x2:548,y1:y,y2:y,stroke:"#2c3b50"}));svg.append(node("text",{x:34,y:y+4,fill:"#a9bbce","text-anchor":"end","font-size":10},(maximum*j/3).toFixed(1)));}
for(const i of [...new Set([0,Math.floor((count-1)/2),count-1])]){const x=40+(i+.5)*508/count;svg.append(node("text",{x,y:178,fill:"#a9bbce","text-anchor":"middle","font-size":10},new Date(current.intervals[i].start).toISOString().slice(11,16)));}}
function chart(id,key,selected,bars){const svg=$(id);svg.replaceChildren();const rows=current.intervals,n=rows.length;
const maximum=Math.max(1,...rows.map(r=>r[key]===null?0:r[key]));tickLabels(svg,maximum,n);const width=508/n;let segment=[];
function finish(){if(segment.length)svg.append(node("polyline",{points:segment.join(" "),fill:"none",stroke:"#71e6c4","stroke-width":2}));segment=[];}
rows.forEach((r,i)=>{const x=40+(i+.5)*width,v=r[key];
if(i===selected)svg.append(node("rect",{x:40+i*width,y:18,width,height:137,fill:"#71e6c4",opacity:.09}));
if(v===null){finish();svg.append(node("text",{x,y:150,fill:"#ffcd80","text-anchor":"middle","font-size":11},"x"));return;}
const y=155-v/maximum*132;if(bars)svg.append(node("rect",{x:40+i*width+1,y,width:Math.max(1,width-2),height:Math.max(.8,155-y),rx:2,fill:i===selected?"#ffcd80":"#71e6c4",opacity:i===selected?1:.65}));else segment.push(x+","+y);});finish();}
function drawMap(){const svg=$("map");svg.replaceChildren();const g=current.map.geometry;
const polygons=g.type==="Polygon"?[g.coordinates]:g.coordinates;const all=polygons.flat(2);const p=current.map.extraction_point;all.push(p);
const xs=all.map(v=>v[0]),ys=all.map(v=>v[1]);const minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);
const scale=Math.min(380/Math.max(1,maxx-minx),210/Math.max(1,maxy-miny));const cx=(minx+maxx)/2,cy=(miny+maxy)/2;
const xy=v=>[220+(v[0]-cx)*scale,135-(v[1]-cy)*scale];
polygons.forEach(poly=>{const path=poly.map(ring=>ring.map((v,i)=>(i?"L":"M")+xy(v).join(",")).join(" ")+"Z").join(" ");
svg.append(node("path",{d:path,fill:"#1e5861",stroke:"#71e6c4","stroke-width":2,"fill-rule":"evenodd"}));});
const point=xy(p);svg.append(node("circle",{cx:point[0],cy:point[1],r:5,fill:"#ffcd80",stroke:"#0b1523","stroke-width":2}));
svg.append(node("text",{x:410,y:24,fill:"#a9bbce","font-size":12},"N ↑"));
const metres=Math.max(1,Math.round(90/scale));svg.append(node("line",{x1:20,x2:20+metres*scale,y1:245,y2:245,stroke:"#a9bbce","stroke-width":2}));
svg.append(node("text",{x:20,y:237,fill:"#a9bbce","font-size":10},metres+" m")); }
function drawTime(){if(!current)return;const i=Number($("time").value),row=current.intervals[i];
$("rate").textContent=row.rate_mm_h===null?"Missing":row.rate_mm_h.toFixed(2)+" mm/h";$("qc").textContent="QC: "+row.qc;
$("timestamp").textContent=new Date(row.start).toISOString().slice(0,16).replace("T"," ")+" → "+new Date(row.end).toISOString().slice(11,16)+" UTC";
$("local-time").textContent="Asia/Kolkata: "+new Intl.DateTimeFormat("en-IN",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Kolkata"}).format(new Date(row.start))+" (display only)";
const w=current.manifest.windows.find(w=>Date.parse(w.start)<=Date.parse(row.start)&&Date.parse(row.start)<Date.parse(w.end));
$("window").textContent=w?"Window: "+w.status+" · package "+(w.forcing_package_id||"not created")+" · "+w.blockers.join("; "):"No linked window";
chart("rain","rate_mm_h",i,true);chart("accumulation","accumulation_mm",i,false);}
function display(data){stop();if(!Array.isArray(data.intervals)||!data.intervals.length)throw Error("Event has no intervals");current=data;
$("time").max=String(data.intervals.length-1);$("time").value="0";$("content").classList.remove("hidden");
const last=data.intervals[data.intervals.length-1];$("total").textContent=last.accumulation_mm===null?"Incomplete":last.accumulation_mm.toFixed(2)+" mm";
$("coverage").textContent=data.coverage.valid+" / "+data.coverage.total+" h";$("twin").textContent=data.twin_readiness.replaceAll("_"," ");
$("map-label").textContent=data.request.catchment_id+" · "+data.request.catchment_status+" · "+data.map.horizontal_crs;
$("resolution").textContent=data.source_resolution;$("source").textContent=data.manifest.title+" · NASA POWER / MERRA-2 reanalysis";
$("availability").textContent="Historical provider availability: "+data.manifest.availability.availability_status+". Acquired "+data.manifest.availability.acquired_at+". Strict issue-time backtest: ineligible.";
$("gaps").replaceChildren();data.manifest.evidence_gaps.forEach(g=>{const li=document.createElement("li");li.textContent=g;$("gaps").append(li);});
$("assumptions").textContent=data.request.infrastructure_assumptions.join(" ");$("provenance").textContent=JSON.stringify(data.manifest,null,2);
$("status").textContent="Verified retained rainfall evidence. No flood-validation claim.";drawMap();drawTime();}
async function json(url){const response=await fetch(url,{cache:"no-store"});if(!response.ok)throw Error("Evidence request failed: HTTP "+response.status);return response.json();}
async function load(id){const mine=++generation;stop();current=null;$("content").classList.add("hidden");$("status").textContent="Verifying event artifacts…";
try{const data=await json("/history/events/"+encodeURIComponent(id)+"/view");if(mine===generation)display(data);}
catch(error){if(mine===generation)$("status").textContent=error.message;}}
$("time").addEventListener("input",()=>{stop();drawTime();});$("play").addEventListener("click",()=>{if(timer!==null){stop();return;}if(!current)return;
if(Number($("time").value)>=Number($("time").max))$("time").value="0";drawTime();$("play").textContent="Pause";
timer=setInterval(()=>{const next=Number($("time").value)+1;if(next>Number($("time").max)){stop();return;}$("time").value=String(next);drawTime();},800);});
$("events").addEventListener("change",()=>load($("events").value));
async function start(){try{const embedded=JSON.parse($("embedded").textContent);if(embedded){const o=document.createElement("option");o.textContent=embedded.manifest.title;o.value=embedded.manifest.historical_event_id;$("events").replaceChildren(o);$("events").disabled=true;display(embedded);return;}
const events=await json("/history/events");$("events").replaceChildren();if(!events.length){$("events").disabled=true;$("status").textContent="No retained historical events. An operator must acquire and prepare an event first.";return;}
events.forEach(e=>{const o=document.createElement("option");o.value=e.historical_event_id;o.textContent=e.event_key;$("events").append(o);});await load(events[0].historical_event_id);}
catch(error){$("status").textContent=error.message;}}
start();
</script></body></html>"""
