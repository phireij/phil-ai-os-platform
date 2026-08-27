#!/usr/bin/env python3
import pathlib,sys
if len(sys.argv)!=3: raise SystemExit('usage: build-dashboard-phase21m.py SOURCE_2_1I OUTPUT')
s=pathlib.Path(sys.argv[1]).read_text()

def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}_match_count={n}')
    s=s.replace(old,new,1)

once('READ ONLY · Phase 2.1I','READ ONLY · Phase 2.1M','badge')
once("data = {'schema_version':'2.1i.v1','overall_state':'unknown'", "data = {'schema_version':'2.1m.v1','overall_state':'unknown'", 'fallback_schema')

coordinator_card='<section class="card"><h2>Coordinator</h2><div id="coordinator">Loading…</div></section>'
runtime_card=coordinator_card+'\n<section class="card"><h2>Runtime Presence & Workload</h2><div id="runtime">Loading…</div></section>'
once(coordinator_card,runtime_card,'runtime_card')

binding="const g=d.governance||{}, gp=g.provenance||{}, ds=d.durable_correlation_summary||{}, links=d.durable_correlations||[], coord=d.coordinator||{}, cs=coord.summary||{};"
new_binding="const g=d.governance||{}, gp=g.provenance||{}, ds=d.durable_correlation_summary||{}, links=d.durable_correlations||[], coord=d.coordinator||{}, cs=coord.summary||{}, ar=d.agent_runtime||{}, ap=ar.presence||{}, aw=ar.workload||{}, art=ar.runtime||{}, ag=ar.governance||{};"
once(binding,new_binding,'runtime_binding')

needle="document.getElementById('coordinator').innerHTML=kv('Owner',cs.coordinator_owner)+kv('Registry',cs.registry_state)+kv('Registered agents',cs.registered_agent_count)+kv('Plan store',cs.plan_store_state)+kv('Observed plans',cs.plan_count_observed)+kv('Assignment',cs.assignment_semantics)+kv('Planning',cs.planning_semantics)+kv('Mission Control mutation',cs.mission_control_mutation)+'<ul>'+(coord.agent_registry||[]).map(a=>`<li><strong>${esc(a.display_name||a.agent_id)}</strong> — ${esc(a.role)} / ceiling=${esc(a.authority_ceiling)} / enabled=${esc(a.enabled)} / assignable=${esc(a.assignable)}</li>`).join('')+'</ul>';"
runtime_render=needle+"\n document.getElementById('runtime').innerHTML=kv('Logical presence',ap.logical_presence??'unknown')+kv('Heartbeat age',ap.heartbeat_age_seconds==null?'unknown':ap.heartbeat_age_seconds+'s')+kv('Runtime',art.running===true?'running':(art.running===false?'stopped':'unknown'))+kv('Restart count',art.restart_count??'unknown')+kv('Active tasks',aw.active_task_count??0)+kv('Workload source',aw.source??'unavailable')+kv('Observation',((ap.heartbeat||{}).observation_type)||'none')+kv('Authority effect',ag.presence_authority_effect??'none')+'<div class=\"meta\">Presence is observational only. It does not grant authority, trigger execution, retry, reroute, or delegation.</div>';"
once(needle,runtime_render,'runtime_render')

old_footer='No mutation controls are present. Phase 2.1I adds Control API-owned coordinator registry and planning metadata visibility. Assignment and planning remain explicit authenticated Control API operations and do not grant execution authority. Existing Control API and human approval mechanisms remain authoritative.'
new_footer='No mutation controls are present. Phase 2.1M adds authenticated Hermes runtime presence and durable workload visibility. Presence is observational only and has no authority effect. Existing Control API, approval, execution, monitoring, and backup mechanisms remain authoritative.'
once(old_footer,new_footer,'footer')

pathlib.Path(sys.argv[2]).write_text(s)
print('dashboard_badge=Phase_2.1M')
print('runtime_presence_card=enabled_read_only')
print('presence_authority_effect=none')
print('dashboard_mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1M_DASHBOARD_BUILD_OK')
