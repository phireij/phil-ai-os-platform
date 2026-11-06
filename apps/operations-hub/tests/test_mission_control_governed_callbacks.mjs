import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(process.argv[2] || new URL('../mission-control/mission-control.mjs', import.meta.url), 'utf8');
const start = source.indexOf('function installConversationConnection() {');
const end = source.indexOf('\nfunction renderLiveSummary', start);
assert.ok(start >= 0 && end > start);
const installation = source.slice(start, end);
function deferred() { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise, resolve, reject}; }
const tick = () => new Promise(resolve => setImmediate(resolve));
const forms = { proposal: '#governed-proposal-form', decision: '#governed-decision-form', handoff: '#cto-handoff-form', logout: '#conversation-sign-out' };
const fields = { proposal: ['#proposal-scope', '#proposal-result'], decision: ['#decision-rationale', '#decision-expiry'], handoff: [], logout: [] };
function harness(kind, delayedLoader = -1) {
  const response = deferred(), gate = deferred(), nodes = new Map(), loads = [], labels = [], requests = [];
  let syncs = 0, resets = 0;
  const node = selector => {
    if (!nodes.has(selector)) nodes.set(selector, { value: '', disabled: false, handlers: {}, addEventListener(event, fn) { this.handlers[event] = fn; }, focus() {} });
    return nodes.get(selector);
  };
  const load = name => async (id, epoch) => { loads.push({name,id,epoch}); if (loads.length - 1 === delayedLoader) await gate.promise; };
  const c = vm.createContext({ document: {querySelector: node},
    conversationRequest: (...args) => { requests.push(args); return response.promise; },
    loadConversationSession: async () => {}, conversationIdempotencyKey: () => 'synthetic',
    setConversationState: label => labels.push(label), syncGovernedControls: () => { syncs++; }, setConversationControls: () => { syncs++; },
    loadGovernedProposals: load('proposals'), loadConversationLifecycle: load('lifecycle'), loadCtoHandoffs: load('handoffs'),
    resetConversationView: label => { resets++; labels.push(label); c.replace('reset'); },
  });
  vm.runInContext(`let conversationEpoch = 1; let activeConversationId = 'original'; let conversationSession = { authenticated:true, conversation_authority:true, cto_handoff_recording:true, csrf_token:'synthetic' }; ${installation}
    this.replace = mode => { if(mode !== 'conversation') conversationEpoch++; activeConversationId = mode === 'reset' ? null : 'replacement'; };
    this.id = () => activeConversationId; this.install = installConversationConnection;`, c);
  c.install();
  for (const [selector,value] of Object.entries({'#proposal-source-message':'message','#proposal-scope':'original scope','#proposal-result':'original result','#decision-proposal':'proposal','#decision-rationale':'original rationale','#decision-expiry':'2099-01-01T00:00','#decision-value':'approved','#cto-handoff-proposal':'proposal'})) node(selector).value=value;
  return {c,node,response,gate,loads,labels,requests,stats:()=>({syncs,resets}),run:()=>node(forms[kind]).handlers[kind==='logout'?'click':'submit']({preventDefault(){}})};
}
let passed = 0;
const failures = [];
async function test(name, fn) { try { await fn(); passed++; } catch(error) { failures.push(name + ': ' + error.message); } }
for (const kind of ['proposal','decision','handoff','logout']) {
  // Both success and failure must preserve replacement state. Logout is session-bound, not conversation-bound.
  for (const mode of (kind === 'logout' ? ['epoch','reset'] : ['epoch','conversation','reset'])) {
    for (const fail of [false,true]) await test(`${kind} stale ${mode} ${fail?'error':'success'}`, async () => {
      const h=harness(kind), pending=h.run(); h.c.replace(mode);
      for(const field of fields[kind]) h.node(field).value='new draft';
      if(fail) h.response.reject(Error('late failure')); else h.response.resolve({ok:true});
      await pending;
      assert.equal(h.loads.length,0); assert.equal(h.labels.length,0); assert.deepEqual(h.stats(),{syncs:0,resets:0});
      for(const field of fields[kind]) assert.equal(h.node(field).value,'new draft');
      assert.equal(h.requests.length,1);
    });
  }
  for (const fail of [false,true]) await test(`${kind} current ${fail?'error':'success'}`, async () => {
    const h=harness(kind),pending=h.run();
    if(fail) h.response.reject(Error('current failure')); else h.response.resolve({ok:true});
    await pending; assert.equal(h.labels.length,1); assert.equal(h.requests.length,1);
    if(kind==='logout') assert.equal(h.stats().resets,fail?0:1);
    else { assert.equal(h.stats().syncs,1); assert.equal(h.loads.length,fail?0:2); for(const call of h.loads){ assert.equal(call.id,'original'); assert.equal(call.epoch,1); } }
  });
}
for(const kind of ['proposal','decision','handoff']) for(const index of [0,1]) for(const fail of [false,true]) await test(`${kind} stale reload ${index} ${fail?'error':'success'}`,async()=>{
  const h=harness(kind,index),pending=h.run();h.response.resolve({ok:true});await tick();h.c.replace('epoch');
  if(fail)h.gate.reject(Error('late reload failure'));else h.gate.resolve();await pending;
  assert.equal(h.loads.length,index+1);assert.equal(h.labels.length,0);assert.equal(h.stats().syncs,0);
});
for(const kind of ['proposal','decision']) for(const field of fields[kind]) await test(`${kind} preserve edited ${field}`,async()=>{
  const h=harness(kind),pending=h.run();h.node(field).value='newer text';h.response.resolve({ok:true});await pending;
  assert.equal(h.node(field).value,'newer text');assert.equal(h.labels.length,1);assert.equal(h.loads.length,2);
});
for(const kind of ['proposal','decision','handoff','logout']) await test(`${kind} current HTTP failure`,async()=>{
  const h=harness(kind),pending=h.run();h.response.resolve({ok:false,status:500});await pending;
  assert.equal(h.labels.length,1);assert.equal(h.loads.length,0);assert.equal(h.requests.length,1);assert.equal(h.stats().syncs,1);
});
for(const kind of ['proposal','decision','handoff']) await test(`${kind} current reload failure`,async()=>{
  const h=harness(kind,0),pending=h.run();h.response.resolve({ok:true});await tick();h.gate.reject(Error('current reload failed'));await pending;
  assert.equal(h.labels.length,1);assert.match(h.labels[0],/current reload failed/);assert.equal(h.loads.length,1);assert.equal(h.stats().syncs,1);
});
for(const fail of [false,true]) await test(`logout current session navigation ${fail?'error':'success'}`,async()=>{
  const h=harness('logout'),pending=h.run();h.c.replace('conversation');
  if(fail)h.response.reject(Error('logout failed'));else h.response.resolve({ok:true});await pending;
  assert.equal(h.labels.length,1);assert.equal(h.stats().resets,fail?0:1);assert.equal(h.c.id(),fail?'replacement':null);
});
for(const kind of ['proposal','decision']) await test(`${kind} preserve whitespace edit`,async()=>{
  const h=harness(kind),field=fields[kind][0],original=h.node(field).value,pending=h.run();h.node(field).value=' '+original+' ';h.response.resolve({ok:true});await pending;
  assert.equal(h.node(field).value,' '+original+' ');
});
for(const kind of ['proposal','decision']) await test(`${kind} preserve fields after target selection change`,async()=>{
  const h=harness(kind),original=fields[kind].map(field=>h.node(field).value),pending=h.run();
  h.node(kind==='proposal'?'#proposal-source-message':'#decision-proposal').value='new-target';
  h.response.resolve({ok:true});await pending;
  fields[kind].forEach((field,index)=>assert.equal(h.node(field).value,original[index]));
});
// Use the real sync helper with select-like nodes whose replacement defaults to the first option.
for(const mode of ['preserve','removed','empty']) await test(`real sync selection ${mode}`,async()=>{
  const nodes=new Map();
  const node=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'second',options:[],replaceChildren(...options){this.options=options;this.value=options[0]?.value??'';}});return nodes.get(selector);};
  const a=source.indexOf('function syncGovernedControls() {'),b=source.indexOf('\nfunction renderConversationMessages',a);assert.ok(a>=0&&b>a);
  const ids=mode==='empty'?[]:mode==='removed'?['first']:['first','second'];
  const c=vm.createContext({document:{querySelector:node},Option:function(label,value){this.text=label;this.value=value;},ids});
  vm.runInContext(`let conversationSession={conversation_authority:true,cto_handoff_recording:true};let activeConversationId='original';
    let activeConversationMessages=ids.map(id=>({sender:'ceo',message_id:id,created_at:'2026-01-01'}));
    let activeGovernedProposals=ids.map(id=>({proposal_id:id,scope:'synthetic'}));let recordedDecisionProposalIds=new Set();let approvedDecisionProposalIds=new Set(ids);let activeCtoHandoffs=[];
    ${source.slice(a,b)};syncGovernedControls();`,c);
  for(const selector of ['#proposal-source-message','#decision-proposal','#cto-handoff-proposal'])assert.equal(node(selector).value,mode==='preserve'?'second':mode==='removed'?'first':'');
  for(const selector of ['#proposal-create','#decision-record','#cto-handoff-record'])assert.equal(node(selector).disabled,mode==='empty');
});
for(const [kind,selector] of [['proposal','#proposal-project'],['proposal','#proposal-authority'],['decision','#decision-value']]) await test(`${kind} preserve fields after ${selector} change`,async()=>{
  const h=harness(kind),original=fields[kind].map(field=>h.node(field).value),pending=h.run();h.node(selector).value='changed';h.response.resolve({ok:true});await pending;
  fields[kind].forEach((field,index)=>assert.equal(h.node(field).value,original[index]));
});
console.log(`${passed} governed/logout callback checks passed; ${failures.length} failed.`);
for(const failure of failures)console.error(failure);
if(failures.length)process.exitCode=1;
