#!/usr/bin/env python3
import sqlite3, uuid
from datetime import datetime, timezone, timedelta

AUTH={'L0':0,'L1':1,'L2':2,'L3':3,'L4':4}

def now(): return datetime.now(timezone.utc)
def iso(x=None): return (x or now()).isoformat()
def uid(p): return f'{p}_{uuid.uuid4().hex}'

class Canary:
    def __init__(self):
        self.db=sqlite3.connect(':memory:', isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        create table agent_registry(agent_id text primary key, authority_ceiling text not null, enabled integer not null, assignable integer not null);
        create table tasks(task_id text primary key, task_class text not null, execution_approval_state text not null);
        create table lifecycle(event_id text primary key, task_id text not null, stage text not null, assigned_agent_id text, correlation_id text, occurred_at text not null);
        create table handoffs(handoff_id text primary key, task_id text not null, source_agent_id text not null, target_agent_id text not null, required_authority text not null, correlation_id text not null unique, handoff_approval_state text not null, state text not null, lifecycle_event_id text unique);
        ''')
        self.db.execute("insert into agent_registry values('hermes','L3',1,1)")
        self.db.execute("insert into agent_registry values('specialist-worker-01','L1',0,0)")
        self.provider_calls=0
        self.execution_calls=0
        self.policy=None
        self.readiness=None

    def owner(self, task):
        r=self.db.execute("select assigned_agent_id from lifecycle where task_id=? and stage='ASSIGNED' order by occurred_at desc,event_id desc limit 1",(task,)).fetchone()
        return r[0] if r else None

    def target_assignments(self, task):
        return self.db.execute("select count(*) from lifecycle where task_id=? and stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'",(task,)).fetchone()[0]

    def active_specialist_workload(self):
        rows=self.db.execute("select distinct task_id from lifecycle where assigned_agent_id='specialist-worker-01' and stage='ASSIGNED'").fetchall()
        active=0
        for r in rows:
            t=r[0]
            last=self.db.execute("select stage from lifecycle where task_id=? order by occurred_at desc,event_id desc limit 1",(t,)).fetchone()
            if last and last[0] not in ('COMPLETED','FAILED','CANCELLED','DENIED','EXPIRED'):
                active+=1
        return active

    def make_task(self):
        tid=uid('tsk_a68')
        self.db.execute('insert into tasks values(?,?,?)',(tid,'general','pending'))
        self.db.execute('insert into lifecycle values(?,?,?,?,?,?)',(uid('evt'),tid,'ASSIGNED','hermes',uid('corr'),iso()))
        return tid

    def set_task_policy(self, tid, *, handoff_id=None, authorized=False, required='L1', stale=False):
        self.policy={
            'task_id':tid,'task_class':'general','required_authority':required,
            'source_agent_id':'hermes','target_agent_id':'specialist-worker-01',
            'authorized_by':'CEO','authorization':'APPROVE_PHASE_2_2_A6_8',
            'handoff_id':handoff_id,'handoff_authorized':authorized,
            'expires_at':iso(now()+timedelta(seconds=(-1 if stale else 300))),
        }

    def set_readiness(self, tid, *, target_fresh=True, source_fresh=True, stale=False):
        self.readiness={
            'task_id':tid,'source_agent_id':'hermes','target_agent_id':'specialist-worker-01',
            'source_presence_authenticated':source_fresh,
            'target_presence_signature_verified':target_fresh,
            'generated_at':iso(now()+timedelta(seconds=(-500 if stale else 0))),
        }

    def required_authority(self, tid):
        p=self.policy
        if not p: return None
        if datetime.fromisoformat(p['expires_at']) <= now(): return None
        if p['authorization']!='APPROVE_PHASE_2_2_A6_8' or p['authorized_by']!='CEO': return None
        if p['task_id']!=tid or p['task_class']!='general': return None
        if p['source_agent_id']!='hermes' or p['target_agent_id']!='specialist-worker-01': return None
        return p['required_authority']

    def readiness_state(self, aid, tid):
        row=self.db.execute('select enabled,assignable from agent_registry where agent_id=?',(aid,)).fetchone()
        if not row or not row[0] or not row[1]: return 'unassignable'
        r=self.readiness
        if not r or r['task_id']!=tid: return 'indeterminate'
        if (now()-datetime.fromisoformat(r['generated_at'])).total_seconds()>120: return 'stale'
        if aid=='hermes':
            return 'busy' if r['source_presence_authenticated'] and self.owner(tid)=='hermes' else 'indeterminate'
        if aid=='specialist-worker-01':
            prior=self.db.execute("select count(*) from lifecycle where assigned_agent_id='specialist-worker-01' and stage='ASSIGNED'").fetchone()[0]
            return 'ready' if r['target_presence_signature_verified'] and prior==0 else 'busy'
        return 'indeterminate'

    def enable_specialist(self):
        self.db.execute("update agent_registry set enabled=1,assignable=1 where agent_id='specialist-worker-01' and authority_ceiling='L1'")

    def disable_specialist(self):
        self.db.execute("update agent_registry set enabled=0,assignable=0 where agent_id='specialist-worker-01' and authority_ceiling='L1'")

    def request(self, tid):
        if self.owner(tid)!='hermes': return 409,None
        req=self.required_authority(tid)
        if not req: return 409,None
        src=self.db.execute("select authority_ceiling from agent_registry where agent_id='hermes'").fetchone()[0]
        tgt=self.db.execute("select authority_ceiling from agent_registry where agent_id='specialist-worker-01'").fetchone()[0]
        if AUTH[req]>AUTH[src] or AUTH[req]>AUTH[tgt]: return 409,None
        hid=uid('hnd'); corr=uid('hcorr')
        self.db.execute('insert into handoffs values(?,?,?,?,?,?,?,?,?)',(hid,tid,'hermes','specialist-worker-01',req,corr,'pending','requested',None))
        return 201,hid

    def accept(self, hid):
        h=self.db.execute('select * from handoffs where handoff_id=?',(hid,)).fetchone()
        if not h: return 404
        if h['state']=='accepted': return 200
        if h['state']!='requested': return 409
        if self.owner(h['task_id'])!='hermes': return 409
        req=self.required_authority(h['task_id'])
        if not req or req!=h['required_authority']: return 409
        p=self.policy
        if not p or not p['handoff_authorized'] or p['handoff_id']!=hid: return 409
        if self.readiness_state('hermes',h['task_id']) not in ('busy','ready'): return 409
        if self.readiness_state('specialist-worker-01',h['task_id'])!='ready': return 409
        tgt=self.db.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='specialist-worker-01'").fetchone()
        if not tgt[1] or not tgt[2] or AUTH[req]>AUTH[tgt[0]]: return 409
        evt=uid('evt')
        try:
            self.db.execute('begin immediate')
            if self.owner(h['task_id'])!='hermes': raise RuntimeError('owner changed')
            self.db.execute('insert into lifecycle values(?,?,?,?,?,?)',(evt,h['task_id'],'ASSIGNED','specialist-worker-01',h['correlation_id'],iso()))
            self.db.execute("update handoffs set state='accepted',handoff_approval_state='approved',lifecycle_event_id=? where handoff_id=? and state='requested'",(evt,hid))
            self.db.execute('commit')
        except Exception:
            self.db.execute('rollback'); return 500
        return 200

    def terminalize(self, tid):
        self.db.execute('insert into lifecycle values(?,?,?,?,?,?)',(uid('evt'),tid,'COMPLETED',None,uid('corr'),iso()))


def main():
    # Missing policy is fail-closed.
    c=Canary(); tid=c.make_task(); c.enable_specialist(); c.set_readiness(tid)
    code,hid=c.request(tid); assert code==409 and hid is None
    print('missing_authority_policy_fail_closed=ok')

    # Wrong/stale authority policy is fail-closed.
    for kwargs in ({'required':'L2'},{'stale':True}):
        c=Canary(); tid=c.make_task(); c.enable_specialist(); c.set_readiness(tid); c.set_task_policy(tid,**kwargs)
        code,hid=c.request(tid); assert code==409 and hid is None
    print('authority_scope_and_expiry_enforced=ok')

    # Disabled target remains unassignable even with fresh evidence.
    c=Canary(); tid=c.make_task(); c.set_task_policy(tid); c.set_readiness(tid)
    assert c.readiness_state('specialist-worker-01',tid)=='unassignable'
    print('registry_precedence=ok')

    # Bounded canary: temporary eligibility, request has no assignment, separate human auth,
    # source may be busy, target must be ready, one atomic target assignment, replay idempotent.
    c=Canary(); tid=c.make_task(); c.enable_specialist(); c.set_task_policy(tid); c.set_readiness(tid)
    assert c.readiness_state('hermes',tid)=='busy'
    assert c.readiness_state('specialist-worker-01',tid)=='ready'
    before=c.target_assignments(tid)
    code,hid=c.request(tid); assert code==201 and hid
    assert c.owner(tid)=='hermes' and c.target_assignments(tid)==before
    assert c.db.execute('select handoff_approval_state from handoffs where handoff_id=?',(hid,)).fetchone()[0]=='pending'
    assert c.accept(hid)==409
    c.set_task_policy(tid,handoff_id=hid,authorized=True)
    assert c.accept(hid)==200
    assert c.owner(tid)=='specialist-worker-01'
    assert c.target_assignments(tid)==before+1
    assert c.accept(hid)==200
    assert c.target_assignments(tid)==before+1
    print('one_handoff_atomic_accept_and_replay=ok')

    # Post-canary containment: terminal task, remove evidence, restore disabled/nonassignable.
    c.terminalize(tid); c.policy=None; c.readiness=None; c.disable_specialist()
    reg=c.db.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='specialist-worker-01'").fetchone()
    assert reg[0]=='L1' and reg[1]==0 and reg[2]==0
    assert c.active_specialist_workload()==0
    assert c.provider_calls==0 and c.execution_calls==0
    assert c.db.execute("select count(*) from handoffs where state='accepted'").fetchone()[0]==1
    print('post_canary_containment=ok')
    print('provider_call=none')
    print('execution_call=none')
    print('automatic_assignment=false')
    print('automatic_retry=false')
    print('automatic_reroute=false')
    print('automatic_delegation=false')
    print('automatic_execution=false')
    print('PHIL_AI_OS_PHASE_2_2_A6_8_ISOLATED_CANARY_CONTRACT_OK')

if __name__=='__main__': main()
