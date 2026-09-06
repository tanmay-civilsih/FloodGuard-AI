"""Offline-capable metric geometry inspection, with explicit immutable product identity."""

QA_VIEWER_HTML = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>FloodGuard-AI · Drain Model QA</title>
<style>
body{margin:0;background:#101923;color:#eef4fa;font:16px system-ui;padding:24px}
main{max-width:1200px;margin:auto}select,button{font:inherit;padding:8px;max-width:100%}
svg{width:100%;height:480px;background:#172535;border:1px solid #486078;margin-top:16px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#172535;padding:16px}
a{color:#90d5ff;margin-right:14px}p{line-height:1.5}.controls{display:flex;gap:12px;flex-wrap:wrap}
</style><main><h1>Drain Model QA</h1>
<p>Inspect stored geometry, direction, parameter gaps, and source lineage.
Reference fixtures use invented engineering values for testing. Real import drafts have no assigned
connectivity or flow direction. Final engineering acceptance is pending Sequence 20.</p>
<div class="controls"><label>Product <select id="products" aria-label="Drain product"></select></label>
<button id="refresh" type="button">Refresh products</button></div>
<p id="status" role="status" aria-live="polite">Loading…</p>
<p>Metric plan view · Ward boundaries: grey · Drains: cyan · Nodes: yellow ·
Exchanges: pink · Labels: grey. Arrows appear only on directed model edges.</p>
<svg id="map" role="img" aria-label="Selected drain model and ward geometry"></svg>
<nav id="links" aria-label="Immutable artifact downloads"></nav>
<pre id="details"></pre></main><script>
'use strict';
const el = id => document.getElementById(id);
const ns = 'http://www.w3.org/2000/svg';
let generation = 0, products = [];
async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}: artifact unavailable or integrity check failed`);
  return r.json();
}
function element(name, attributes) {
  const item = document.createElementNS(ns, name);
  for (const [key,value] of Object.entries(attributes)) item.setAttribute(key, String(value));
  return item;
}
function clear() { el('map').replaceChildren(); el('links').replaceChildren(); el('details').textContent = ''; }
function draw(qa, wards) {
  const features = qa.features, points = [];
  function collect(coords) {
    if (typeof coords[0] === 'number') points.push(coords);
    else coords.forEach(collect);
  }
  features.forEach(f => collect(f.geometry.coordinates));
  if (!points.length) throw new Error('No geometry to inspect');
  const xs = points.map(p=>p[0]), ys = points.map(p=>p[1]);
  const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
  const scale=900/Math.max(xmax-xmin,ymax-ymin,1), point=p=>[(p[0]-xmin)*scale+50,(ymax-p[1])*scale+50];
  el('map').setAttribute('viewBox','0 0 1000 1000');
  function line(coords, color, width) {
    el('map').appendChild(element('polyline',{points:coords.map(p=>point(p).join(',')).join(' '),
      fill:'none',stroke:color,'stroke-width':width}));
  }
  for (const ward of wards.boundaries) {
    const polys=ward.geometry.type==='Polygon'?[ward.geometry.coordinates]:ward.geometry.coordinates;
    for (const poly of polys) for (const ring of poly) line(ring,'#60758b',1.5);
  }
  for (const f of features) {
    const g=f.geometry, kind=f.properties.kind;
    if(g.type==='LineString') {
      line(g.coordinates,'#6ad6f3',3);
      if(f.properties.from && f.properties.to) {
        const b=point(g.coordinates[g.coordinates.length-1]), a=point(g.coordinates[g.coordinates.length-2]);
        const angle=Math.atan2(b[1]-a[1],b[0]-a[0]), size=10;
        el('map').appendChild(element('path',{d:`M ${b[0]-size*Math.cos(angle-.5)} ${b[1]-size*Math.sin(angle-.5)} L ${b[0]} ${b[1]} L ${b[0]-size*Math.cos(angle+.5)} ${b[1]-size*Math.sin(angle+.5)}`,
          stroke:'#6ad6f3',fill:'none','stroke-width':3}));
      }
    } else if(g.type==='Point') {
      const p=point(g.coordinates), exchange=['POINT_INLET','MANHOLE_SURCHARGE','LINEAR_OVERTOP'].includes(kind);
      const dot=element('circle',{cx:p[0],cy:p[1],r:exchange?8:4,fill:exchange?'#ff9dc9':kind==='LABEL'?'#8899aa':'#ffd783'});
      const title=element('title',{}); title.textContent=`${f.id}: ${kind}`; dot.appendChild(title); el('map').appendChild(dot);
    }
  }
}
async function selectProduct() {
  const token=++generation; clear(); el('status').textContent='Loading selected immutable product…';
  const selected=products.find(p=>p.product_id===el('products').value);
  if(!selected) { el('status').textContent='No stored drain products'; return; }
  const base=`/drainage/products/${encodeURIComponent(selected.product_id)}`;
  try {
    const [qa,wards,details]=await Promise.all([get(base+'/qa'),get(base+'/wards'),
      get(base+(selected.product_kind==='IMPORT_DRAFT'?'/draft':'/assessment'))]);
    if(token!==generation) return;
    draw(qa,wards);
    el('status').textContent=`${selected.evidence_scope} · ${details.readiness_status || 'VISUAL_ONLY'} · ${selected.working_crs}`;
    el('details').textContent=JSON.stringify({product_id:selected.product_id,fingerprint:selected.fingerprint,
      pipeline:selected.pipeline_version,assessment:details},null,2);
    for(const kind of Object.keys(selected.artifacts)) {
      const a=document.createElement('a'); a.href=base+'/'+encodeURIComponent(kind); a.textContent=kind;
      el('links').appendChild(a);
    }
  } catch(error) { if(token===generation) { clear(); el('status').textContent=`Unable to inspect product: ${error.message}`; } }
}
async function refresh() {
  const token=++generation; clear(); el('products').replaceChildren(); el('status').textContent='Loading products…';
  try {
    const result=await get('/drainage/products?city_id=kolkata');
    if(token!==generation) return;
    products=result;
    for(const p of products) {
      const option=document.createElement('option'); option.value=p.product_id;
      option.textContent=`${p.pilot_area_id} · ${p.product_kind} · ${p.product_id}`;
      el('products').appendChild(option);
    }
    await selectProduct();
  } catch(error) { if(token===generation) { clear(); el('status').textContent=`Unable to load products: ${error.message}`; } }
}
el('products').addEventListener('change',selectProduct);
el('refresh').addEventListener('click',refresh);
refresh();
</script></html>"""
