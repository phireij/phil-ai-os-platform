import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const sourcePath=process.env.MC_SOURCE || new URL('../mission-control/mission-control.mjs', import.meta.url);
const source=fs.readFileSync(sourcePath,'utf8');
const start=source.indexOf('async function loadLiveRecords(');
const end=source.indexOf('\nfunction clearAuthenticatedLiveView(',start);
assert(start>=0 && end>start);
const extracted=source.slice(start,end);
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
const ok=(id)=>({status:200,ok:true,json:async()=>({id})});
const bad=(status=503)=>({status,ok:false,json:()=>assert.fail('failed HTTP body must not parse')});
function harness(){
 const nodes=new Map(),calls=[],renders=[];let clock=0,disconnects=0;
 const context=vm.createContext({liveSessionToken:'token',liveSessionEpoch:1,liveRecordsRequestSequence:0,Date:class{toLocaleString(){return `clock-${++clock}`;}},document:{querySelector(selector){
  if(!nodes.has(selector))nodes.set(selector,{textContent:'initial',className:'state-chip safe',disabled:false,listeners:{},addEventListener(event,cb){this.listeners[event]=cb;},click(){if(selector==='#live-control-disconnect'){disconnects++;context.liveSessionEpoch++;context.liveSessionToken=null;}else return this.listeners.click();}});
  return nodes.get(selector);
 }},fetch(url){const pending=deferred();calls.push({url,...pending});return pending.promise;},renderLiveRecords(payload,list,state){renders.push({id:payload.id,list});context.document.querySelector(list).payload=payload.id;context.document.querySelector(state).textContent='loaded';}});
 vm.runInContext(extracted,context);context.installLiveRecordsRefresh();
 const node=selector=>context.document.querySelector(selector);
 return {context,calls,renders,node,get disconnects(){return disconnects;},load:()=>context.loadLiveRecords('token',1),manual:()=>node('#live-records-refresh').click(),resolve(offset,id){calls[offset].resolve(ok(`${id}-approvals`));calls[offset+1].resolve(ok(`${id}-executions`));},snapshot(){return JSON.stringify([...nodes].map(([key,node])=>[key,node.textContent,node.className,node.disabled,node.payload]));}};
}
function assertNew(h){assert.equal(h.node('#live-approvals-list').payload,'new-approvals');assert.equal(h.node('#live-executions-list').payload,'new-executions');assert.equal(h.disconnects,0);}
for(const olderKind of ['success','http','network','401'])test(`older ${olderKind} headers cannot overwrite completed new request or its timestamp`,async()=>{
 const h=harness();const old=h.load(),fresh=h.load();h.resolve(2,'new');await fresh;const before=h.snapshot();
 if(olderKind==='success')h.resolve(0,'old');
 else if(olderKind==='network'){h.calls[0].reject(new Error('network'));h.calls[1].reject(new Error('network'));}
 else{h.calls[0].resolve(bad(olderKind==='401'?401:503));h.calls[1].resolve(bad(503));}
 await old;assertNew(h);assert.equal(h.snapshot(),before);
});
for(const resource of [0,1])for(const outcome of ['resolve','reject'])test(`older ${resource===0?'approval':'execution'} body ${outcome} cannot change newer UI or timestamp`,async()=>{
 const h=harness(),body=deferred(),entered=deferred();const old=h.load();
 h.calls[resource].resolve({ok:true,status:200,json(){entered.resolve();return body.promise;}});
 h.calls[1-resource].resolve(ok('old-other'));await entered.promise;
 const fresh=h.load();h.resolve(2,'new');await fresh;const before=h.snapshot();
 if(outcome==='resolve')body.resolve({id:'old-body'});else body.reject(new SyntaxError('bad JSON'));
 await old;assertNew(h);assert.equal(h.snapshot(),before);
});
for(const failure of ['http','network','body'])test(`newest ${failure} failure stays authoritative when older success finishes`,async()=>{
 const h=harness();const old=h.load(),fresh=h.load();
 for(const i of [2,3]){if(failure==='network')h.calls[i].reject(new Error('network'));else if(failure==='http')h.calls[i].resolve(bad());else h.calls[i].resolve({ok:true,status:200,json:async()=>{throw new SyntaxError('bad JSON');}});}
 await fresh;assert.equal(h.node('#live-approvals-state').textContent,'unavailable');assert.equal(h.node('#live-executions-state').textContent,'unavailable');const before=h.snapshot();h.resolve(0,'old');await old;assert.equal(h.snapshot(),before);assert.equal(h.renders.length,0);
});
for(const newerMode of ['manual','timer'])test(`overlapping ${newerMode==='manual'?'timer then manual':'manual then timer'} refresh keeps newer results`,async()=>{
 const h=harness();const old=newerMode==='manual'?h.load():h.manual();const fresh=newerMode==='manual'?h.manual():h.load();h.resolve(2,'new');await fresh;assertNew(h);const timestamp=h.node('#live-records-refreshed').textContent;h.resolve(0,'old');await old;assertNew(h);assert.equal(h.node('#live-records-refreshed').textContent,timestamp);assert.equal(h.node('#live-records-refresh').disabled,false);assert.equal(h.node('#live-records-refresh').textContent,'Refresh live records');
});
test('older manual completion may restore its button while newer timer pending but cannot render',async()=>{
 const h=harness();const old=h.manual(),fresh=h.load();h.resolve(0,'old');await old;assert.equal(h.renders.length,0);assert.equal(h.node('#live-records-refresh').disabled,false);assert.equal(h.node('#live-records-refreshed').textContent,'initial');h.resolve(2,'new');await fresh;assertNew(h);
});
for(const resource of [0,1])test(`latest ${resource===0?'approval':'execution'} 401 still expires session before parsing`,async()=>{
 const h=harness();const old=h.load(),fresh=h.manual();h.calls[2+resource].resolve(bad(401));h.calls[3-resource].resolve({ok:true,status:200,json:()=>assert.fail('must not parse before 401')});await fresh;assert.equal(h.disconnects,1);assert.equal(h.context.liveSessionToken,null);assert.equal(h.node('#live-control-state').textContent,'session expired');assert.equal(h.renders.length,0);const before=h.snapshot();h.resolve(0,'old');await old;assert.equal(h.snapshot(),before);
});
test('new session still rejects late old body independently of sequence',async()=>{
 const h=harness(),body=deferred(),entered=deferred();const old=h.load();h.calls[0].resolve({ok:true,status:200,json(){entered.resolve();return body.promise;}});h.calls[1].resolve(ok('old-execution'));await entered.promise;h.context.liveSessionEpoch++;h.context.liveSessionToken='new-token';h.node('#live-records-refreshed').textContent='new-session';const before=h.snapshot();body.resolve({id:'old'});await old;assert.equal(h.snapshot(),before);assert.equal(h.renders.length,0);
});
