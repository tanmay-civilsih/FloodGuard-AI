"""Read-only manifest inspection with explicit component absence and readiness."""

QA_VIEWER_HTML = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>FloodGuard-AI · Twin Manifest QA</title>
<style>body{background:#101923;color:#eef4fa;font:16px system-ui;margin:24px auto;max-width:1150px;padding:0 20px}
select,button{font:inherit;padding:8px;max-width:100%}table{border-collapse:collapse;width:100%;margin:20px 0}
td,th{text-align:left;padding:10px;border-bottom:1px solid #486078;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#172535;padding:16px}a{color:#90d5ff}</style>
<h1>Twin Manifest QA</h1><p>Inspect exact static component versions and their evidence.
Missing components remain explicit. Reference twins are synthetic. Final human acceptance is pending.</p>
<label>Twin <select id="products"></select></label> <button id="refresh">Refresh twins</button>
<p id="status" role="status" aria-live="polite">Loading…</p><nav id="links"></nav>
<table><thead><tr><th>Component</th><th>State</th><th>Version / reason</th></tr></thead><tbody id="components"></tbody></table>
<pre id="details"></pre><script>
'use strict';
const el=id=>document.getElementById(id); let generation=0;
function clear(){el('components').replaceChildren();el('links').replaceChildren();el('details').textContent='';}
async function get(url){const response=await fetch(url);if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();}
async function selectTwin(){
  const token=++generation;clear();const id=el('products').value;
  if(!id){el('status').textContent='No stored twins';return;}
  el('status').textContent='Verifying frozen components…';
  const base='/twins/products/'+encodeURIComponent(id);
  try{
    const m=await get(base+'/manifest');if(token!==generation)return;
    el('status').textContent=`${m.evidence_scope} · ${m.hydraulic_readiness} · ${m.vertical_reference_status}`;
    for(const [name,component] of Object.entries(m)){
      if(!name.endsWith('_version')||!component||typeof component!=='object'||!component.status)continue;
      const row=document.createElement('tr');
      for(const text of [name,component.status,component.missing_reason||`${component.source.product_id} · SHA-256 ${component.artifact.sha256}`]){
        const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);
      }el('components').appendChild(row);
    }
    for(const kind of ['manifest','audit']){const a=document.createElement('a');a.href=base+'/'+kind;a.textContent=' Download '+kind+' ';el('links').appendChild(a);}
    el('details').textContent=JSON.stringify({twin_id:m.twin_id,pilot_area:m.pilot_area,horizontal_crs:m.horizontal_crs,
      software_version:m.software_version,software_source_sha256:m.software_source_sha256,
      real_cross_ward_path_available:m.real_cross_ward_path_available,readiness_blockers:m.readiness_blockers,
      final_human_acceptance_pending:m.final_human_acceptance_pending},null,2);
  }catch(error){if(token===generation){clear();el('status').textContent='Unable to verify twin: '+error.message;}}
}
async function refresh(){
  const token=++generation;clear();el('products').replaceChildren();el('status').textContent='Loading twins…';
  try{const products=await get('/twins/products?city_id=kolkata');if(token!==generation)return;
    for(const p of products){const option=document.createElement('option');option.value=p.twin_id;
      option.textContent=`${p.pilot_area_id} · ${p.evidence_scope} · ${p.twin_id}`;el('products').appendChild(option);}
    await selectTwin();
  }catch(error){if(token===generation){clear();el('status').textContent='Unable to load twins: '+error.message;}}
}
el('products').addEventListener('change',selectTwin);el('refresh').addEventListener('click',refresh);refresh();
</script></html>"""
