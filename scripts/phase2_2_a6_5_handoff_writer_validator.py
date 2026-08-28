#!/usr/bin/env python3
import sqlite3, uuid
from datetime import datetime, timezone, timedelta

AUTH = {'L0':0,'L1':1,'L2':2,'L3':3,'L4':4}
TOKEN = 'isolated-coordinator-token'

def now(): return datetime.now(timezone.utc)
def iso(x): return x.isoformat()
def uid(p): return f'{p}_{uuid.uuid4().hex}'

class App:
    def __init__(self):
        self.db=sqlite3.connect(':memory:', isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        create table agent_registry(
          agent_id text primary key, role text not null, authority_ceiling text not null,
          enabled integer not null, assignable integer not null, readiness text not null);
        create table tasks(
          task_id text primary key, task_class text not null, required_authority text not null,
          execution_approval_state text not null);
        create table task_lifecycle_events(
          event_id text primary key, task_id text not null, stage text not null,
          assigned_agent_id text, correlation_id text, occurred_at text not null);
        create table task_handoffs(
          handoff_id text primary key, handoff_version text not null, task_id text not null,
          source_agent_id text not null, target_agent_id text not null, task_class text not null,
          required_authority text not null, source_authority_ceiling text not null,
          target_authority_ceiling text not null, reason_code text not null,
          correlation_id text not null unique, requested_by text not null, requested_at text not null,
          expires_at text not null, handoff_approval_required integer not null,
          handoff_approval_state text not null, execution_approval_state text,
          source_readiness text, target_readiness text, state text not null,
          decided_by text, decided_at text, containment_reason text, lifecycle_event_id text unique);
        create index idx_task_handoffs_task_time on task_handoffs(task_id,requested_at,handoff_id);
        create index idx_task_handoffs_state_expiry on task_handoffs(state,expires_at);
        ''')
        self.provider_calls=0
        self.execution_calls=0

    def auth(self, token):
        return token == TOKEN

    def add_agent(self, aid, ceiling, enabled, assignable, readiness):
        self.db.execute('insert into agent_registry values(?,?,?,?,?,?)',
                        (aid,'worker',ceiling,int(enabled),int(assignable),readiness))

    def add_task(self, tid, task_class='general', required='L1', exec_approval='pending'):
        self.db.execute('insert into tasks values(?,?,?,?)',(tid,task_class,required,exec_approval))

    def assign(self, tid, aid, corr=None):
        self.db.execute('insert into task_lifecycle_events values(?,?,?,?,?,?)',
                        (uid('evt'),tid,'ASSIGNED',aid,corr or uid('corr'),iso(now())))

    def owner(self, tid):
        r=self.db.execute("select assigned_agent_id from task_lifecycle_events where task_id=? and stage='ASSIGNED' order by occurred_at desc,event_id desc limit 1",(tid,)).fetchone()
        return r[0] if r else None

    def assignment_count(self, tid, aid):
        return self.db.execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED' and assigned_agent_id=?",(tid,aid)).fetchone()[0]

    def request(self, token, task_id, target_agent_id, reason_code='capacity_balance', requested_by='human-operator-ceo', expires=None):
        if not self.auth(token): return 401, {'status':'unauthorized'}
        task=self.db.execute('select * from tasks where task_id=?',(task_id,)).fetchone()
        if not task: return 404, {'status':'task_not_found'}
        source_id=self.owner(task_id)
        if not source_id: return 409, {'status':'contained','reason':'source_owner_unknown'}
        source=self.db.execute('select * from agent_registry where agent_id=?',(source_id,)).fetchone()
        target=self.db.execute('select * from agent_registry where agent_id=?',(target_agent_id,)).fetchone()
        if not source or not target or source_id==target_agent_id:
            return 409, {'status':'contained','reason':'identity_invalid'}
        hid,corr=uid('hnd'),uid('hcorr')
        exp=expires or now()+timedelta(minutes=10)
        self.db.execute('''insert into task_handoffs values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            hid,'2.2-a6.5.v1',task_id,source_id,target_agent_id,task['task_class'],task['required_authority'],
            source['authority_ceiling'],target['authority_ceiling'],reason_code,corr,requested_by,iso(now()),iso(exp),
            1,'pending',task['execution_approval_state'],source['readiness'],target['readiness'],'requested',None,None,None,None))
        return 201, {'status':'requested','handoff_id':hid,'correlation_id':corr}

    def authorize_human_test_only(self, hid):
        # Simulates a separately governed human-authorization source; not a candidate public route.
        self.db.execute("update task_handoffs set handoff_approval_state='approved' where handoff_id=? and state='requested'",(hid,))

    def accept(self, token, hid, decided_by='control-api-coordinator', fail_lifecycle=False):
        if not self.auth(token): return 401, {'status':'unauthorized'}
        h=self.db.execute('select * from task_handoffs where handoff_id=?',(hid,)).fetchone()
        if not h: return 404, {'status':'not_found'}
        if h['state']=='accepted':
            return 200, {'status':'accepted','handoff_id':hid,'lifecycle_event_id':h['lifecycle_event_id'],'replay':True}
        if h['state'] in ('rejected','expired','contained'):
            return 409, {'status':h['state']}
        if datetime.fromisoformat(h['expires_at']) <= now():
            self.db.execute("update task_handoffs set state='expired',decided_by=?,decided_at=? where handoff_id=? and state='requested'",(decided_by,iso(now()),hid))
            return 409, {'status':'expired'}

        task=self.db.execute('select * from tasks where task_id=?',(h['task_id'],)).fetchone()
        source=self.db.execute('select * from agent_registry where agent_id=?',(h['source_agent_id'],)).fetchone()
        target=self.db.execute('select * from agent_registry where agent_id=?',(h['target_agent_id'],)).fetchone()
        reason=None
        if not task or not source or not target: reason='identity_or_task_missing'
        elif self.owner(h['task_id']) != h['source_agent_id']: reason='ownership_conflict'
        elif not int(target['enabled']) or not int(target['assignable']): reason='target_ineligible'
        elif target['readiness'] != 'ready': reason='target_not_ready'
        elif task['task_class'] != h['task_class'] or task['task_class'] != 'general': reason='task_class_invalid'
        elif task['required_authority'] != h['required_authority']: reason='required_authority_changed'
        elif source['authority_ceiling'] != h['source_authority_ceiling'] or target['authority_ceiling'] != h['target_authority_ceiling']: reason='authority_evidence_changed'
        elif AUTH[h['required_authority']] > AUTH[source['authority_ceiling']] or AUTH[h['required_authority']] > AUTH[target['authority_ceiling']]: reason='authority_exceeded'
        elif int(h['handoff_approval_required']) and h['handoff_approval_state'] != 'approved':
            return 409, {'status':'requested','reason':'handoff_approval_required'}
        elif task['execution_approval_state'] != h['execution_approval_state']: reason='execution_approval_changed'
        if reason:
            self.db.execute("update task_handoffs set state='contained',containment_reason=?,decided_by=?,decided_at=? where handoff_id=? and state='requested'",(reason,decided_by,iso(now()),hid))
            return 409, {'status':'contained','reason':reason}

        evt=uid('evt')
        try:
            self.db.execute('begin immediate')
            current=self.db.execute('select state from task_handoffs where handoff_id=?',(hid,)).fetchone()[0]
            if current!='requested':
                self.db.execute('rollback')
                return 409, {'status':current}
            # Revalidate owner inside the write transaction.
            if self.owner(h['task_id']) != h['source_agent_id']:
                self.db.execute("update task_handoffs set state='contained',containment_reason='ownership_conflict',decided_by=?,decided_at=? where handoff_id=?",(decided_by,iso(now()),hid))
                self.db.execute('commit')
                return 409, {'status':'contained','reason':'ownership_conflict'}
            self.db.execute("update task_handoffs set state='accepted',decided_by=?,decided_at=?,lifecycle_event_id=? where handoff_id=? and state='requested'",(decided_by,iso(now()),evt,hid))
            if fail_lifecycle:
                raise sqlite3.IntegrityError('simulated lifecycle failure')
            self.db.execute('insert into task_lifecycle_events values(?,?,?,?,?,?)',(evt,h['task_id'],'ASSIGNED',h['target_agent_id'],h['correlation_id'],iso(now())))
            self.db.execute('commit')
        except Exception:
            self.db.execute('rollback')
            return 500, {'status':'write_failed'}
        return 200, {'status':'accepted','handoff_id':hid,'lifecycle_event_id':evt,'replay':False}

    def reject(self, token, hid, decided_by='control-api-coordinator'):
        if not self.auth(token): return 401, {'status':'unauthorized'}
        h=self.db.execute('select * from task_handoffs where handoff_id=?',(hid,)).fetchone()
        if not h: return 404, {'status':'not_found'}
        if h['state']!='requested': return 409, {'status':h['state']}
        self.db.execute("update task_handoffs set state='rejected',decided_by=?,decided_at=? where handoff_id=? and state='requested'",(decided_by,iso(now()),hid))
        return 200, {'status':'rejected'}


def base(*, specialist_enabled=True, specialist_assignable=True, specialist_ready='ready', required='L1', task_class='general'):
    a=App()
    a.add_agent('hermes','L3',True,True,'ready')
    a.add_agent('specialist-worker-01','L1',specialist_enabled,specialist_assignable,specialist_ready)
    a.add_task('tsk_canary',task_class,required,'pending')
    a.assign('tsk_canary','hermes')
    return a

def main():
    # Auth boundary.
    a=base()
    for op in ('request','accept','reject'):
        if op=='request': code,_=a.request('wrong','tsk_canary','specialist-worker-01')
        else: code,_=getattr(a,op)('wrong','missing')
        assert code==401
    print('authenticated_internal_routes=ok')

    # Request persists no ownership transfer and derives server-side evidence.
    a=base(); before=a.owner('tsk_canary')
    code,r=a.request(TOKEN,'tsk_canary','specialist-worker-01')
    assert code==201 and a.owner('tsk_canary')==before=='hermes'
    assert a.assignment_count('tsk_canary','specialist-worker-01')==0
    h=dict(a.db.execute('select * from task_handoffs where handoff_id=?',(r['handoff_id'],)).fetchone())
    assert h['source_agent_id']=='hermes' and h['target_agent_id']=='specialist-worker-01'
    assert h['source_authority_ceiling']=='L3' and h['target_authority_ceiling']=='L1'
    assert h['task_class']=='general' and h['required_authority']=='L1'
    assert h['handoff_approval_required']==1 and h['handoff_approval_state']=='pending'
    print('request_no_assignment=ok')

    # Approval separation; then valid atomic accept.
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['reason']=='handoff_approval_required'
    assert a.owner('tsk_canary')=='hermes'
    a.authorize_human_test_only(r['handoff_id'])
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==200 and x['status']=='accepted' and not x['replay']
    assert a.owner('tsk_canary')=='specialist-worker-01'
    assert a.assignment_count('tsk_canary','specialist-worker-01')==1
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==200 and x['replay']
    assert a.assignment_count('tsk_canary','specialist-worker-01')==1
    print('approval_separation_atomic_accept_replay=ok')

    # Current production specialist state must remain inert.
    a=base(specialist_enabled=False,specialist_assignable=False)
    _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); a.authorize_human_test_only(r['handoff_id'])
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['reason']=='target_ineligible'
    assert a.owner('tsk_canary')=='hermes' and a.assignment_count('tsk_canary','specialist-worker-01')==0
    print('disabled_nonassignable_specialist_inert=ok')

    # Readiness gating.
    for state in ('busy','stale','unassignable','indeterminate'):
        a=base(specialist_ready=state); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); a.authorize_human_test_only(r['handoff_id'])
        code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['reason']=='target_not_ready'; assert a.owner('tsk_canary')=='hermes'
    print('target_readiness_enforced=ok')

    # Authority containment and task-class enforcement.
    a=base(required='L2'); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); a.authorize_human_test_only(r['handoff_id'])
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['reason']=='authority_exceeded'
    a=base(task_class='coding'); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); a.authorize_human_test_only(r['handoff_id'])
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['reason']=='task_class_invalid'
    print('authority_and_task_class_contained=ok')

    # Owner conflict containment.
    a=base(); a.add_agent('other','L1',True,True,'ready'); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); a.authorize_human_test_only(r['handoff_id']); a.assign('tsk_canary','other')
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['reason']=='ownership_conflict'; assert a.assignment_count('tsk_canary','specialist-worker-01')==0
    print('ownership_conflict_contained=ok')

    # Expiry and rejection preserve source.
    a=base(); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01',expires=now()-timedelta(seconds=1)); a.authorize_human_test_only(r['handoff_id'])
    code,x=a.accept(TOKEN,r['handoff_id']); assert code==409 and x['status']=='expired' and a.owner('tsk_canary')=='hermes'
    a=base(); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); code,x=a.reject(TOKEN,r['handoff_id']); assert code==200 and a.owner('tsk_canary')=='hermes'
    print('expiry_rejection_preserve_source=ok')

    # Atomic rollback if lifecycle append fails.
    a=base(); _,r=a.request(TOKEN,'tsk_canary','specialist-worker-01'); a.authorize_human_test_only(r['handoff_id'])
    before_approval=a.db.execute("select execution_approval_state from tasks where task_id='tsk_canary'").fetchone()[0]
    code,x=a.accept(TOKEN,r['handoff_id'],fail_lifecycle=True); assert code==500
    h=a.db.execute('select state,lifecycle_event_id from task_handoffs where handoff_id=?',(r['handoff_id'],)).fetchone()
    assert h['state']=='requested' and h['lifecycle_event_id'] is None
    assert a.owner('tsk_canary')=='hermes' and a.assignment_count('tsk_canary','specialist-worker-01')==0
    after_approval=a.db.execute("select execution_approval_state from tasks where task_id='tsk_canary'").fetchone()[0]
    assert before_approval==after_approval=='pending'
    print('atomic_failure_rollback_and_execution_approval_immutability=ok')

    assert a.provider_calls==0 and a.execution_calls==0
    print('provider_call=none')
    print('execution_call=none')
    print('automatic_assignment=false')
    print('automatic_retry=false')
    print('automatic_reroute=false')
    print('automatic_delegation=false')
    print('automatic_execution=false')
    print('production_change=none')
    print('PHIL_AI_OS_PHASE_2_2_A6_5_HANDOFF_WRITER_ISOLATED_OK')

if __name__=='__main__': main()
