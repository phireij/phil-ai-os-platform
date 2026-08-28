#!/usr/bin/env python3
import sqlite3, uuid
from datetime import datetime, timezone, timedelta

AUTH={'L0':0,'L1':1,'L2':2,'L3':3,'L4':4}
TERMINAL={'accepted','rejected','expired','contained'}

def now(): return datetime.now(timezone.utc)
def iso(dt): return dt.isoformat()
def uid(p): return f'{p}_{uuid.uuid4().hex}'

class Store:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        create table agents(agent_id text primary key, ceiling text not null, enabled integer not null, assignable integer not null, readiness text not null);
        create table tasks(task_id text primary key, task_class text not null, required_authority text not null, execution_approval_state text not null);
        create table lifecycle(event_id text primary key, task_id text not null, stage text not null, assigned_agent_id text, correlation_id text, occurred_at text not null);
        create table handoffs(handoff_id text primary key, task_id text not null, source_agent_id text not null, target_agent_id text not null, task_class text not null, required_authority text not null, source_ceiling text not null, target_ceiling text not null, correlation_id text not null unique, expires_at text not null, approval_required integer not null, approval_state text not null, execution_approval_snapshot text not null, state text not null, lifecycle_event_id text);
        ''')
    def agent(self,a,c='L3',enabled=1,assignable=1,readiness='ready'):
        self.db.execute('insert into agents values(?,?,?,?,?)',(a,c,enabled,assignable,readiness))
    def task(self,t,cls='general',req='L2',approval='pending'):
        self.db.execute('insert into tasks values(?,?,?,?)',(t,cls,req,approval))
    def assign(self,t,a,corr=None):
        self.db.execute('insert into lifecycle values(?,?,?,?,?,?)',(uid('evt'),t,'ASSIGNED',a,corr or uid('corr'),iso(now())))
    def owner(self,t):
        r=self.db.execute("select assigned_agent_id from lifecycle where task_id=? and stage='ASSIGNED' order by occurred_at desc,event_id desc limit 1",(t,)).fetchone()
        return r[0] if r else None
    def count_assign(self,t,a):
        return self.db.execute("select count(*) from lifecycle where task_id=? and stage='ASSIGNED' and assigned_agent_id=?",(t,a)).fetchone()[0]

def request(s, task_id, source, target, *, approval_required=False, approval_state='not_required', expires=None):
    task=s.db.execute('select * from tasks where task_id=?',(task_id,)).fetchone()
    src=s.db.execute('select * from agents where agent_id=?',(source,)).fetchone()
    tgt=s.db.execute('select * from agents where agent_id=?',(target,)).fetchone()
    if not task or not src or not tgt: return None,'contained'
    hid,corr=uid('hnd'),uid('hcorr')
    s.db.execute('insert into handoffs values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        hid,task_id,source,target,task['task_class'],task['required_authority'],src['ceiling'],tgt['ceiling'],corr,
        iso(expires or (now()+timedelta(minutes=10))),int(approval_required),approval_state,task['execution_approval_state'],'requested',None))
    return hid,'requested'

def accept(s,hid):
    h=s.db.execute('select * from handoffs where handoff_id=?',(hid,)).fetchone()
    if not h: return 'contained'
    if h['state'] in TERMINAL: return h['state']
    task=s.db.execute('select * from tasks where task_id=?',(h['task_id'],)).fetchone()
    src=s.db.execute('select * from agents where agent_id=?',(h['source_agent_id'],)).fetchone()
    tgt=s.db.execute('select * from agents where agent_id=?',(h['target_agent_id'],)).fetchone()
    reason=None
    if not task or not src or not tgt: reason='identity_missing'
    elif s.owner(h['task_id']) != h['source_agent_id']: reason='ownership_conflict'
    elif not src['enabled'] or not tgt['enabled'] or not tgt['assignable']: reason='registry_ineligible'
    elif h['source_agent_id']==h['target_agent_id']: reason='same_agent'
    elif task['task_class'] != h['task_class'] or task['task_class'] != 'general': reason='task_class_invalid'
    elif task['required_authority'] != h['required_authority']: reason='authority_requirement_changed'
    elif src['ceiling'] != h['source_ceiling'] or tgt['ceiling'] != h['target_ceiling']: reason='authority_evidence_changed'
    elif AUTH[h['required_authority']] > AUTH[src['ceiling']] or AUTH[h['required_authority']] > AUTH[tgt['ceiling']]: reason='authority_exceeded'
    elif tgt['readiness'] != 'ready': reason='target_not_ready'
    elif datetime.fromisoformat(h['expires_at']) <= now():
        s.db.execute("update handoffs set state='expired' where handoff_id=?",(hid,)); return 'expired'
    elif h['approval_required'] and h['approval_state'] != 'approved': reason='handoff_approval_missing'
    elif task['execution_approval_state'] != h['execution_approval_snapshot']: reason='execution_approval_changed'
    if reason:
        s.db.execute("update handoffs set state='contained' where handoff_id=?",(hid,)); return 'contained'
    with s.db:
        current=s.db.execute('select state,lifecycle_event_id from handoffs where handoff_id=?',(hid,)).fetchone()
        if current['state'] != 'requested': return current['state']
        evt=uid('evt')
        s.db.execute('insert into lifecycle values(?,?,?,?,?,?)',(evt,h['task_id'],'ASSIGNED',h['target_agent_id'],h['correlation_id'],iso(now())))
        s.db.execute("update handoffs set state='accepted', lifecycle_event_id=? where handoff_id=? and state='requested'",(evt,hid))
    return 'accepted'

def reject(s,hid):
    s.db.execute("update handoffs set state='rejected' where handoff_id=? and state='requested'",(hid,))
    return s.db.execute('select state from handoffs where handoff_id=?',(hid,)).fetchone()[0]

def base(target_ceiling='L3',target_ready='ready',target_enabled=1,target_assignable=1, task_class='general', required='L2'):
    s=Store(); s.agent('source','L3',1,1,'ready'); s.agent('target',target_ceiling,target_enabled,target_assignable,target_ready); s.task('t1',task_class,required,'pending'); s.assign('t1','source'); return s

def assert_case(name,fn): fn(); print(f'{name}=ok')

def run():
    def valid():
        s=base(); before=s.owner('t1'); hid,state=request(s,'t1','source','target'); assert state=='requested' and s.owner('t1')==before=='source'; assert accept(s,hid)=='accepted'; assert s.owner('t1')=='target' and s.count_assign('t1','target')==1; assert accept(s,hid)=='accepted' and s.count_assign('t1','target')==1
    assert_case('valid_explicit_handoff_and_replay_protection',valid)
    def unknown():
        s=base(); hid,state=request(s,'t1','source','missing'); assert hid is None and state=='contained' and s.owner('t1')=='source'
    assert_case('unknown_target_fails_closed',unknown)
    def ineligible():
        for enabled,assignable in [(0,1),(1,0)]:
            s=base(target_enabled=enabled,target_assignable=assignable); hid,_=request(s,'t1','source','target'); assert accept(s,hid)=='contained' and s.owner('t1')=='source'
    assert_case('disabled_or_nonassignable_target_fails_closed',ineligible)
    def readiness():
        for r in ['busy','stale','unassignable','indeterminate']:
            s=base(target_ready=r); hid,_=request(s,'t1','source','target'); assert accept(s,hid)=='contained' and s.owner('t1')=='source'
    assert_case('unready_target_fails_closed',readiness)
    def target_auth():
        s=base(target_ceiling='L1',required='L2'); hid,_=request(s,'t1','source','target'); assert accept(s,hid)=='contained'
    assert_case('target_authority_ceiling_enforced',target_auth)
    def source_auth():
        s=Store(); s.agent('source','L1',1,1,'ready'); s.agent('target','L4',1,1,'ready'); s.task('t1','general','L2','pending'); s.assign('t1','source'); hid,_=request(s,'t1','source','target'); assert accept(s,hid)=='contained' and s.owner('t1')=='source'
    assert_case('source_cannot_escalate_via_handoff',source_auth)
    def cls():
        s=base(task_class='coding'); hid,_=request(s,'t1','source','target'); assert accept(s,hid)=='contained'
    assert_case('non_general_scope_fails_closed',cls)
    def approval():
        for st in ['pending','denied','expired']:
            s=base(); hid,_=request(s,'t1','source','target',approval_required=True,approval_state=st); assert accept(s,hid)=='contained'
        s=base(); hid,_=request(s,'t1','source','target',approval_required=True,approval_state='approved'); assert accept(s,hid)=='accepted'
    assert_case('handoff_approval_enforced',approval)
    def expiry():
        s=base(); hid,_=request(s,'t1','source','target',expires=now()-timedelta(seconds=1)); assert accept(s,hid)=='expired' and s.owner('t1')=='source'
    assert_case('expiry_preserves_source',expiry)
    def conflict():
        s=base(); hid,_=request(s,'t1','source','target'); s.assign('t1','other'); assert accept(s,hid)=='contained' and s.count_assign('t1','target')==0
    assert_case('ownership_conflict_contained',conflict)
    def rejection():
        s=base(); hid,_=request(s,'t1','source','target'); assert reject(s,hid)=='rejected' and s.owner('t1')=='source' and s.count_assign('t1','target')==0
    assert_case('rejection_preserves_source',rejection)
    def approval_immutability():
        s=base(); hid,_=request(s,'t1','source','target'); before=s.db.execute('select execution_approval_state from tasks where task_id="t1"').fetchone()[0]; accept(s,hid); after=s.db.execute('select execution_approval_state from tasks where task_id="t1"').fetchone()[0]; assert before==after=='pending'
    assert_case('execution_approval_not_mutated',approval_immutability)
    print('provider_call=none')
    print('execution_call=none')
    print('production_change=none')
    print('authority_expansion=none')
    print('PHIL_AI_OS_PHASE_2_2_A2_ISOLATED_HANDOFF_CONTRACT_OK')

if __name__=='__main__': run()
