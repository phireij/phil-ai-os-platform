import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../mission-control/mission-control.mjs',import.meta.url),'utf8');
function part(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};}
const tick=()=>new Promise(r=>setImmediate(r));
function harness(response,failRender=false){
 const nodes=new Map(),loads=[],labels=[];
 const node=s=>{if(!nodes.has(s))nodes.set(s,{value:'',disabled:false,handlers:{},addEventListener(k,f){this.handlers[k]=f;},focus(){}});return nodes.get(s);};
 const c=vm.createContext({document:{querySelector:node},conversationRequest:()=>response.promise,loadConversationSession:async()=>{},conversationIdempotencyKey:()=> 'synthetic',renderConversationMessages(){if(failRender)throw Error('render failure');},syncGovernedControls(){},setConversationState:l=>labels.push(l),loadConversationMessages:async(id,epoch)=>loads.push({id,epoch})});
 vm.runInContext(`let conversationEpoch=1;let conversationSession={authenticated:true,conversation_authority:true,csrf_token:'synthetic'};let activeConversationId='original';
 ${part('function setConversationControls(enabled) {','\nfunction syncGovernedControls')}
 ${part('function installConversationConnection() {','\nfunction renderLiveSummary')}
 this.install=installConversationConnection;this.replace=(id,advance=true)=>{if(advance)conversationEpoch++;conversationSession=id?{authenticated:true,conversation_authority:true,csrf_token:'new'}:null;activeConversationId=id;setConversationControls(Boolean(id));};this.id=()=>activeConversationId;`,c);
 c.install();return {c,node,loads,labels};
}
let count=0;
for(const replacement of ['unchanged',null,'replacement','same-epoch'])for(const fail of [false,true]){
 const response=deferred(),body=deferred(),h=harness(response);const pending=h.node('#conversation-new').handlers.click();response.resolve({ok:true,json:()=>body.promise});await tick();
 if(replacement!=='unchanged')h.c.replace(replacement,replacement!=='same-epoch');
 if(fail)body.reject(Error('create failure'));else body.resolve({conversation_id:'created'});await pending;
 assert.equal(h.c.id(),replacement==='unchanged'?(fail?'original':'created'):replacement);assert.equal(h.labels.length,replacement==='unchanged'&&fail?1:0);
 if(replacement===null){assert.equal(h.node('#conversation-message').disabled,true);assert.equal(h.node('#decision-request-button').disabled,true);}count++;
}
for(const replacement of ['unchanged',null,'replacement','same-epoch'])for(const fail of [false,true]){
 const response=deferred(),h=harness(response);h.node('#conversation-message').value='original message';const pending=h.node('#decision-request-button').handlers.click();
 if(replacement!=='unchanged'){h.c.replace(replacement,replacement!=='same-epoch');h.node('#conversation-message').value='new unsent draft';}
 if(fail)response.reject(Error('send failure'));else response.resolve({ok:true});await pending;
 assert.equal(h.node('#conversation-message').value,replacement==='unchanged'?(fail?'original message':''):'new unsent draft');assert.equal(h.labels.length,replacement==='unchanged'&&fail?1:0);assert.deepEqual(h.loads,replacement==='unchanged'&&!fail?[{id:'original',epoch:1}]:[]);count++;
}
{
 const response=deferred(),h=harness(response,true);const pending=h.node('#conversation-new').handlers.click();response.resolve({ok:true,json:async()=>({conversation_id:'created'})});await pending;assert.equal(h.c.id(),'created');assert.deepEqual(h.labels,['create unavailable · render failure']);assert.equal(h.node('#conversation-new').disabled,false);count++;
}
for(const edited of ['a new draft','  same text  ']){
 const response=deferred(),h=harness(response);h.node('#conversation-message').value=edited==='  same text  '?'same text':'old draft';const pending=h.node('#decision-request-button').handlers.click();h.node('#conversation-message').value=edited;response.resolve({ok:true});await pending;assert.equal(h.node('#conversation-message').value,edited);assert.deepEqual(h.loads,[{id:'original',epoch:1}]);count++;
}
console.log(`${count} create/send callback and draft-preservation checks passed.`);
