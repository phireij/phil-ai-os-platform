#!/usr/bin/env python3
import pathlib,sys
if len(sys.argv)!=3: raise SystemExit('usage: build-dashboard-phase21i.py SOURCE_2_1H OUTPUT')
s=pathlib.Path(sys.argv[1]).read_text()
def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}_match_count={n}')
    s=s.replace(old,new,1)
rep('READ ONLY · Phase 2.1H','READ ONLY · Phase 2.1I','badge')
rep("data = {'schema_version':'2.1h.v1','overall_state':'unknown'","data = {'schema_version':'2.1i.v1','overall_state':'unknown'",'default_schema')
rep('PHIL_AI_OS_PHASE_2_1H_READ_ONLY_DASHBOARD_LISTENING','PHIL_AI_OS_PHASE_2_1I_READ_ONLY_DASHBOARD_LISTENING','marker')
rep(
    '<section class="card"><h2>Agents</h2><div id="agents">Loading…</div></section>\n<section class="card"><h2>Tasks & Approvals</h2><div id="approvals">Loading…</div></section>',
    '<section class="card"><h2>Agents</h2><div id="agents">Loading…</div></section>\n<section class="card"><h2>Coordinator</h2><div id="coordinator">Loading…</div></section>\n<section class="card"><h2>Tasks & Approvals</h2><div id="approvals">Loading…</div></section>',
    'coordinator_card',
)
rep(
    ' const g=d.governance||{}, gp=g.provenance||{}, ds=d.durable_correlation_summary||{}, links=d.durable_correlations||[];',
    ' const g=d.governance||{}, gp=g.provenance||{}, ds=d.durable_correlation_summary||{}, links=d.durable_correlations||[], coord=d.coordinator||{}, cs=coord.summary||{};',
    'coordinator_binding',
)
rep(
    " document.getElementById('agents').innerHTML='<ul>'+(d.agents||[]).map(a=>`<li><strong>${esc(a.display_name)}</strong> — ${esc(a.role)} / ${esc(a.authority_level)} / ${esc(a.status)}<br><span class=\"meta\">lifecycle=${esc(a.lifecycle_state)} · task=${esc(a.current_task_id??'none')}</span></li>`).join('')+'</ul>';",
    " document.getElementById('agents').innerHTML='<ul>'+(d.agents||[]).map(a=>`<li><strong>${esc(a.display_name)}</strong> — ${esc(a.role)} / ${esc(a.authority_level)} / ${esc(a.status)}<br><span class=\"meta\">lifecycle=${esc(a.lifecycle_state)} · task=${esc(a.current_task_id??'none')}</span></li>`).join('')+'</ul>';\n document.getElementById('coordinator').innerHTML=kv('Owner',cs.coordinator_owner)+kv('Registry',cs.registry_state)+kv('Registered agents',cs.registered_agent_count)+kv('Plan store',cs.plan_store_state)+kv('Observed plans',cs.plan_count_observed)+kv('Assignment',cs.assignment_semantics)+kv('Planning',cs.planning_semantics)+kv('Mission Control mutation',cs.mission_control_mutation)+'<ul>'+(coord.agent_registry||[]).map(a=>`<li><strong>${esc(a.display_name||a.agent_id)}</strong> — ${esc(a.role)} / ceiling=${esc(a.authority_ceiling)} / enabled=${esc(a.enabled)} / assignable=${esc(a.assignable)}</li>`).join('')+'</ul>';",
    'coordinator_render',
)
rep(
    'No mutation controls are present. Phase 2.1H adds an append-only lifecycle ledger for future genuine canonical tasks. Agent assignment remains explicit-event-only and does not grant execution authority. Existing Control API and human approval mechanisms remain authoritative.',
    'No mutation controls are present. Phase 2.1I adds Control API-owned coordinator registry and planning metadata visibility. Assignment and planning remain explicit authenticated Control API operations and do not grant execution authority. Existing Control API and human approval mechanisms remain authoritative.',
    'footer',
)
pathlib.Path(sys.argv[2]).write_text(s)
print('dashboard_badge=Phase_2.1I')
print('dashboard_coordinator_card=enabled_read_only')
print('dashboard_mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1I_DASHBOARD_BUILD_OK')
