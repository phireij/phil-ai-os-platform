import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const path = process.env.MC_SOURCE || new URL('../mission-control/mission-control.mjs', import.meta.url);
const source = readFileSync(path, 'utf8');
const start = source.indexOf('async function loadLiveRecords(');
const end = source.indexOf('\nfunction clearAuthenticatedLiveView(', start);
assert(start >= 0 && end > start, 'real source function boundaries found');
const extracted = source.slice(start, end);
const good = (id) => ({ ok: true, status: 200, json: async () => ({ id }) });
const bad = () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('Malformed JSON'); } });
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
function harness(responses) {
  const nodes = new Map();
  const rendered = [];
  const calls = [];
  const context = vm.createContext({
    liveSessionEpoch: 1, liveSessionToken: 'test-token',
    document: { querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, { textContent: 'original', className: 'state-chip safe', disabled: false, listeners: {}, addEventListener(name, cb) { this.listeners[name] = cb; }, click() { this.clicked = true; context.liveSessionEpoch++; context.liveSessionToken = null; } });
      return nodes.get(selector);
    } },
    fetch: async (url, options) => { calls.push({ url, options }); const response = responses[url]; if (response instanceof Error) throw response; return response; },
    renderLiveRecords: (payload, list, state, kind) => { rendered.push({ payload, list, state, kind }); context.document.querySelector(state).textContent = 'ready'; },
  });
  vm.runInContext(extracted, context);
  return { context, rendered, calls, node: (id) => context.document.querySelector(id), load: () => context.loadLiveRecords('test-token', 1), click: () => { context.installLiveRecordsRefresh(); return context.document.querySelector('#live-records-refresh').listeners.click(); } };
}
for (const broken of ['approvals', 'executions']) {
  const healthy = broken === 'approvals' ? 'executions' : 'approvals';
  test(`malformed ${broken} is isolated and healthy ${healthy} renders`, async () => {
    const h = harness({ [`/api/${broken}`]: bad(), [`/api/${healthy}`]: good(healthy) });
    await h.load();
    assert.equal(h.node(`#live-${broken}-state`).textContent, 'unavailable');
    assert.equal(h.node(`#live-${broken}-state`).className, 'state-chip');
    assert.deepEqual(h.rendered.map(x => x.payload.id), [healthy]);
    assert.match(h.node('#live-records-refreshed').textContent, /^Last refreshed /);
  });
  for (const failure of ['network', 'http']) test(`${failure} ${broken} preserves healthy ${healthy}`, async () => {
    const response = failure === 'network' ? new Error('Network down') : { ok: false, status: 503 };
    const h = harness({ [`/api/${broken}`]: response, [`/api/${healthy}`]: good(healthy) });
    await h.load();
    assert.equal(h.node(`#live-${broken}-state`).textContent, 'unavailable');
    assert.deepEqual(h.rendered.map(x => x.payload.id), [healthy]);
  });
}
test('both malformed resources settle as unavailable', async () => {
  const h = harness({ '/api/approvals': bad(), '/api/executions': bad() });
  await h.load();
  assert.equal(h.node('#live-approvals-state').textContent, 'unavailable');
  assert.equal(h.node('#live-executions-state').textContent, 'unavailable');
});
for (const outcome of ['reject', 'resolve']) test(`stale session parse ${outcome} does not mutate new session`, async () => {
  const pending = deferred(); const entered = deferred();
  const h = harness({ '/api/approvals': { ok: true, status: 200, json: () => { entered.resolve(); return pending.promise; } }, '/api/executions': good('executions') });
  const load = h.load();
  await entered.promise;
  h.context.liveSessionEpoch = 2;
  h.context.liveSessionToken = 'new-session';
  h.node('#live-approvals-state').textContent = 'new-session-state';
  h.node('#live-records-refreshed').textContent = 'new-session-timestamp';
  if (outcome === 'reject') pending.reject(new SyntaxError('Old invalid body')); else pending.resolve({ id: 'old' });
  await load;
  assert.equal(h.node('#live-approvals-state').textContent, 'new-session-state');
  assert.equal(h.node('#live-records-refreshed').textContent, 'new-session-timestamp');
  assert.equal(h.rendered.length, 0);
});
test('refresh button recovers after malformed body', async () => {
  const h = harness({ '/api/approvals': bad(), '/api/executions': good('executions') });
  await h.click();
  assert.equal(h.node('#live-records-refresh').disabled, false);
  assert.equal(h.node('#live-records-refresh').textContent, 'Refresh live records');
});
test('refresh finally restores button on an unexpected loader rejection', async () => {
  const h = harness({});
  h.context.loadLiveRecords = async () => { throw new Error('Unexpected renderer failure'); };
  await h.click().catch(() => {});
  assert.equal(h.node('#live-records-refresh').disabled, false);
  assert.equal(h.node('#live-records-refresh').textContent, 'Refresh live records');
});
test('stale refresh completion leaves new session button unchanged', async () => {
  const h = harness({}); const pending = deferred();
  h.context.loadLiveRecords = () => pending.promise;
  const click = h.click();
  h.context.liveSessionEpoch = 2;
  h.node('#live-records-refresh').textContent = 'new-session-button';
  h.node('#live-records-refresh').disabled = true;
  pending.resolve(); await click;
  assert.equal(h.node('#live-records-refresh').textContent, 'new-session-button');
  assert.equal(h.node('#live-records-refresh').disabled, true);
});
test('401 expires active session before parsing or rendering either body', async () => {
  const h = harness({ '/api/approvals': good('approvals'), '/api/executions': { ok: false, status: 401 } });
  await h.load();
  assert.equal(h.node('#live-control-disconnect').clicked, true);
  assert.equal(h.node('#live-control-state').textContent, 'session expired');
  assert.equal(h.rendered.length, 0);
});
