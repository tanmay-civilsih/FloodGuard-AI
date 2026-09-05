"""MapLibre engineering QA page for human review of reconstructed drainage."""

QA_VIEWER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FloodGuard-AI · Drainage Reconstruction QA</title>
  <link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
  <style>
    html, body { height: 100%; margin: 0; font-family: system-ui, sans-serif; }
    #map { position: absolute; inset: 0; }
    #panel { position: absolute; z-index: 2; top: 12px; left: 12px; width: min(390px, calc(100% - 48px));
      background: rgba(255,255,255,.96); padding: 14px; border-radius: 8px; box-shadow: 0 2px 12px #0003; }
    h1 { font-size: 17px; margin: 0 0 8px; } p { margin: 5px 0; font-size: 13px; }
    .pending { color: #9a6700; font-weight: 700; } .approved { color: #137333; font-weight: 700; }
    code { font-size: 11px; overflow-wrap: anywhere; }
  </style>
</head>
<body>
<div id="map"></div>
<section id="panel">
  <h1>FloodGuard-AI · Drainage Reconstruction QA</h1>
  <p id="status">Loading reconstructed drainage…</p>
  <p>Red lines: native CAD drain candidates. Cyan points: manhole candidates. Yellow points: preserved drainage labels.</p>
  <p>The basemap is visual context only. Approval requires a human to check alignment, symbology, placement, and NULL engineering attributes.</p>
  <div id="details"></div>
</section>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({container: 'map', style: 'https://demotiles.maplibre.org/style.json', center: [88.369, 22.605], zoom: 14});
map.addControl(new maplibregl.NavigationControl(), 'top-right');
async function loadQa() {
  const records = await fetch('/reconstruction/maps?city_id=kolkata').then(r => r.json());
  if (!records.length) throw new Error('No reconstruction is available.');
  const record = records[0];
  const data = await fetch(`/reconstruction/maps/${record.reconstruction_id}/geojson`).then(r => r.json());
  map.addSource('reconstruction', {type: 'geojson', data});
  map.addLayer({id:'drains', type:'line', source:'reconstruction', filter:['==',['get','feature_kind'],'DRAIN'],
    paint:{'line-color':['match',['get','confidence_band'],'HIGH','#d93025','MEDIUM','#f9ab00','#777'], 'line-width':2.2}});
  map.addLayer({id:'structures', type:'circle', source:'reconstruction', filter:['==',['get','feature_kind'],'STRUCTURE'],
    paint:{'circle-color':'#00bcd4','circle-radius':3,'circle-stroke-color':'#004d57','circle-stroke-width':1}});
  map.addLayer({id:'labels', type:'circle', source:'reconstruction', filter:['==',['get','feature_kind'],'LABEL'],
    paint:{'circle-color':'#fbbc04','circle-radius':2}});
  const bounds = record.bounds_wgs84;
  map.fitBounds([[bounds[0],bounds[1]],[bounds[2],bounds[3]]], {padding: 60});
  const statusClass = record.status === 'APPROVED' ? 'approved' : 'pending';
  document.getElementById('status').innerHTML = `Ward ${record.ward_id}: <span class="${statusClass}">${record.status}</span>`;
  document.getElementById('details').innerHTML = `<p>${record.drain_count} drains · ${record.structure_count} structures · ${record.label_count} labels</p>
    <p>Georeference RMSE: ${record.georeference_rmse_m.toFixed(2)} m (limit ${record.georeference_tolerance_m.toFixed(2)} m)</p>
    <p>Source SHA-256:<br><code>${record.source_sha256}</code></p>`;
}
map.on('load', () => loadQa().catch(error => { document.getElementById('status').textContent = `QA load failed: ${error}`; }));
</script>
</body>
</html>"""

