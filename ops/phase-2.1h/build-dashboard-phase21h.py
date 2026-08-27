#!/usr/bin/env python3
import pathlib,sys
if len(sys.argv)!=3:
    raise SystemExit('usage: build-dashboard-phase21h.py SOURCE_2_1G OUTPUT')
s=pathlib.Path(sys.argv[1]).read_text()
def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}_match_count={n}')
    s=s.replace(old,new,1)
rep('READ ONLY · Phase 2.1G','READ ONLY · Phase 2.1H','badge')
rep("data = {'schema_version':'2.1g.v1','overall_state':'unknown'","data = {'schema_version':'2.1h.v1','overall_state':'unknown'",'default_schema')
rep('PHIL_AI_OS_PHASE_2_1G_READ_ONLY_DASHBOARD_LISTENING','PHIL_AI_OS_PHASE_2_1H_READ_ONLY_DASHBOARD_LISTENING','marker')
rep(
    'No mutation controls are present. Phase 2.1G lifecycle visibility is evidence-based: unsupported stages and agent assignment remain explicitly unavailable until durable sources exist. Existing Control API and human approval mechanisms remain authoritative.',
    'No mutation controls are present. Phase 2.1H adds an append-only lifecycle ledger for future genuine canonical tasks. Agent assignment remains explicit-event-only and does not grant execution authority. Existing Control API and human approval mechanisms remain authoritative.',
    'footer',
)
old="kv('Provenance',tq.lifecycle_provenance)+kv('Agent assignment',tq.agent_assignment_provenance)+kv('Unsupported stages',(tq.unsupported_lifecycle_stages||[]).join(', ')||'none')+kv('Canonical tasks',tasks.length)"
new="kv('Provenance',tq.lifecycle_provenance)+kv('Ledger state',tq.lifecycle_ledger_state??'unavailable')+kv('Ledger events',tq.lifecycle_event_count_observed??0)+kv('Agent assignment',tq.agent_assignment_provenance)+kv('Unsupported stages',(tq.unsupported_lifecycle_stages||[]).join(', ')||'none')+kv('Canonical tasks',tasks.length)"
rep(old,new,'lifecycle_metrics')
pathlib.Path(sys.argv[2]).write_text(s)
print('dashboard_badge=Phase_2.1H')
print('dashboard_lifecycle_ledger_metrics=enabled')
print('dashboard_mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1H_DASHBOARD_BUILD_OK')
