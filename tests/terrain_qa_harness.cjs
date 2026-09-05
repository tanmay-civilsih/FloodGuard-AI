// Execute the actual inline QA script against a small DOM/MapLibre contract double.
// This is behavior coverage, not a WebGL rendering or CDN integration test.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {script, scenario} = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.disabled = true; }
  set innerHTML(value) { throw new Error('Untrusted metadata must not use innerHTML'); }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return (this.text || '') + this.children.map(child => child.textContent).join(' '); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren() { this.children = []; this.text = ''; }
  addEventListener(name, callback) { this.events[name] = callback; }
}
const nodes = Object.fromEntries(['status', 'details', 'sampling', 'product'].map(id => [id, new Element(id)]));
let map;
class MapDouble {
  constructor() { map = this; this.sources = {}; this.handlers = {}; this.layers = []; }
  addControl() {}
  on(name, callback) { this.handlers[name] = callback; }
  getSource(name) { return this.sources[name]; }
  addSource(name, source) {
    assert.equal(this.sources[name], undefined, 'do not duplicate map sources');
    this.sources[name] = {data: source.data, setData(data) { this.data = data; }};
  }
  addLayer(layer) { this.layers.push(layer); }
  fitBounds(bounds) { assert.ok(bounds.flat().every(Number.isFinite)); this.bounds = bounds; }
}
const malicious = '<img src=x onerror=alert(1)>';
const records = [
  {terrain_id: 'a', pilot_area_id: malicious, pipeline_version: 'v4', readiness_status: 'VISUAL_READY'},
  {terrain_id: 'b', pilot_area_id: 'pilot-b', pipeline_version: 'v4', readiness_status: 'HYDRAULIC_VALIDATED'},
  {terrain_id: 'old', pilot_area_id: malicious, pipeline_version: 'v1', readiness_status: 'HYDRAULIC_VALIDATED'},
].map(record => ({...record, limitations: [malicious], validation_limitations: ['Survey not verified']}));
const data = {
  type: 'FeatureCollection', bbox: [88, 22, 88.5, 22.5],
  sampling: {displayed_cells: 1, valid_cells: 20, omitted_cells: 19, omitted_intervention_cells: 2},
  features: [{geometry: {type: 'Polygon', coordinates: [[[88, 22], [88.5, 22], [88.5, 22.5], [88, 22]]]}}],
};
const requests = [];
let delayNextA = false, finishDelayed;
async function fetchDouble(path) {
  requests.push(path);
  if (scenario === 'http_error') return {ok: false, status: 503};
  let body;
  if (path.startsWith('/terrain/readiness?')) body = {
    current_pipeline_version: 'v4', best_readiness_status: 'HYDRAULIC_VALIDATED',
    completion_gate_passed: true, completion_gate_reason: 'Other pilot is ready',
  };
  else if (path.startsWith('/terrain/products?')) body = scenario === 'empty' ? [] : records;
  else {
    body = {...data, selected: path};
    if (scenario === 'historical') { delete body.bbox; delete body.sampling; }
    if (delayNextA && path.endsWith('/a/qa')) {
      delayNextA = false;
      return new Promise(resolve => { finishDelayed = () => resolve({ok: true, json: async () => body}); });
    }
  }
  return {ok: true, json: async () => body};
}
const context = vm.createContext({
  document: {getElementById: id => nodes[id], createElement: tag => new Element(tag)},
  window: {location: {search: '?city_id=new%20city%26x%3D1'}}, URLSearchParams,
  maplibregl: {Map: MapDouble, NavigationControl: class {}}, fetch: fetchDouble,
});
vm.runInContext(script, context, {timeout: 2000});
(async () => {
  await map.handlers.load();
  if (scenario === 'http_error') {
    assert.match(nodes.status.textContent, /HTTP 503/);
    assert.equal(map.getSource('terrain'), undefined);
  } else if (scenario === 'empty') {
    assert.match(nodes.status.textContent, /No terrain product/);
    assert.equal(nodes.product.disabled, true);
  } else {
    assert.match(nodes.status.textContent, /VISUAL_READY/);
    assert.equal(nodes.status.className, 'visual');
    assert.ok(nodes.details.textContent.includes(malicious), 'metadata is displayed as literal text');
    assert.deepEqual(JSON.parse(JSON.stringify(map.bounds)), [[88, 22], [88.5, 22.5]]);
    assert.ok(requests.includes('/terrain/products?city_id=new%20city%26x%3D1'));
    assert.equal(nodes.product.disabled, false);
    if (scenario === 'historical') {
      assert.match(nodes.sampling.textContent, /coverage is unknown/);
      await vm.runInContext("selectProduct('old')", context);
      assert.match(nodes.status.textContent, /historical; excluded/);
      assert.equal(nodes.status.className, 'visual');
    } else {
      assert.match(nodes.sampling.textContent, /19 cells and 2 intervention cells omitted/);
      if (scenario === 'race') {
        delayNextA = true;
        const slow = vm.runInContext("selectProduct('a')", context);
        await vm.runInContext("selectProduct('b')", context);
        finishDelayed(); await slow;
      } else {
        nodes.product.value = 'b'; await nodes.product.events.change();
      }
      assert.match(nodes.status.textContent, /HYDRAULIC_VALIDATED/);
      assert.equal(map.getSource('terrain').data.selected, '/terrain/products/b/qa');
      assert.equal(map.layers.length, 2);
    }
  }
  process.stdout.write(`PASS ${scenario}\n`);
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
