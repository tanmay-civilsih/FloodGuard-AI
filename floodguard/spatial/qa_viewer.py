"""Minimal MapLibre engineering QA viewer for normalized Sequence 4 layers."""

QA_VIEWER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FloodGuard-AI Spatial QA</title>
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@6.7.0/dist/maplibre-gl.css" />
  <style>
    html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
    #app { display: grid; grid-template-columns: 330px 1fr; height: 100%; }
    #sidebar { overflow: auto; padding: 16px; border-right: 1px solid #d6d6d6; background: #fff; }
    #map { min-width: 0; }
    h1 { font-size: 18px; margin: 0 0 8px; }
    .muted { color: #666; font-size: 12px; line-height: 1.4; }
    .status { padding: 9px; margin: 12px 0; border: 1px solid #ddd; border-radius: 6px; }
    .layer { padding: 10px 0; border-top: 1px solid #eee; }
    .layer label { display: flex; gap: 8px; align-items: flex-start; font-weight: 600; }
    .meta { font-size: 11px; color: #666; margin-left: 24px; line-height: 1.45; }
    .pass { color: #176b2c; font-weight: 700; }
    .fail { color: #9b1c1c; font-weight: 700; }
    code { font-size: 11px; }
  </style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <h1>FloodGuard-AI · Spatial QA</h1>
    <div class="muted">
      Sequence 4 MapLibre engineering QA viewer. Normalized engineering layers are served from
      FloodGuard's immutable spatial vault. The basemap is visual context only and is not a
      hydraulic input.
    </div>
    <div id="status" class="status">Loading readiness…</div>
    <div class="muted">
      Supported overlays: wards, catchments, water bodies, future normalized roads/buildings,
      source-map derivatives, reconstructed drainage, and QA/confidence markers when available.
    </div>
    <div id="layers"></div>
  </aside>
  <main id="map"></main>
</div>
<script src="https://unpkg.com/maplibre-gl@6.7.0/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({
  container: 'map',
  style: 'https://demotiles.maplibre.org/style.json',
  center: [88.3639, 22.5726],
  zoom: 10
});
map.addControl(new maplibregl.NavigationControl(), 'top-right');

const categoryColors = {
  WARD_BOUNDARY: '#0057b8',
  CATCHMENT: '#8a2be2',
  WATER_BODY: '#0088cc',
  OPENSTREETMAP: '#555555',
  DRAINAGE_MAP: '#d95f02',
  TRAFFIC: '#7f7f7f'
};

function layerColor(category) {
  return categoryColors[category] || '#333333';
}

function visibility(checked) {
  return checked ? 'visible' : 'none';
}

async function loadQa() {
  const readiness = await fetch('/spatial/readiness?city_id=kolkata').then(r => r.json());
  const status = document.getElementById('status');
  const alignmentClass = readiness.alignment_check_passed ? 'pass' : 'fail';
  const rainfallClass = readiness.rainfall_conservation.passed ? 'pass' : 'fail';
  status.innerHTML = `
    <div><b>Working CRS:</b> <code>${readiness.working_crs}</code></div>
    <div class="${alignmentClass}">Alignment: ${readiness.alignment_check_passed ? 'PASS' : 'NOT READY'}</div>
    <div class="${rainfallClass}">Rainfall conservation: ${readiness.rainfall_conservation.passed ? 'PASS' : 'FAIL'}</div>
    <div class="muted">Normalized layers: ${readiness.normalized_layers}<br/>
    Max round-trip error: ${readiness.max_roundtrip_error_m ?? 'n/a'} m<br/>
    Missing core categories: ${readiness.missing_core_categories.join(', ') || 'none'}</div>`;

  const layers = await fetch('/spatial/layers?city_id=kolkata').then(r => r.json());
  const panel = document.getElementById('layers');
  let west = 180, south = 90, east = -180, north = -90;
  for (const layer of layers) {
    const sourceId = `source-${layer.normalization_id}`;
    const fillId = `fill-${layer.normalization_id}`;
    const lineId = `line-${layer.normalization_id}`;
    const pointId = `point-${layer.normalization_id}`;
    const color = layerColor(layer.source_category);
    const item = document.createElement('div');
    item.className = 'layer';
    item.innerHTML = `<label><input type="checkbox" checked />${layer.source_category} · ${layer.layer_name}</label>
      <div class="meta">features=${layer.feature_count}<br/>
      source=${layer.source_crs} → ${layer.working_crs}<br/>
      round-trip=${layer.max_roundtrip_error_m.toExponential(3)} m<br/>
      vertical=${layer.datum_transform_status}</div>`;
    panel.appendChild(item);

    const bounds = layer.bounds_wgs84;
    west = Math.min(west, bounds[0]); south = Math.min(south, bounds[1]);
    east = Math.max(east, bounds[2]); north = Math.max(north, bounds[3]);

    const data = await fetch(`/spatial/layers/${layer.normalization_id}/geojson`).then(r => r.json());
    map.addSource(sourceId, { type: 'geojson', data });
    map.addLayer({
      id: fillId,
      type: 'fill',
      source: sourceId,
      filter: ['in', ['geometry-type'], ['literal', ['Polygon', 'MultiPolygon']]],
      paint: { 'fill-color': color, 'fill-opacity': 0.16 }
    });
    map.addLayer({
      id: lineId,
      type: 'line',
      source: sourceId,
      paint: { 'line-color': color, 'line-width': 2 }
    });
    map.addLayer({
      id: pointId,
      type: 'circle',
      source: sourceId,
      filter: ['in', ['geometry-type'], ['literal', ['Point', 'MultiPoint']]],
      paint: { 'circle-color': color, 'circle-radius': 5 }
    });
    const checkbox = item.querySelector('input');
    checkbox.addEventListener('change', () => {
      for (const id of [fillId, lineId, pointId]) {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visibility(checkbox.checked));
      }
    });
  }
  if (layers.length && west < east && south < north) {
    map.fitBounds([[west, south], [east, north]], { padding: 40, maxZoom: 14 });
  }
}

map.on('load', () => {
  loadQa().catch(error => {
    document.getElementById('status').innerHTML = `<span class="fail">QA load failed:</span> ${error}`;
    console.error(error);
  });
});
</script>
</body>
</html>
"""
