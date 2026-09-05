"""MapLibre engineering QA page for conditioned terrain products."""

QA_VIEWER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FloodGuard-AI · Terrain QA</title>
  <link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
  <style>
    html, body { height: 100%; margin: 0; font-family: system-ui, sans-serif; }
    #map { position: absolute; inset: 0; }
    #panel { position: absolute; z-index: 2; top: 12px; left: 12px; width: min(430px, calc(100% - 48px));
      background: rgba(255,255,255,.96); padding: 14px; border-radius: 8px; box-shadow: 0 2px 12px #0003; }
    h1 { font-size: 17px; margin: 0 0 8px; } p { margin: 5px 0; font-size: 13px; }
    .ready { color: #137333; font-weight: 700; } .visual { color: #9a6700; font-weight: 700; }
    code { font-size: 11px; overflow-wrap: anywhere; }
  </style>
</head>
<body>
<div id="map"></div>
<section id="panel">
  <h1>FloodGuard-AI · Terrain QA</h1>
  <p id="status">Loading terrain products…</p>
  <p>Blue cells show visual elevations; orange cells show explicit hydraulic conditioning deltas. Purple outlines are separately catalogued multi-level structures.</p>
  <p>Raw elevation remains immutable. Genuine depressions are not automatically filled, and DSM inputs are not silently converted to DTM.</p>
  <div id="details"></div>
</section>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({container: 'map', style: 'https://demotiles.maplibre.org/style.json', center: [88.369, 22.605], zoom: 14});
map.addControl(new maplibregl.NavigationControl(), 'top-right');
async function loadQa() {
  const readiness = await fetch('/terrain/readiness?city_id=kolkata').then(r => r.json());
  const records = await fetch('/terrain/products?city_id=kolkata').then(r => r.json());
  if (!records.length) throw new Error('No terrain product is available. Upload an approved metric terrain package first.');
  const record = records[0];
  const data = await fetch(`/terrain/products/${record.terrain_id}/qa`).then(r => r.json());
  map.addSource('terrain', {type: 'geojson', data});
  map.addLayer({id:'cells', type:'fill', source:'terrain', filter:['==',['get','feature_kind'],'TERRAIN_CELL'],
    paint:{'fill-color':['interpolate',['linear'],['coalesce',['get','conditioning_delta_m'],0],-10,'#f28e2b',0,'#4e79a7',10,'#e15759'],'fill-opacity':.45}});
  map.addLayer({id:'structures', type:'line', source:'terrain', filter:['==',['get','feature_kind'],'MULTI_LEVEL_STRUCTURE'],
    paint:{'line-color':'#7b1fa2','line-width':3}});
  const allCoordinates = data.features.flatMap(feature => feature.geometry.coordinates.flat(2));
  if (allCoordinates.length) {
    const xs = allCoordinates.map(point => point[0]); const ys = allCoordinates.map(point => point[1]);
    map.fitBounds([[Math.min(...xs),Math.min(...ys)],[Math.max(...xs),Math.max(...ys)]], {padding: 60});
  }
  const statusClass = readiness.best_readiness_status === 'VISUAL_READY' ? 'visual' : 'ready';
  document.getElementById('status').innerHTML = `Readiness: <span class="${statusClass}">${readiness.best_readiness_status}</span>`;
  document.getElementById('details').innerHTML = `<p>${record.width} x ${record.height} cells · ${record.source_surface_type} source</p>
    <p>Native ${record.native_horizontal_resolution_m} m · computational ${record.computational_resolution_m} m · effective information ${record.effective_information_resolution_m} m</p>
    <p>Vertical quality: ${record.vertical_quality}; ${record.vertical_datum || 'datum unresolved'} (${record.vertical_unit || 'unit unresolved'})</p>
    <p>Preserved depressions: ${record.preserved_depression_count} · documented fills: ${record.filled_artifact_count} · multi-level structures: ${record.multi_level_structure_count}</p>
    <p>Source SHA-256:<br><code>${record.source_sha256}</code></p>`;
}
map.on('load', () => loadQa().catch(error => { document.getElementById('status').textContent = `QA load failed: ${error}`; }));
</script>
</body>
</html>"""
