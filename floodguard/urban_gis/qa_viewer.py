QA_VIEWER_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>FloodGuard-AI · Urban GIS QA</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
header{padding:16px 20px;background:#111827;border-bottom:1px solid #334155}
main{padding:18px;display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
section{background:#111827;border:1px solid #334155;border-radius:10px;padding:14px;min-height:180px}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;color:#cbd5e1}
a{color:#7dd3fc}.warn{color:#fbbf24}code{color:#bfdbfe}
</style>
</head>
<body>
<header><strong>FloodGuard-AI · Urban GIS QA</strong><div class="warn">Visual and hydraulic representations are separate. Reference fixtures are not real-pilot acceptance.</div></header>
<main>
<section><h3>Readiness</h3><pre id="readiness">Loading…</pre></section>
<section><h3>Latest package</h3><pre id="product">Loading…</pre></section>
<section><h3>Artifact links</h3><div id="links">Loading…</div></section>
</main>
<script>
(async()=>{
 const readiness=await (await fetch('/urban-gis/readiness?city_id=kolkata')).json();
 document.getElementById('readiness').textContent=JSON.stringify(readiness,null,2);
 const products=await (await fetch('/urban-gis/products?city_id=kolkata')).json();
 const product=products[0];
 document.getElementById('product').textContent=product?JSON.stringify(product,null,2):'No package';
 if(!product){document.getElementById('links').textContent='No artifacts';return;}
 const id=product.urban_gis_id;
 const names=['visual','hydraulic','roof-runoff','qa','audit'];
 document.getElementById('links').innerHTML=names.map(n=>`<p><a href="/urban-gis/products/${id}/${n}" target="_blank">${n}</a></p>`).join('');
})().catch(err=>{document.getElementById('readiness').textContent=String(err)});
</script>
</body>
</html>"""
