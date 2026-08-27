#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-dashboard-phase21f.py SOURCE OUTPUT")

src = pathlib.Path(sys.argv[1]).read_text()
repls = [
    ('READ ONLY · Phase 2.1E', 'READ ONLY · Phase 2.1F'),
    ('No mutation controls are present. Durable links use approval_id and are not canonical task IDs. Existing Control API and Telegram approval mechanisms remain authoritative.',
     'No mutation controls are present. Canonical task persistence is active for new Phase 2.1F records; historical pre-2.1F rows may remain approval_id-only. Existing Control API and Telegram approval mechanisms remain authoritative.'),
    ("data = {'schema_version':'2.1e.v1','overall_state':'unknown'", "data = {'schema_version':'2.1f.v1','overall_state':'unknown'"),
    ('PHIL_AI_OS_PHASE_2_1E_READ_ONLY_DASHBOARD_LISTENING', 'PHIL_AI_OS_PHASE_2_1F_READ_ONLY_DASHBOARD_LISTENING'),
]
for old,new in repls:
    if src.count(old) != 1:
        raise SystemExit('anchor_count_failed:'+old[:50]+':'+str(src.count(old)))
    src = src.replace(old,new,1)

old = "document.getElementById('durable').innerHTML=kv('Correlation key',ds.correlation_key_type)+kv('Durable approvals observed',ds.approval_row_count_observed)+kv('Audit rows observed',ds.execution_audit_row_count_observed)+kv('Approvals with audit links',ds.linked_approval_count)+kv('Approval-only',ds.approval_only_count)+kv('Link quality',d.data_quality?.durable_link_quality)+'<ul class=\"links\">'+recent.map(x=>`<li><strong class=\"approval-id\">${esc(x.approval_id)}</strong><span class=\"meta\">state=${esc(x.approval?.state)} · audits=${esc(x.execution_audit_count)} · quality=${esc(x.link_quality)}</span></li>`).join('')+'</ul>';"
new = "document.getElementById('durable').innerHTML=kv('Correlation key',ds.correlation_key_type)+kv('Canonical persistence',ds.canonical_task_persistence)+kv('Approvals with task_id',ds.approval_rows_with_task_id)+kv('Audits with task_id',ds.execution_audit_rows_with_task_id)+kv('Canonical links',ds.canonical_link_count)+kv('Task ID mismatches',ds.task_id_mismatch_count)+kv('Durable approvals observed',ds.approval_row_count_observed)+kv('Audit rows observed',ds.execution_audit_row_count_observed)+kv('Approvals with audit links',ds.linked_approval_count)+kv('Approval-only',ds.approval_only_count)+kv('Link quality',d.data_quality?.durable_link_quality)+'<ul class=\"links\">'+recent.map(x=>`<li><strong class=\"approval-id\">${esc(x.canonical_task_id??x.approval_id)}</strong><span class=\"meta\">approval=${esc(x.approval_id)} · state=${esc(x.approval?.state)} · audits=${esc(x.execution_audit_count)} · quality=${esc(x.link_quality)}</span></li>`).join('')+'</ul>';"
if src.count(old) != 1:
    raise SystemExit('durable_panel_anchor_count='+str(src.count(old)))
src = src.replace(old,new,1)

pathlib.Path(sys.argv[2]).write_text(src)
print('dashboard_badge=Phase_2.1F')
print('dashboard_canonical_task_metrics=enabled')
print('dashboard_mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1F_DASHBOARD_BUILD_OK')
