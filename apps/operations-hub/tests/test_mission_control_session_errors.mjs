import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../mission-control/mission-control.mjs', import.meta.url), 'utf8');
function extract(name, next) {
  const start = source.indexOf(`async function ${name}(`);
  const end = source.indexOf(`\n${next}`, start);
  assert.ok(start >= 0 && end > start);
  return source.slice(start, end);
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
let checks = 0;

for (const stale of [false, true]) {
  const response = deferred();
  const context = vm.createContext({ fetch: () => response.promise });
  vm.runInContext(`
    let conversationEpoch = 1;
    let session = 'original';
    let resets = 0;
    function resetConversationView() { conversationEpoch++; session = null; resets++; }
    ${extract('conversationRequest', 'async function loadConversationMessages')}
    this.start = conversationRequest;
    this.replace = () => { conversationEpoch++; session = 'replacement'; };
    this.inspect = () => ({ session, resets });
  `, context);
  const pending = context.start('/synthetic-only');
  if (stale) context.replace();
  response.resolve({ status: 401 });
  await assert.rejects(pending, /session expired/);
  assert.equal(context.inspect().session, stale ? 'replacement' : null);
  assert.equal(context.inspect().resets, stale ? 0 : 1);
  checks++;
}

for (const phase of ['fetch', 'json']) {
  for (const stale of [false, true]) {
    const delayed = deferred();
    const context = vm.createContext({
      fetch: () => phase === 'fetch'
        ? delayed.promise
        : Promise.resolve({ ok: true, json: () => delayed.promise }),
    });
    vm.runInContext(`
      let conversationEpoch = 0;
      let label = 'original';
      ${extract('loadConversationSession', 'function installConversationConnection')}
      this.start = () => loadConversationSession().catch(error => { label = 'session unavailable: ' + error.message; });
      this.replace = () => { conversationEpoch++; label = 'replacement'; };
      this.label = () => label;
    `, context);
    const pending = context.start();
    await tick();
    if (stale) context.replace();
    delayed.reject(new Error(`late ${phase} failure`));
    await pending;
    assert.equal(context.label(), stale ? 'replacement' : `session unavailable: late ${phase} failure`);
    checks++;
  }
}

// A later successful session must survive an older session's JSON rejection.
{
  const oldBody = deferred();
  let calls = 0;
  const context = vm.createContext({
    fetch: async () => ++calls === 1
      ? { ok: true, json: () => oldBody.promise }
      : { ok: true, json: async () => ({ authenticated: true, csrf_token: 'synthetic-new', conversation_authority: false }) },
    document: { querySelector: () => ({}) },
    setConversationControls() {},
    loadRubySyntheticReview: async () => {},
  });
  vm.runInContext(`
    let conversationEpoch = 0;
    let conversationSession = null;
    let label = '';
    function setConversationState(value) { label = value; }
    ${extract('loadConversationSession', 'function installConversationConnection')}
    this.start = () => loadConversationSession().catch(error => { label = error.message; });
    this.inspect = () => ({ session: conversationSession, label });
  `, context);
  const old = context.start();
  await tick();
  await context.start();
  oldBody.reject(new Error('old session failed'));
  await old;
  assert.equal(context.inspect().session.csrf_token, 'synthetic-new');
  assert.equal(context.inspect().label, 'signed in · storage inactive');
  checks++;
}
// A superseded session must not proceed to the next request in its load chain.
for (let delayedIndex = 0; delayedIndex < 4; delayedIndex++) {
  const delayed = deferred();
  const calls = [];
  const loaderNames = ['loadConversationMessages', 'loadGovernedProposals',
    'loadConversationLifecycle', 'loadCtoHandoffs', 'loadCtoHandoffResults'];
  const dependencies = Object.fromEntries(loaderNames.map((name, index) => [name, async () => {
    calls.push(name);
    if (index === delayedIndex) await delayed.promise;
  }]));
  const context = vm.createContext({
    ...dependencies,
    fetch: async () => ({ ok: true, json: async () => ({ authenticated: true,
      csrf_token: 'synthetic-only', conversation_authority: true }) }),
    conversationRequest: async () => ({ ok: true,
      json: async () => ({ conversations: [{ conversation_id: 'synthetic-conversation' }] }) }),
    document: { querySelector: () => ({}) },
    setConversationControls() {}, setConversationState() {},
    loadRubySyntheticReview: async () => {},
  });
  vm.runInContext(`
    let conversationEpoch = 0, conversationSession = null, activeConversationId = null;
    ${extract('loadConversationSession', 'function installConversationConnection')}
    this.start = loadConversationSession;
    this.replace = () => { conversationEpoch++; conversationSession = null; activeConversationId = null; };
  `, context);
  const pending = context.start();
  await tick();
  context.replace();
  delayed.resolve();
  await pending;
  assert.deepEqual(calls, loaderNames.slice(0, delayedIndex + 1));
  checks++;
}
console.log(`${checks} offline stale-error and 401 regressions passed.`);
