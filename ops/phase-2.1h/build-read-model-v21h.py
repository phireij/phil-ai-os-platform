#!/usr/bin/env python3
import pathlib, sys

if len(sys.argv)!=3:
    raise SystemExit('usage: build-read-model-v21h.py BASE_2_1G_READ_MODEL OUTPUT_READ_MODEL')
s=pathlib.Path(sys.argv[1]).read_text()

def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}_match_count={n}')
    s=s.replace(old,new,1)

rep('SCHEMA_VERSION = "2.1g.v1"','SCHEMA_VERSION = "2.1h.v1"','schema')

rep(
    'def canonical_tasks(approvals, executions):',
    'def canonical_tasks(approvals, executions, lifecycle_events=None):',
    'canonical_signature',
)

anchor='''    for task in by_id.values():\n        task["lifecycle_evidence"].sort(key=lambda x: (str(x.get("at") or ""), x.get("stage") or ""))\n'''
insert='''    for row in (lifecycle_events or []):
        if not isinstance(row, dict) or not row.get("task_id"):
            continue
        task = task_for(row.get("task_id"))
        stage = str(row.get("stage") or "").upper()
        if not stage:
            continue
        evidence(task, stage, "task_lifecycle_events", row.get("occurred_at"), row.get("reason_code"))
        task["lifecycle_state"] = stage
        if stage == "ASSIGNED" and row.get("assigned_agent_id"):
            task["assigned_agent_id"] = row.get("assigned_agent_id")
            task["assignment_provenance"] = "task_lifecycle_events.assigned_agent_id"
        if stage in task.get("unsupported_stages", []):
            task["unsupported_stages"].remove(stage)

    for task in by_id.values():
        task["lifecycle_evidence"].sort(key=lambda x: (str(x.get("at") or ""), x.get("stage") or ""))
'''
rep(anchor,insert,'ledger_merge')

sql_old='''indexes=[r[1] for r in c.execute("pragma index_list(approval_requests)")]\napprovals=[dict(r) for r in c.execute("""select approval_id,task_id,created_at,updated_at,expires_at,state,source,requester,task_class,requested_by,decision_by,decision_at,consumed_at,consumed_by from approval_requests order by rowid desc limit 100""")]'''
sql_new='''indexes=[r[1] for r in c.execute("pragma index_list(approval_requests)")]\ntables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}\nlifecycle_present="task_lifecycle_events" in tables\nlifecycle_triggers={r[0] for r in c.execute("select name from sqlite_master where type='trigger' and tbl_name='task_lifecycle_events'")} if lifecycle_present else set()\nlifecycles=[dict(r) for r in c.execute("""select event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id from task_lifecycle_events order by rowid desc limit 500""")] if lifecycle_present else []\napprovals=[dict(r) for r in c.execute("""select approval_id,task_id,created_at,updated_at,expires_at,state,source,requester,task_class,requested_by,decision_by,decision_at,consumed_at,consumed_by from approval_requests order by rowid desc limit 100""")]'''
rep(sql_old,sql_new,'safe_sql_ledger')

print_old='''print(json.dumps({"approvals":approvals,"audits":audits,"schema":{"approval_task_id":"task_id" in approval_cols,"audit_task_id":"task_id" in audit_cols,"task_id_unique_index":"idx_approval_requests_task_id_nonnull" in indexes}},default=str))'''
print_new='''print(json.dumps({"approvals":approvals,"audits":audits,"lifecycles":lifecycles,"schema":{"approval_task_id":"task_id" in approval_cols,"audit_task_id":"task_id" in audit_cols,"task_id_unique_index":"idx_approval_requests_task_id_nonnull" in indexes,"lifecycle_ledger":lifecycle_present,"lifecycle_no_update":"trg_task_lifecycle_events_no_update" in lifecycle_triggers,"lifecycle_no_delete":"trg_task_lifecycle_events_no_delete" in lifecycle_triggers}},default=str))'''
rep(print_old,print_new,'json_payload')

rep(
    '    audits = data.get("audits", [])\n    schema = data.get("schema", {})',
    '    audits = data.get("audits", [])\n    lifecycles = data.get("lifecycles", [])\n    schema = data.get("schema", {})',
    'payload_read',
)

rep(
    '    return links, summary',
    '    summary["lifecycle_ledger"] = "append_only" if schema.get("lifecycle_ledger") and schema.get("lifecycle_no_update") and schema.get("lifecycle_no_delete") else "partial" if schema.get("lifecycle_ledger") else "absent"\n    summary["lifecycle_event_count_observed"] = len(lifecycles)\n    return links, summary, lifecycles',
    'durable_return',
)

rep(
    '    durable_links, durable_summary = durable_approval_execution_links(control)',
    '    durable_links, durable_summary, lifecycle_events = durable_approval_execution_links(control)',
    'main_durable_call',
)

rep(
    '    tasks, correlation_quality, legacy_record_count = canonical_tasks(durable_approvals, durable_executions)',
    '    tasks, correlation_quality, legacy_record_count = canonical_tasks(durable_approvals, durable_executions, lifecycle_events)',
    'canonical_call',
)

rep(
    '            "lifecycle_provenance": "durable_subset_only",\n            "unsupported_lifecycle_stages": ["ASSIGNED", "PLANNED", "POLICY_CHECK", "EXECUTING", "CLOSED"],\n            "agent_assignment_provenance": "authoritative_source_unavailable",',
    '            "lifecycle_provenance": "append_only_ledger_available" if durable_summary.get("lifecycle_ledger") == "append_only" else "durable_subset_only",\n            "lifecycle_ledger_state": durable_summary.get("lifecycle_ledger", "absent"),\n            "lifecycle_event_count_observed": durable_summary.get("lifecycle_event_count_observed", 0),\n            "unsupported_lifecycle_stages": ["ASSIGNED", "PLANNED", "POLICY_CHECK", "EXECUTING", "CLOSED"],\n            "agent_assignment_provenance": "explicit_ledger_event_only" if durable_summary.get("lifecycle_ledger") == "append_only" else "authoritative_source_unavailable",',
    'data_quality',
)

rep(
    '    warnings.append("lifecycle observability is evidence-based; ASSIGNED, PLANNED, POLICY_CHECK, EXECUTING-start, and CLOSED remain unavailable until durable sources exist")',
    '    if durable_summary.get("lifecycle_ledger") == "append_only":\n        if durable_summary.get("lifecycle_event_count_observed", 0) == 0:\n            warnings.append("append-only lifecycle ledger is active; no genuine lifecycle events are observed yet")\n        warnings.append("ASSIGNED, PLANNED, POLICY_CHECK, EXECUTING-start, and CLOSED remain unavailable unless explicit authoritative events are written")\n    else:\n        warnings.append("lifecycle observability is evidence-based; append-only lifecycle ledger is not fully available")',
    'warnings',
)

pathlib.Path(sys.argv[2]).write_text(s)
print('read_model_schema=2.1h.v1')
print('lifecycle_source=append_only_task_lifecycle_events')
print('assignment_source=explicit_ledger_event_only')
print('secret_column_expansion=none')
print('mutation_controls=none')
print('PHIL_AI_OS_PHASE_2_1H_READ_MODEL_BUILD_OK')
