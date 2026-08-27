#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-dashboard-phase21g.py SOURCE_2_1F OUTPUT")

src = pathlib.Path(sys.argv[1]).read_text()
repls = [
    ('READ ONLY · Phase 2.1F', 'READ ONLY · Phase 2.1G'),
    ('No mutation controls are present. Canonical task persistence is active for new Phase 2.1F records; historical pre-2.1F rows may remain approval_id-only. Existing Control API and Telegram approval mechanisms remain authoritative.',
     'No mutation controls are present. Phase 2.1G lifecycle visibility is evidence-based: unsupported stages and agent assignment remain explicitly unavailable until durable sources exist. Existing Control API and human approval mechanisms remain authoritative.'),
    ("data = {'schema_version':'2.1f.v1','overall_state':'unknown'", "data = {'schema_version':'2.1g.v1','overall_state':'unknown'"),
    ('PHIL_AI_OS_PHASE_2_1F_READ_ONLY_DASHBOARD_LISTENING', 'PHIL_AI_OS_PHASE_2_1G_READ_ONLY_DASHBOARD_LISTENING'),
]
for old,new in repls:
    if src.count(old) != 1:
        raise SystemExit('anchor_count_failed:'+old[:60]+':'+str(src.count(old)))
    src = src.replace(old,new,1)

old_section = '<section class="card"><h2>Tasks & Approvals</h2><div id="approvals">Loading…</div></section>'
new_section = old_section + '\n<section class="card"><h2>Lifecycle Evidence</h2><div id="lifecycle">Loading…</div></section>'
if src.count(old_section) != 1:
    raise SystemExit('lifecycle_section_anchor_count='+str(src.count(old_section)))
src = src.replace(old_section,new_section,1)

anchor = " document.getElementById('agents').innerHTML='<ul>'+(d.agents||[]).map(a=>`<li><strong>${esc(a.display_name)}</strong> — ${esc(a.role)} / ${esc(a.authority_level)} / ${esc(a.status)}<br><span class=\"meta\">lifecycle=${esc(a.lifecycle_state)} · task=${esc(a.current_task_id??'none')}</span></li>`).join('')+'</ul>';"
insert = anchor + "\n const tq=d.data_quality||{}, tasks=d.tasks||[]; document.getElementById('lifecycle').innerHTML=kv('Provenance',tq.lifecycle_provenance)+kv('Agent assignment',tq.agent_assignment_provenance)+kv('Unsupported stages',(tq.unsupported_lifecycle_stages||[]).join(', ')||'none')+kv('Canonical tasks',tasks.length)+'<ul class=\"links\">'+tasks.slice(0,8).map(t=>`<li><strong class=\"approval-id\">${esc(t.task_id)}</strong><span class=\"meta\">state=${esc(t.lifecycle_state)} · assigned=${esc(t.assigned_agent_id??'unavailable')} · evidence=${esc((t.lifecycle_evidence||[]).map(e=>e.stage).join(' → ')||'none')}</span></li>`).join('')+'</ul>';"
if src.count(anchor) != 1:
    raise SystemExit('agents_js_anchor_count='+str(src.count(anchor)))
src = src.replace(anchor,insert,1)

pathlib.Path(sys.argv[2]).write_text(src)
print('dashboard_badge=Phase_2.1G')
print('dashboard_lifecycle_evidence=enabled')
print('dashboard_assignment_authority=none')
print('dashboard_mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1G_DASHBOARD_BUILD_OK')
