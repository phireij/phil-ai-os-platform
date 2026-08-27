#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-read-model-v21f.py BASE_READ_MODEL OUTPUT_READ_MODEL")

p = pathlib.Path(sys.argv[1])
s = p.read_text()

replacements = []
replacements.append((
    'SCHEMA_VERSION = "2.1e.v1"',
    'SCHEMA_VERSION = "2.1f.v1"',
    'schema version',
))
replacements.append((
    'approvals=[dict(r) for r in c.execute("""select approval_id,created_at,updated_at,expires_at,state,source,requester,task_class,requested_by,decision_by,decision_at,consumed_at,consumed_by from approval_requests order by rowid desc limit 100""")]\naudits=[dict(r) for r in c.execute("""select id,occurred_at,source,task_class,provider_id,model_id,route_path,compatibility_pass,execution_mode,outcome,approval_id from execution_audit order by rowid desc limit 200""")]\nprint(json.dumps({"approvals":approvals,"audits":audits},default=str))',
    'approval_cols=[r[1] for r in c.execute("pragma table_info(approval_requests)")]\naudit_cols=[r[1] for r in c.execute("pragma table_info(execution_audit)")]\nindexes=[r[1] for r in c.execute("pragma index_list(approval_requests)")]\napprovals=[dict(r) for r in c.execute("""select approval_id,task_id,created_at,updated_at,expires_at,state,source,requester,task_class,requested_by,decision_by,decision_at,consumed_at,consumed_by from approval_requests order by rowid desc limit 100""")]\naudits=[dict(r) for r in c.execute("""select id,task_id,occurred_at,source,task_class,provider_id,model_id,route_path,compatibility_pass,execution_mode,outcome,approval_id from execution_audit order by rowid desc limit 200""")]\nprint(json.dumps({"approvals":approvals,"audits":audits,"schema":{"approval_task_id":"task_id" in approval_cols,"audit_task_id":"task_id" in audit_cols,"task_id_unique_index":"idx_approval_requests_task_id_nonnull" in indexes}},default=str))',
    'durable SQL allowlist',
))
replacements.append((
    '    audits = data.get("audits", [])\n    audits_by_approval = {}',
    '    audits = data.get("audits", [])\n    schema = data.get("schema", {})\n    canonical_persistence = "present" if schema.get("approval_task_id") and schema.get("audit_task_id") and schema.get("task_id_unique_index") else "partial" if schema.get("approval_task_id") or schema.get("audit_task_id") else "absent"\n    audits_by_approval = {}',
    'schema capability derivation',
))
replacements.append((
    '            "correlation_key_type": "approval_id",\n            "approval_id": approval_id,\n            "canonical_task_id": None,',
    '            "correlation_key_type": "approval_id",\n            "approval_id": approval_id,\n            "canonical_task_id": approval.get("task_id"),',
    'link canonical task id',
))
replacements.append((
    '            "link_quality": "durable_authoritative" if linked else "approval_only",',
    '            "link_quality": "canonical_durable_authoritative" if approval.get("task_id") and linked and all((a.get("task_id") == approval.get("task_id")) for a in linked) else "canonical_approval_only" if approval.get("task_id") and not linked else "durable_authoritative" if linked else "approval_only",',
    'link quality',
))
replacements.append((
    '    orphan_linked = sum(len(v) for k, v in audits_by_approval.items() if k not in seen)\n    summary = {',
    '    orphan_linked = sum(len(v) for k, v in audits_by_approval.items() if k not in seen)\n    canonical_approval_count = sum(1 for x in approvals if x.get("task_id"))\n    canonical_audit_count = sum(1 for x in audits if x.get("task_id"))\n    task_id_mismatch_count = sum(1 for x in links for a in x["execution_audits"] if x.get("canonical_task_id") and a.get("task_id") != x.get("canonical_task_id"))\n    summary = {',
    'canonical summary counters',
))
replacements.append((
    '        "canonical_task_persistence": "absent",\n        "correlation_key_type": "approval_id",',
    '        "canonical_task_persistence": canonical_persistence,\n        "canonical_approval_count_observed": canonical_approval_count,\n        "canonical_execution_audit_count_observed": canonical_audit_count,\n        "canonical_task_id_mismatch_count": task_id_mismatch_count,\n        "correlation_key_type": "approval_id",',
    'summary persistence',
))
replacements.append((
    '    tasks, correlation_quality, legacy_record_count = canonical_tasks(approvals, executions)',
    '    durable_approvals = [x.get("approval", {}) for x in durable_links]\n    durable_executions = [a for x in durable_links for a in x.get("execution_audits", [])]\n    tasks, correlation_quality, legacy_record_count = canonical_tasks(durable_approvals, durable_executions)',
    'canonical task source',
))
replacements.append((
    '    warnings.append("canonical task persistence is absent; durable approval-to-execution linkage uses approval_id and is not a task_id")',
    '    if durable_summary.get("canonical_task_persistence") == "present":\n        if durable_summary.get("canonical_approval_count_observed", 0) == 0:\n            warnings.append("canonical task persistence is active; no post-activation task_id records are observed yet")\n        if legacy_record_count:\n            warnings.append("historical approval/execution rows without task_id remain legacy by design; no backfill was performed")\n        if durable_summary.get("canonical_task_id_mismatch_count", 0):\n            warnings.append("canonical task_id mismatch detected between approval and execution audit records")\n    else:\n        warnings.append("canonical task persistence is not fully available from the authoritative SQLite schema")',
    'persistence warnings',
))
replacements.append((
    '            "durable_link_quality": "approval_id_authoritative",',
    '            "durable_link_quality": "approval_id_plus_canonical_task_id" if durable_summary.get("canonical_task_persistence") == "present" else "approval_id_authoritative",',
    'data quality durable link label',
))

for old, new, label in replacements:
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label} match count={count}, expected=1")
    s = s.replace(old, new, 1)

pathlib.Path(sys.argv[2]).write_text(s)
print("read_model_schema=2.1f.v1")
print("canonical_task_source=control_api_sqlite_read_only")
print("canonical_task_persistence=detected_from_schema")
print("historical_backfill=none")
print("secret_column_expansion=none")
print("PHIL_AI_OS_PHASE_2_1F_READ_MODEL_BUILD_OK")
