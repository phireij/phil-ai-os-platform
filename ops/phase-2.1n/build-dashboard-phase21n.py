#!/usr/bin/env python3
import pathlib,sys
if len(sys.argv)!=3: raise SystemExit('usage: build-dashboard-phase21n.py SOURCE_2_1M OUTPUT')
s=pathlib.Path(sys.argv[1]).read_text()

def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}_match_count={n}')
    s=s.replace(old,new,1)

once('READ ONLY · Phase 2.1M','READ ONLY · Phase 2.1N','badge')
once("data = {'schema_version':'2.1m.v1','overall_state':'unknown'", "data = {'schema_version':'2.1n.v1','overall_state':'unknown'", 'fallback_schema')

runtime_card='<section class="card"><h2>Runtime Presence & Workload</h2><div id="runtime">Loading…</div></section>'
readiness_card=runtime_card+'\n<section class="card"><h2>Worker Readiness</h2><div id="readiness">Loading…</div></section>'
once(runtime_card,readiness_card,'readiness_card')

binding="const g=d.governance||{}, gp=g.provenance||{}, ds=d.durable_correlation_summary||{}, links=d.durable_correlations||[], coord=d.coordinator||{}, cs=coord.summary||{}, ar=d.agent_runtime||{}, ap=ar.presence||{}, aw=ar.workload||{}, art=ar.runtime||{}, ag=ar.governance||{};"
new_binding="const g=d.governance||{}, gp=g.provenance||{}, ds=d.durable_correlation_summary||{}, links=d.durable_correlations||[], coord=d.coordinator||{}, cs=coord.summary||{}, ar=d.agent_runtime||{}, ap=ar.presence||{}, aw=ar.workload||{}, art=ar.runtime||{}, ag=ar.governance||{}, wr=d.worker_readiness||{};"
once(binding,new_binding,'readiness_binding')

needle="document.getElementById('runtime').innerHTML=kv('Logical presence',ap.logical_presence??'unknown')+kv('Heartbeat age',ap.heartbeat_age_seconds==null?'unknown':ap.heartbeat_age_seconds+'s')+kv('Runtime',art.running===true?'running':(art.running===false?'stopped':'unknown'))+kv('Restart count',art.restart_count??'unknown')+kv('Active tasks',aw.active_task_count??0)+kv('Workload source',aw.source??'unavailable')+kv('Observation',((ap.heartbeat||{}).observation_type)||'none')+kv('Authority effect',ag.presence_authority_effect??'none')+'<div class=\"meta\">Presence is observational only. It does not grant authority, trigger execution, retry, reroute, or delegation.</div>';"
render=needle+"\n document.getElementById('readiness').innerHTML=kv('Agent',wr.agent_id??'unknown')+kv('Task class scope',wr.task_class_scope??'unknown')+kv('Readiness',wr.readiness??'indeterminate')+kv('Reason',wr.reason_code??'unknown')+kv('Authority effect',wr.authority_effect??'none')+kv('Automatic assignment',wr.automatic_assignment===true?'true':'false')+kv('Automatic execution',wr.automatic_execution===true?'true':'false')+'<div class=\"meta\">Readiness is informational only and grants no authority. It does not assign, approve, execute, retry, reroute, or delegate work.</div>';"
once(needle,render,'readiness_render')

old_footer='No mutation controls are present. Phase 2.1M adds authenticated Hermes runtime presence and durable workload visibility. Presence is observational only and has no authority effect. Existing Control API, approval, execution, monitoring, and backup mechanisms remain authoritative.'
new_footer='No mutation controls are present. Phase 2.1N adds a fail-closed worker-readiness view for explicit future governed assignment decisions. Readiness is informational only and has no authority effect. Existing Control API, human approval, execution, monitoring, and backup mechanisms remain authoritative.'
once(old_footer,new_footer,'footer')

pathlib.Path(sys.argv[2]).write_text(s)
print('dashboard_badge=Phase_2.1N')
print('worker_readiness_card=enabled_read_only')
print('readiness_authority_effect=none')
print('dashboard_mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1N_N5_DASHBOARD_BUILD_OK')
