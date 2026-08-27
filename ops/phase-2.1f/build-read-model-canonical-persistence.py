#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-read-model-canonical-persistence.py SOURCE OUTPUT")

src = pathlib.Path(sys.argv[1]).read_text()

if src.count('SCHEMA_VERSION = "2.1e.v1"') != 1:
    raise SystemExit("unexpected_schema_version_anchor")
src = src.replace('SCHEMA_VERSION = "2.1e.v1"', 'SCHEMA_VERSION = "2.1f.v1"', 1)

start = src.index('def durable_approval_execution_links(control: str):')
end = src.index('\ndef main():', start)

new_func = r"""def durable_approval_execution_links(control: str):
    # Explicit column allowlists prevent task text, decision notes, link hashes,
    # execution detail, provider responses, or credential material from entering
    # the browser-facing read model. task_id is safe correlation metadata.
    code = r'''import sqlite3,json
c=sqlite3.connect("/app/state/control-plane.db")
c.row_factory=sqlite3.Row
approval_cols={r[1] for r in c.execute("pragma table_info(approval_requests)")}
audit_cols={r[1] for r in c.execute("pragma table_info(execution_audit)")}
approval_task_expr="task_id" if "task_id" in approval_cols else "NULL as task_id"
audit_task_expr="task_id" if "task_id" in audit_cols else "NULL as task_id"
approvals=[dict(r) for r in c.execute(f"select approval_id,{approval_task_expr},created_at,updated_at,expires_at,state,source,requester,task_class,requested_by,decision_by,decision_at,consumed_at,consumed_by from approval_requests order by rowid desc limit 100")]
audits=[dict(r) for r in c.execute(f"select id,{audit_task_expr},occurred_at,source,task_class,provider_id,model_id,route_path,compatibility_pass,execution_mode,outcome,approval_id from execution_audit order by rowid desc limit 200")]
print(json.dumps({"approvals":approvals,"audits":audits,"schema":{"approval_task_id":"task_id" in approval_cols,"audit_task_id":"task_id" in audit_cols}},default=str))'''
    out, _ = run(["docker", "exec", control, "python3", "-c", code])
    data = json.loads(out)
    approvals = data.get("approvals", [])
    audits = data.get("audits", [])
    schema = data.get("schema", {})
    approval_task_column = bool(schema.get("approval_task_id"))
    audit_task_column = bool(schema.get("audit_task_id"))
    if approval_task_column and audit_task_column:
        persistence = "present"
    elif approval_task_column or audit_task_column:
        persistence = "partial"
    else:
        persistence = "absent"

    audits_by_approval = {}
    unlinked_audits = 0
    for audit in audits:
        approval_id = audit.get("approval_id")
        if approval_id:
            audits_by_approval.setdefault(str(approval_id), []).append(audit)
        else:
            unlinked_audits += 1

    links = []
    seen = set()
    task_id_mismatch_count = 0
    canonical_link_count = 0
    for approval in approvals:
        approval_id = approval.get("approval_id")
        if not approval_id:
            continue
        approval_id = str(approval_id)
        seen.add(approval_id)
        linked = audits_by_approval.get(approval_id, [])
        approval_task_id = approval.get("task_id")
        audit_task_ids = sorted({str(x.get("task_id")) for x in linked if x.get("task_id")})
        canonical_task_id = str(approval_task_id) if approval_task_id else (audit_task_ids[0] if len(audit_task_ids) == 1 else None)
        mismatch = bool(approval_task_id and any(x != str(approval_task_id) for x in audit_task_ids))
        if mismatch:
            task_id_mismatch_count += 1
        if canonical_task_id and not mismatch:
            canonical_link_count += 1
        links.append({
            "correlation_key_type": "task_id" if canonical_task_id else "approval_id",
            "approval_id": approval_id,
            "canonical_task_id": canonical_task_id,
            "approval": approval,
            "execution_audits": linked,
            "execution_audit_count": len(linked),
            "link_quality": "task_id_mismatch" if mismatch else "canonical_authoritative" if canonical_task_id else "durable_authoritative" if linked else "approval_only",
        })

    orphan_linked = sum(len(v) for k, v in audits_by_approval.items() if k not in seen)
    summary = {
        "approval_row_count_observed": len(approvals),
        "execution_audit_row_count_observed": len(audits),
        "approval_rows_with_task_id": sum(1 for x in approvals if x.get("task_id")),
        "execution_audit_rows_with_task_id": sum(1 for x in audits if x.get("task_id")),
        "canonical_link_count": canonical_link_count,
        "task_id_mismatch_count": task_id_mismatch_count,
        "linked_approval_count": sum(1 for x in links if x["execution_audit_count"] > 0),
        "approval_only_count": sum(1 for x in links if x["execution_audit_count"] == 0),
        "unlinked_execution_audit_count": unlinked_audits,
        "execution_audits_with_missing_observed_approval": orphan_linked,
        "canonical_task_persistence": persistence,
        "canonical_task_schema": "approval_and_execution_audit" if persistence == "present" else persistence,
        "historical_null_task_ids_allowed": True,
        "correlation_key_type": "task_id_when_present_else_approval_id",
        "provenance": "control_api_sqlite_read_only",
    }
    return links, summary
"""

src = src[:start] + new_func + src[end:]

old_warning = '''    if correlation_quality == "legacy":
        warnings.append("recent approval/execution records are legacy because no canonical task_id is present")
    elif correlation_quality == "none":
        warnings.append("recent API history has no records for canonical task correlation; durable approval_id linkage is shown separately")
    warnings.append("canonical task persistence is absent; durable approval-to-execution linkage uses approval_id and is not a task_id")
'''
new_warning = '''    if correlation_quality == "legacy":
        warnings.append("recent approval/execution API records are historical/legacy because no canonical task_id is present on those rows")
    elif correlation_quality == "none":
        warnings.append("recent API history has no canonical task-bearing records yet")
    if durable_summary.get("canonical_task_persistence") == "present":
        warnings.append("canonical task persistence is active; historical pre-Phase 2.1F rows may remain null by design")
    else:
        warnings.append("canonical task persistence is not fully available in current authoritative storage")
    if durable_summary.get("task_id_mismatch_count", 0):
        warnings.append("canonical task_id mismatch detected between approval and execution audit rows")
'''
if src.count(old_warning) != 1:
    raise SystemExit("unexpected_warning_block_anchor")
src = src.replace(old_warning, new_warning, 1)

old_quality = '            "durable_link_quality": "approval_id_authoritative",\n'
new_quality = '            "durable_link_quality": "task_id_capable_with_approval_id_fallback" if durable_summary.get("canonical_task_persistence") == "present" else "approval_id_authoritative",\n'
if src.count(old_quality) != 1:
    raise SystemExit("unexpected_durable_link_quality_anchor")
src = src.replace(old_quality, new_quality, 1)

pathlib.Path(sys.argv[2]).write_text(src)
print("read_model_schema=2.1f.v1")
print("canonical_task_persistence_source=sqlite_schema")
print("task_id_browser_surface=safe_correlation_metadata_only")
print("historical_null_task_ids=preserved")
print("mutation_behavior=none")
print("PHIL_AI_OS_PHASE_2_1F_READ_MODEL_BUILD_OK")
