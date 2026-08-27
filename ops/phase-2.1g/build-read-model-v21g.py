#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-read-model-v21g.py BASE_2_1F_READ_MODEL OUTPUT_READ_MODEL")

src = pathlib.Path(sys.argv[1]).read_text()

if src.count('SCHEMA_VERSION = "2.1f.v1"') != 1:
    raise SystemExit("expected exactly one 2.1f schema marker")
src = src.replace('SCHEMA_VERSION = "2.1f.v1"', 'SCHEMA_VERSION = "2.1g.v1"', 1)

start = src.find("def canonical_tasks(")
end = src.find("\ndef durable_approval_execution_links", start)
if start < 0 or end < 0:
    raise SystemExit("canonical_tasks function boundaries not found")

replacement = r'''def canonical_tasks(approvals, executions):
    by_id = {}
    legacy = 0

    def task_for(task_id):
        return by_id.setdefault(str(task_id), {
            "task_id": str(task_id),
            "lifecycle_state": "RECEIVED",
            "assigned_agent_id": None,
            "assignment_provenance": "authoritative_source_unavailable",
            "approval_ids": [],
            "execution_ids": [],
            "correlation_quality": "canonical",
            "lifecycle_evidence": [],
            "unsupported_stages": ["ASSIGNED", "PLANNED", "POLICY_CHECK", "EXECUTING", "CLOSED"],
        })

    def evidence(task, stage, source, at=None, detail=None):
        item = {"stage": stage, "provenance": source}
        if at is not None:
            item["at"] = at
        if detail is not None:
            item["detail"] = detail
        if item not in task["lifecycle_evidence"]:
            task["lifecycle_evidence"].append(item)

    for row in approvals:
        if not isinstance(row, dict):
            legacy += 1
            continue
        task_id = row.get("task_id") or row.get("canonical_task_id")
        if not task_id:
            legacy += 1
            continue
        task = task_for(task_id)
        evidence(task, "RECEIVED", "approval_requests.created_at", row.get("created_at"))
        if row.get("task_class"):
            evidence(task, "CLASSIFIED", "approval_requests.task_class", row.get("updated_at"), str(row.get("task_class")))
        rid = row.get("approval_id") or row.get("id")
        if rid and rid not in task["approval_ids"]:
            task["approval_ids"].append(rid)
        state = str(row.get("state") or row.get("status") or "").lower()
        if state == "pending":
            task["lifecycle_state"] = "APPROVAL_PENDING"
            evidence(task, "APPROVAL_PENDING", "approval_requests.state", row.get("updated_at"))
        elif state == "approved":
            task["lifecycle_state"] = "AUTHORIZED"
            evidence(task, "AUTHORIZED", "approval_requests.state", row.get("decision_at") or row.get("updated_at"))
        elif state == "denied":
            task["lifecycle_state"] = "DENIED"
            evidence(task, "DENIED", "approval_requests.state", row.get("decision_at") or row.get("updated_at"))
        elif state == "expired":
            task["lifecycle_state"] = "EXPIRED"
            evidence(task, "EXPIRED", "approval_requests.state", row.get("updated_at"))
        if row.get("consumed_at") or row.get("consumed_by"):
            evidence(task, "APPROVAL_CONSUMED", "approval_requests.consumed_at/consumed_by", row.get("consumed_at"))

    for row in executions:
        if not isinstance(row, dict):
            legacy += 1
            continue
        task_id = row.get("task_id") or row.get("canonical_task_id")
        if not task_id:
            legacy += 1
            continue
        task = task_for(task_id)
        rid = row.get("execution_id") or row.get("id")
        if rid and rid not in task["execution_ids"]:
            task["execution_ids"].append(rid)
        outcome = str(row.get("outcome") or row.get("state") or row.get("status") or "").lower()
        mapped = None
        if outcome in {"success", "succeeded", "completed"}:
            mapped = "SUCCEEDED"
        elif outcome in {"failed", "error"}:
            mapped = "FAILED"
        elif outcome in {"blocked", "rejected"}:
            mapped = "BLOCKED"
        elif outcome in {"cancelled", "canceled"}:
            mapped = "CANCELLED"
        if mapped:
            task["lifecycle_state"] = mapped
            evidence(task, mapped, "execution_audit.outcome", row.get("occurred_at"), outcome)
        evidence(task, "AUDITED", "execution_audit.occurred_at", row.get("occurred_at"))

    for task in by_id.values():
        task["lifecycle_evidence"].sort(key=lambda x: (str(x.get("at") or ""), x.get("stage") or ""))

    quality = "canonical" if by_id and legacy == 0 else "partial" if by_id else "none" if not approvals and not executions else "legacy"
    return list(by_id.values()), quality, legacy
'''

src = src[:start] + replacement + src[end:]

needle = '            "durable_link_quality": "approval_id_plus_canonical_task_id" if durable_summary.get("canonical_task_persistence") == "present" else "approval_id_authoritative",'
if src.count(needle) != 1:
    raise SystemExit("durable link quality marker not found")
src = src.replace(
    needle,
    needle + '\n            "lifecycle_provenance": "durable_subset_only",\n            "unsupported_lifecycle_stages": ["ASSIGNED", "PLANNED", "POLICY_CHECK", "EXECUTING", "CLOSED"],\n            "agent_assignment_provenance": "authoritative_source_unavailable",',
    1,
)

warning_anchor = '    if durable_summary.get("canonical_task_persistence") == "present":\n'
if src.count(warning_anchor) != 1:
    raise SystemExit("warning anchor not found")
src = src.replace(
    warning_anchor,
    '    warnings.append("lifecycle observability is evidence-based; ASSIGNED, PLANNED, POLICY_CHECK, EXECUTING-start, and CLOSED remain unavailable until durable sources exist")\n' + warning_anchor,
    1,
)

pathlib.Path(sys.argv[2]).write_text(src)
print("read_model_schema=2.1g.v1")
print("lifecycle_provenance=durable_subset_only")
print("agent_assignment=authoritative_source_unavailable")
print("unsupported_stages=ASSIGNED,PLANNED,POLICY_CHECK,EXECUTING,CLOSED")
print("database_migration=none")
print("authority_expansion=none")
print("PHIL_AI_OS_PHASE_2_1G_READ_MODEL_BUILD_OK")
