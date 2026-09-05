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
      background: rgba(255,255,255,.96); padding: 14px; border-radius: 8px; box-shadow: 0 2px 12px #0003;
      max-height: calc(100% - 52px); overflow: auto; }
    h1 { font-size: 17px; margin: 0 0 8px; } p { margin: 5px 0; font-size: 13px; }
    .ready { color: #137333; font-weight: 700; } .visual { color: #9a6700; font-weight: 700; }
    code { font-size: 11px; overflow-wrap: anywhere; }
    select { width: 100%; margin: 6px 0; } li { font-size: 12px; margin: 5px 0; }
    #details { overflow-wrap: anywhere; } #sampling { font-weight: 600; }
  </style>
</head>
<body>
<div id="map"></div>
<section id="panel">
  <h1>FloodGuard-AI · Terrain QA</h1>
  <label for="product">Terrain product</label>
  <select id="product" disabled><option>Loading…</option></select>
  <p id="status" role="status" aria-live="polite">Loading terrain products…</p>
  <p>Blue: unchanged cells. Orange: lowered cells. Red: raised cells. Purple outlines: separately catalogued multi-level structures. Colours show conditioning deltas, not flood depths.</p>
  <p id="sampling"></p>
  <p>Raw elevation remains immutable. Genuine depressions are not automatically filled, and DSM inputs are not silently converted to DTM.</p>
  <div id="details"></div>
</section>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({container: 'map', style: 'https://demotiles.maplibre.org/style.json', center: [88.369, 22.605], zoom: 14});
map.addControl(new maplibregl.NavigationControl(), 'top-right');
const state = {records: [], readiness: null, request: 0};
const element = id => document.getElementById(id);
const emptyLayer = {type: 'FeatureCollection', features: []};
async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`HTTP ${response.status} while loading terrain data`);
  return response.json();
}
function showError(error) {
  element('status').className = 'visual';
  element('status').textContent = `QA load failed: ${error.message || error}`;
}
function addText(parent, tag, text) {
  const child = document.createElement(tag);
  child.textContent = text;
  parent.appendChild(child);
  return child;
}
function layerBounds(data) {
  if (Array.isArray(data.bbox) && data.bbox.length === 4 && data.bbox.every(Number.isFinite)) {
    const [west, south, east, north] = data.bbox;
    if (west <= east && south <= north) return [[west, south], [east, north]];
  }
  // Historical artifacts have no bbox. Preserve coordinate pairs when walking their polygons.
  const bounds = [Infinity, Infinity, -Infinity, -Infinity];
  function visit(value) {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1])) {
      bounds[0] = Math.min(bounds[0], value[0]); bounds[1] = Math.min(bounds[1], value[1]);
      bounds[2] = Math.max(bounds[2], value[0]); bounds[3] = Math.max(bounds[3], value[1]);
    } else value.forEach(visit);
  }
  data.features.forEach(feature => visit(feature.geometry?.coordinates));
  return bounds.every(Number.isFinite) ? [[bounds[0], bounds[1]], [bounds[2], bounds[3]]] : null;
}
async function selectProduct(id) {
  const request = ++state.request;
  element('status').className = '';
  element('status').textContent = 'Loading selected product…';
  element('details').replaceChildren();
  element('sampling').textContent = '';
  map.getSource('terrain')?.setData(emptyLayer);
  try {
    const record = state.records.find(item => item.terrain_id === id);
    if (!record) throw new Error('Selected terrain product was not found');
    const data = await fetchJson(`/terrain/products/${encodeURIComponent(id)}/qa`);
    if (request !== state.request) return;
    if (map.getSource('terrain')) map.getSource('terrain').setData(data);
    else {
      map.addSource('terrain', {type: 'geojson', data});
      map.addLayer({id:'cells', type:'fill', source:'terrain', filter:['==',['get','feature_kind'],'TERRAIN_CELL'],
        paint:{'fill-color':['case',['<',['coalesce',['get','conditioning_delta_m'],0],0],'#f28e2b',['>',['coalesce',['get','conditioning_delta_m'],0],0],'#e15759','#4e79a7'],'fill-opacity':.45}});
      map.addLayer({id:'structures', type:'line', source:'terrain', filter:['==',['get','feature_kind'],'MULTI_LEVEL_STRUCTURE'],
        paint:{'line-color':'#7b1fa2','line-width':3}});
    }
    const bounds = layerBounds(data);
    if (bounds) map.fitBounds(bounds, {padding: 60});
    const latest = state.records.find(item => item.pilot_area_id === record.pilot_area_id && item.pipeline_version === state.readiness.current_pipeline_version);
    const historical = record.terrain_id !== latest?.terrain_id;
    const ready = ['HYDRAULIC_SCENARIO_READY', 'HYDRAULIC_VALIDATED'].includes(record.readiness_status);
    element('status').className = ready && !historical ? 'ready' : 'visual';
    element('status').textContent = `Selected product: ${record.readiness_status}${historical ? ' — historical; excluded from current readiness gate' : ''}`;
    const sampling = data.sampling;
    element('sampling').textContent = sampling
      ? `Showing ${sampling.displayed_cells} of ${sampling.valid_cells} valid cells. ${sampling.omitted_cells} cells and ${sampling.omitted_intervention_cells} intervention cells omitted. Shown polygons represent individual cells, not aggregated coverage.`
      : 'Historical QA artifact: sampling coverage is unknown; rebuild with the current pipeline.';
    const details = element('details');
    addText(details, 'p', `Pilot: ${record.pilot_area_id} · ${record.width} x ${record.height} cells · ${record.source_surface_type} source`);
    addText(details, 'p', `Pipeline: ${record.pipeline_version}`);
    addText(details, 'p', `Native ${record.native_horizontal_resolution_m} m · computational ${record.computational_resolution_m} m · effective information ${record.effective_information_resolution_m} m`);
    addText(details, 'p', `Vertical quality: ${record.vertical_quality}; ${record.vertical_datum || 'datum unresolved'} (${record.vertical_unit || 'unit unresolved'})`);
    addText(details, 'p', `Computed vertical RMSE: ${record.vertical_rmse_m ?? 'not assessed'} m · controls: ${record.control_point_count}`);
    addText(details, 'p', `Preserved depressions: ${record.preserved_depression_count} · fills: ${record.filled_artifact_count} · removals: ${record.removed_obstruction_count} · multi-level structures: ${record.multi_level_structure_count}`);
    addText(details, 'p', `Source SHA-256: ${record.source_sha256}`);
    addText(details, 'p', `City completion gate: ${state.readiness.completion_gate_passed ? 'passed' : 'pending'} — ${state.readiness.completion_gate_reason}`);
    addText(details, 'p', 'Limitations (scenario readiness is not engineering certification):');
    const limitations = document.createElement('ul');
    [...(record.limitations || []), ...(record.validation_limitations || [])].forEach(text => addText(limitations, 'li', text));
    details.appendChild(limitations);
    const audit = addText(details, 'a', 'Open immutable audit and control observations');
    audit.href = `/terrain/products/${encodeURIComponent(id)}/audit`;
    audit.target = '_blank'; audit.rel = 'noopener';
  } catch (error) {
    if (request === state.request) showError(error);
  }
}
async function loadQa() {
  const city = new URLSearchParams(window.location.search).get('city_id') || 'kolkata';
  const query = `city_id=${encodeURIComponent(city)}`;
  [state.readiness, state.records] = await Promise.all([
    fetchJson(`/terrain/readiness?${query}`), fetchJson(`/terrain/products?${query}`)
  ]);
  if (!state.records.length) throw new Error('No terrain product is available. Build a versioned metric terrain package first.');
  const selector = element('product');
  selector.replaceChildren();
  state.records.forEach(record => {
    const option = addText(selector, 'option', `${record.pilot_area_id} · ${record.readiness_status} · ${record.terrain_id}`);
    option.value = record.terrain_id;
  });
  const selected = state.records.find(record => record.pipeline_version === state.readiness.current_pipeline_version) || state.records[0];
  selector.value = selected.terrain_id;
  selector.disabled = false;
  selector.addEventListener('change', () => selectProduct(selector.value));
  await selectProduct(selected.terrain_id);
}
map.on('load', () => loadQa().catch(showError));
</script>
</body>
</html>"""
