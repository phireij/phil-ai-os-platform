#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import tempfile

BASE = '/opt/phil-ai-os/mission-control/read-model.py.pre-phase21o'
CONTROL = 'phil-ai-os-core-control-api-1'
HERMES_PRESENCE = pathlib.Path('/var/lib/phil-ai-os/agent-presence/hermes.json')
SPECIALIST_PRESENCE = pathlib.Path('/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json')
SPECIALIST_PUBLIC_KEY = pathlib.Path('/var/lib/phil-ai-os/agent-identities/specialist-worker-01/public.pem')
FRESH_SECONDS = 120
STALE_SECONDS = 300
TERMINAL = {'COMPLETED','SUCCEEDED','FAILED','CANCELLED','DENIED','EXPIRED','REJECTED','CLOSED'}
OPEN = {'RECEIVED','CLASSIFIED','APPROVAL_PENDING','ASSIGNED','PLANNED','EXECUTION_ALLOWED','EXECUTING'}


def run(cmd, timeout=30):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or 'command failed')
    return p.stdout.strip()


def load_base():
    return json.loads(run(['python3', BASE], timeout=40))


def db_snapshot():
    code = r'''import sqlite3,json
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
def rows(q,args=()): return [dict(r) for r in c.execute(q,args).fetchall()]
out={
 'registry':rows('select agent_id,display_name,role,authority_ceiling,enabled,assignable,created_at,source_component from agent_registry order by agent_id'),
 'lifecycle':rows('select event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id from task_lifecycle_events order by occurred_at,event_id'),
 'handoffs':rows('select * from task_handoffs order by requested_at,handoff_id'),
 'approvals':rows('select approval_id,task_id,state,consumed_at,consumed_by,decision_at from approval_requests order by created_at,approval_id'),
 'audits':rows('select id,task_id,approval_id,response_id,outcome,detail,occurred_at from execution_audit order by occurred_at,id'),
}
print(json.dumps(out,sort_keys=True,default=str))'''
    return json.loads(run(['docker','exec',CONTROL,'python3','-c',code], timeout=30))


def parse_time(value):
    if not value:
        return None
    return dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))


def freshness(observed_at, now):
    ts = parse_time(observed_at)
    if ts is None:
        return 'unknown', None
    age = max(0, int((now - ts).total_seconds()))
    if age <= FRESH_SECONDS:
        return 'fresh', age
    if age <= STALE_SECONDS:
        return 'stale', age
    return 'offline', age


def hermes_presence(now):
    if not HERMES_PRESENCE.exists():
        return {'state':'unknown','observed_at':None,'age_seconds':None,'source_component':None,'identity_verified':False,'evidence_complete':False}
    try:
        hb = json.loads(HERMES_PRESENCE.read_text(encoding='utf-8'))
        valid = (
            hb.get('agent_id') == 'hermes' and
            hb.get('observation_type') == 'authenticated_control_api_roundtrip' and
            hb.get('control_api_status') == 'ok'
        )
        state, age = freshness(hb.get('observed_at'), now)
        if not valid:
            state = 'unknown'
        return {
            'state':state,
            'observed_at':hb.get('observed_at'),
            'age_seconds':age,
            'source_component':hb.get('source_component'),
            'observation_type':hb.get('observation_type'),
            'identity_verified':bool(valid),
            'evidence_complete':bool(valid and age is not None),
        }
    except Exception:
        return {'state':'unknown','observed_at':None,'age_seconds':None,'source_component':None,'identity_verified':False,'evidence_complete':False}


def specialist_presence(now):
    if not SPECIALIST_PRESENCE.exists() or not SPECIALIST_PUBLIC_KEY.exists():
        return {'state':'unknown','observed_at':None,'age_seconds':None,'source_component':None,'identity_verified':False,'evidence_complete':False}
    try:
        env = json.loads(SPECIALIST_PRESENCE.read_text(encoding='utf-8'))
        payload = env.get('payload') or {}
        if env.get('signature_algorithm') != 'ed25519' or payload.get('agent_id') != 'specialist-worker-01':
            raise ValueError('identity envelope invalid')
        canonical = json.dumps(payload, sort_keys=True, separators=(',',':')).encode()
        sig = base64.b64decode(env.get('signature_base64',''), validate=True)
        pub_der = subprocess.check_output(['openssl','pkey','-pubin','-in',str(SPECIALIST_PUBLIC_KEY),'-outform','DER'])
        fingerprint = hashlib.sha256(pub_der).hexdigest()
        if fingerprint != env.get('public_key_sha256'):
            raise ValueError('public key fingerprint mismatch')
        with tempfile.TemporaryDirectory(prefix='philaios-a7-verify-') as td:
            msg = pathlib.Path(td) / 'payload.json'
            sigfile = pathlib.Path(td) / 'signature.bin'
            msg.write_bytes(canonical); sigfile.write_bytes(sig)
            subprocess.run([
                'openssl','pkeyutl','-verify','-pubin','-inkey',str(SPECIALIST_PUBLIC_KEY),
                '-sigfile',str(sigfile),'-rawin','-in',str(msg)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state, age = freshness(payload.get('observed_at'), now)
        return {
            'state':state,
            'observed_at':payload.get('observed_at'),
            'age_seconds':age,
            'source_component':'specialist_presence_heartbeat',
            'observation_type':payload.get('observation_type'),
            'identity_verified':True,
            'public_key_sha256':fingerprint,
            'evidence_complete':age is not None,
        }
    except Exception:
        return {'state':'unknown','observed_at':None,'age_seconds':None,'source_component':'specialist_presence_heartbeat','identity_verified':False,'evidence_complete':False}


def hermes_runtime():
    try:
        names = run(['docker','ps','--format','{{.Names}}']).splitlines()
        name = next((n for n in names if n.startswith('hermes-agent-whow')), None)
        if not name:
            return {'type':'execution_worker','container':'absent','running':False,'restart_count':None,'evidence_complete':True}
        return {
            'type':'execution_worker',
            'container':name,
            'running':run(['docker','inspect',name,'--format','{{.State.Running}}']).lower() == 'true',
            'restart_count':int(run(['docker','inspect',name,'--format','{{.RestartCount}}'])),
            'evidence_complete':True,
        }
    except Exception:
        return {'type':'execution_worker','container':'unknown','running':None,'restart_count':None,'evidence_complete':False}


def specialist_runtime():
    p = subprocess.run(['systemctl','is-active','--quiet','phil-ai-os-specialist-worker-01-presence.timer'])
    return {
        'type':'presence_only',
        'presence_timer_active':p.returncode == 0,
        'execution_runtime':'none',
        'evidence_complete':True,
    }


def audit_closure(task_id, approvals, audits):
    aps = [a for a in approvals if a.get('task_id') == task_id]
    aus = [a for a in audits if a.get('task_id') == task_id]
    success = [a for a in aus if a.get('outcome') == 'success' and a.get('response_id')]
    rejection = [a for a in aus if a.get('outcome') in {'approval_rejected','rejected','failed','cancelled'}]
    same = len({a.get('approval_id') for a in aus if a.get('approval_id')}) == 1
    unique = False
    if len(success) == 1:
        rid = success[0].get('response_id')
        unique = sum(1 for a in audits if a.get('response_id') == rid) == 1
    consumed = len(aps) == 1 and aps[0].get('consumed_at') is not None and aps[0].get('consumed_by') is not None
    replay = False
    if len(aus) == 2 and len(success) == 1 and len(rejection) == 1:
        detail = (rejection[0].get('detail') or '').lower()
        replay = 'already_consumed' in detail or 'replay' in detail
    return bool((len(aus) == 1 and len(success) == 1 and unique and same and consumed) or (unique and same and consumed and replay))


def lifecycle_projection(db):
    by_task = {}
    for ev in db['lifecycle']:
        by_task.setdefault(ev['task_id'], []).append(ev)
    accepted = {}
    for h in db['handoffs']:
        if h.get('state') == 'accepted':
            accepted.setdefault(h['task_id'], set()).add((h.get('source_agent_id'), h.get('target_agent_id'), h.get('lifecycle_event_id')))

    registered = {r['agent_id'] for r in db['registry']}
    tasks_by_owner = {aid:[] for aid in registered}
    conflicts = {aid:False for aid in registered}
    task_latest = {}

    for tid, rows in by_task.items():
        rows = sorted(rows, key=lambda r:(r.get('occurred_at') or '', r.get('event_id') or ''))
        owners = []
        owner_events = []
        for ev in rows:
            if ev.get('stage') == 'ASSIGNED' and ev.get('assigned_agent_id'):
                owners.append(ev['assigned_agent_id'])
                owner_events.append(ev)
        latest = rows[-1]
        latest_stage = latest.get('stage')
        task_latest[tid] = latest_stage

        for i in range(len(owners)-1):
            source, target = owners[i], owners[i+1]
            target_event = owner_events[i+1].get('event_id')
            if source != target and (source,target,target_event) not in accepted.get(tid,set()):
                if source in conflicts: conflicts[source] = True
                if target in conflicts: conflicts[target] = True

        owner = owners[-1] if owners else None
        if owner not in tasks_by_owner:
            continue
        evidence_state = 'complete'
        active = False
        if latest_stage in TERMINAL:
            active = False
        elif latest_stage == 'AUDITED':
            if audit_closure(tid, db['approvals'], db['audits']):
                active = False
            else:
                evidence_state = 'indeterminate'
        elif latest_stage in OPEN:
            active = True
        else:
            evidence_state = 'indeterminate'
        tasks_by_owner[owner].append({
            'task_id':tid,
            'latest_stage':latest_stage,
            'active':active if evidence_state == 'complete' else None,
            'evidence_state':evidence_state,
        })
    return tasks_by_owner, conflicts, task_latest


def project_agent(row, presence, runtime, tasks, conflict):
    active = [t for t in tasks if t.get('active') is True]
    incomplete = conflict or any(t.get('evidence_state') != 'complete' for t in tasks)
    if not bool(row.get('enabled')) or not bool(row.get('assignable')):
        readiness, reason = 'unassignable','registry_disabled_or_nonassignable'
    elif incomplete:
        readiness, reason = 'indeterminate','workload_evidence_incomplete_or_conflicting'
    elif not presence.get('evidence_complete') or presence.get('state') == 'unknown':
        readiness, reason = 'indeterminate','presence_evidence_incomplete'
    elif presence.get('state') == 'stale':
        readiness, reason = 'stale','presence_stale'
    elif presence.get('state') == 'offline':
        readiness, reason = 'offline','presence_offline'
    elif active:
        readiness, reason = 'busy','durable_active_workload_present'
    else:
        readiness, reason = 'ready','eligible_fresh_zero_active_workload'
    latest_owned = tasks[-1]['latest_stage'] if tasks else None
    complete = bool(presence.get('evidence_complete') and runtime.get('evidence_complete') and not incomplete)
    return {
        'agent_id':row['agent_id'],
        'display_name':row.get('display_name'),
        'role':row.get('role'),
        'authority_ceiling':row.get('authority_ceiling'),
        'registry':{
            'enabled':bool(row.get('enabled')),
            'assignable':bool(row.get('assignable')),
            'evidence_complete':True,
        },
        'presence':presence,
        'runtime':runtime,
        'workload':{
            'active_task_count':None if incomplete else len(active),
            'active_tasks':None if incomplete else [t for t in active],
            'historical_owned_task_count':len(tasks),
            'latest_owned_stage':latest_owned,
            'evidence_complete':not incomplete,
        },
        'readiness':{
            'state':readiness,
            'reason':reason,
            'grants_authority':False,
        },
        'evidence_complete':complete,
    }


def handoff_projection(db, task_latest, registry_ids):
    lifecycle_by_id = {e.get('event_id'):e for e in db['lifecycle']}
    approvals_by_task = {}
    for a in db['approvals']:
        approvals_by_task.setdefault(a.get('task_id'), []).append(a)
    out=[]
    for h in db['handoffs']:
        ev = lifecycle_by_id.get(h.get('lifecycle_event_id'))
        latest = task_latest.get(h.get('task_id'))
        aps = approvals_by_task.get(h.get('task_id'), [])
        consumed = any(a.get('consumed_at') is not None or a.get('consumed_by') is not None for a in aps)
        essentials = all(h.get(k) for k in ('handoff_id','task_id','source_agent_id','target_agent_id','correlation_id','required_authority','state'))
        link_ok = bool(ev and ev.get('task_id') == h.get('task_id') and ev.get('assigned_agent_id') == h.get('target_agent_id') and ev.get('correlation_id') == h.get('correlation_id'))
        identities_ok = h.get('source_agent_id') in registry_ids and h.get('target_agent_id') in registry_ids
        complete = bool(essentials and link_ok and identities_ok and latest)
        out.append({
            'handoff_id':h.get('handoff_id'),
            'task_id':h.get('task_id'),
            'source_agent_id':h.get('source_agent_id'),
            'target_agent_id':h.get('target_agent_id'),
            'task_class':h.get('task_class'),
            'required_authority':h.get('required_authority'),
            'source_authority_ceiling':h.get('source_authority_ceiling'),
            'target_authority_ceiling':h.get('target_authority_ceiling'),
            'reason_code':h.get('reason_code'),
            'correlation_id':h.get('correlation_id'),
            'state':h.get('state'),
            'handoff_approval_required':bool(h.get('handoff_approval_required')),
            'handoff_approval_state':h.get('handoff_approval_state'),
            'execution_approval_state':h.get('execution_approval_state'),
            'execution_approval_consumed':consumed,
            'requested_at':h.get('requested_at'),
            'decided_at':h.get('decided_at'),
            'lifecycle_event_id':h.get('lifecycle_event_id'),
            'task_latest_stage':latest,
            'active_ownership':bool(h.get('state') == 'accepted' and latest not in TERMINAL and latest != 'AUDITED'),
            'evidence_complete':complete,
        })
    return out


def main():
    now = dt.datetime.now(dt.timezone.utc)
    data = load_base()
    db = db_snapshot()
    registry = {r['agent_id']:r for r in db['registry']}
    tasks_by_owner, conflicts, task_latest = lifecycle_projection(db)

    presence = {
        'hermes':hermes_presence(now),
        'specialist-worker-01':specialist_presence(now),
    }
    runtimes = {
        'hermes':hermes_runtime(),
        'specialist-worker-01':specialist_runtime(),
    }

    agents=[]
    for aid in sorted(registry):
        agents.append(project_agent(
            registry[aid],
            presence.get(aid, {'state':'unknown','identity_verified':False,'evidence_complete':False}),
            runtimes.get(aid, {'type':'unknown','evidence_complete':False}),
            tasks_by_owner.get(aid, []),
            conflicts.get(aid, False),
        ))

    handoffs = handoff_projection(db, task_latest, set(registry))
    evidence_complete = all(a.get('evidence_complete') for a in agents) and all(h.get('evidence_complete') for h in handoffs)

    data['schema_version'] = '2.2-a7.v1'
    data['multi_agent'] = {
        'schema_version':'2.2-a7.multi-agent.v1',
        'evidence_complete':bool(evidence_complete),
        'registered_agent_count':len(agents),
        'agents':agents,
        'handoff_count':len(handoffs),
        'handoffs':handoffs,
        'authority_effect':'none',
    }
    data['agent_runtimes'] = agents
    data['handoffs'] = handoffs
    data['worker_readiness_by_agent'] = [
        {'agent_id':a['agent_id'], **a['readiness']} for a in agents
    ]

    # Preserve legacy singular Hermes fields for dashboard compatibility.
    hermes = next((a for a in agents if a['agent_id'] == 'hermes'), None)
    if hermes:
        data['agent_runtime'] = {
            'schema_version':'2.2-a7.legacy-hermes.v1',
            'agent':registry['hermes'],
            'runtime':hermes['runtime'],
            'presence':{
                'logical_presence':hermes['presence']['state'],
                'heartbeat_age_seconds':hermes['presence'].get('age_seconds'),
                'heartbeat':{
                    'agent_id':'hermes',
                    'observation_type':hermes['presence'].get('observation_type'),
                    'source_component':hermes['presence'].get('source_component'),
                    'observed_at':hermes['presence'].get('observed_at'),
                },
            },
            'workload':{
                'source':'durable_multi_agent_lifecycle_handoff_projection',
                'evidence_complete':hermes['workload']['evidence_complete'],
                'active_task_count':hermes['workload']['active_task_count'],
                'active_tasks':hermes['workload']['active_tasks'],
            },
            'governance':{'presence_authority_effect':'none'},
        }
        data['worker_readiness'] = {
            'schema_version':'2.2-a7.readiness.v1',
            'agent_id':'hermes',
            'task_class_scope':'general',
            'readiness':hermes['readiness']['state'],
            'reason_code':hermes['readiness']['reason'],
            'authority_effect':'none',
            'automatic_assignment':False,
            'automatic_retry':False,
            'automatic_reroute':False,
            'automatic_execution':False,
        }

    coord = data.setdefault('coordinator', {})
    coord['agent_registry'] = db['registry']
    summary = coord.setdefault('summary', {})
    summary['registered_agent_count'] = len(db['registry'])
    summary['registry_state'] = 'durable_agent_registry'
    summary['mission_control_mutation'] = 'disabled_read_only'

    governance = data.setdefault('governance', {})
    governance.update({
        'multi_agent_read_model_authority_effect':'none',
        'mission_control_authority':'read_only_observer',
        'automatic_assignment':False,
        'automatic_retry':False,
        'automatic_reroute':False,
        'automatic_delegation':False,
        'automatic_execution':False,
    })
    print(json.dumps(data, sort_keys=True))


if __name__ == '__main__':
    main()
