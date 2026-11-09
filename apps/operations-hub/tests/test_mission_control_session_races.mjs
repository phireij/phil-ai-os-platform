import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../mission-control/mission-control.mjs',import.meta.url),'utf8');
function extract(name,next) {const start=source.indexOf(`async function ${name}(`);assert.ok(start>=0);return source.slice(start,source.indexOf(`\n${next}`,start));}
function deferred(){let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j});return {promise,resolve,reject};}
const tick=()=>new Promise(r=>setImmediate(r));
let count=0;
for(const stale of [false,true]) {
 const body=deferred();let labels=[];
 const c=vm.createContext({fetch:async()=>({ok:true,json:()=>body.promise}),document:{querySelector:()=>({})},setConversationControls(){},loadRubySyntheticReview:async()=>{},setConversationState(label){labels.push(label)},resetConversationView(){throw Error('unexpected reset')}});
 vm.runInContext(`let conversationEpoch=0;let conversationSession=null;${extract('loadConversationSession','function installConversationConnection')}\nthis.start=loadConversationSession;this.reset=()=>{conversationEpoch++;conversationSession=null;};this.inspect=()=>conversationSession;`,c);
 const pending=c.start();await tick();if(stale)c.reset();body.resolve({authenticated:true,csrf_token:'synthetic-only',conversation_authority:false});await pending;
 assert.equal(c.inspect()?.authenticated,stale?undefined:true);assert.equal(labels.length,stale?0:1);count++;
}
for(const stale of [false,true]) {
 const body=deferred();let rendered=0;
 const c=vm.createContext({conversationRequest:async()=>({ok:true,json:()=>body.promise}),resetRubySyntheticReview(){},renderRubySyntheticReview(){rendered++;}});
 vm.runInContext(`let conversationEpoch=0;let conversationSession={ruby_review_synthetic:true};${extract('loadRubySyntheticReview','function resetConversationView')}\nthis.start=loadRubySyntheticReview;this.reset=()=>{conversationEpoch++;conversationSession=null;};`,c);
 const pending=c.start();await tick();if(stale)c.reset();body.resolve({synthetic:true});await pending;assert.equal(rendered,stale?0:1);count++;
}
for(const fail of [false,true]) {
 const fixture=deferred();let resets=0,labels=0,requests=0;
 const c=vm.createContext({fetch:async()=>({ok:true,json:async()=>({authenticated:true,csrf_token:'synthetic-only',conversation_authority:true})}),document:{querySelector:()=>({})},setConversationControls(){},loadRubySyntheticReview:()=>fixture.promise,setConversationState(){labels++},resetRubySyntheticReview(){resets++},conversationRequest(){requests++;throw Error('stale continuation')},resetConversationView(){}});
 vm.runInContext(`let conversationEpoch=0;let conversationSession=null;${extract('loadConversationSession','function installConversationConnection')}\nthis.start=loadConversationSession;this.reset=()=>{conversationEpoch++;conversationSession=null;};`,c);
 const pending=c.start();await tick();c.reset();if(fail)fixture.reject(Error('delayed failure'));else fixture.resolve();await pending;
 assert.equal(resets,0);assert.equal(labels,0);assert.equal(requests,0);count++;
}
console.log(`${count} offline session/fixture race regressions passed.`);
