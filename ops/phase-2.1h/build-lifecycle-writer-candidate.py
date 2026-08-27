#!/usr/bin/env python3
import pathlib, sys

if len(sys.argv)!=3:
    raise SystemExit('usage: build-lifecycle-writer-candidate.py INPUT_APP OUTPUT_APP')

src=pathlib.Path(sys.argv[1]).read_text()

def replace_once(old,new,label):
    global src
    n=src.count(old)
    if n!=1:
        raise SystemExit(f'anchor_{label}_count={n}')
    src=src.replace(old,new,1)

helper='''\ndef lifecycle_event_insert(conn, task_id, stage, source_component="control-api", actor_id=None, assigned_agent_id=None, previous_stage=None, reason_code=None, correlation_id=None):\n    if not task_id:\n        return None\n    event_id = "evt_" + uuid.uuid4().hex\n    conn.execute(\n        """INSERT INTO task_lifecycle_events(\n             event_id,task_id,stage,occurred_at,source_component,actor_id,\n             assigned_agent_id,previous_stage,reason_code,correlation_id)\n             VALUES(?,?,?,?,?,?,?,?,?,?)""",\n        (event_id, task_id, stage, now_iso(), source_component, actor_id,\n         assigned_agent_id, previous_stage, reason_code, correlation_id),\n    )\n    return event_id\n\n'''
replace_once('def execution_audit_write(', helper+'def execution_audit_write(', 'helper_insertion')

approval_anchor='''        conn.execute(\n            """\n            INSERT INTO approval_requests(\n'''
# Do not alter the approval insert. Instead insert lifecycle writes immediately before
# the approval transaction's existing commit, using unique nearby return anchor.
commit_anchor='''        conn.commit()\n    finally:\n        conn.close()\n    return (\n        201,'''
commit_repl='''        lifecycle_event_insert(conn, task_id, "RECEIVED", correlation_id=approval_id)\n        lifecycle_event_insert(conn, task_id, "CLASSIFIED", previous_stage="RECEIVED", reason_code="classification_finalized", correlation_id=approval_id)\n        lifecycle_event_insert(conn, task_id, "APPROVAL_PENDING", previous_stage="CLASSIFIED", reason_code="approval_created", correlation_id=approval_id)\n        conn.commit()\n    finally:\n        conn.close()\n    return (\n        201,'''
if approval_anchor not in src:
    raise SystemExit('approval_insert_anchor_missing')
replace_once(commit_anchor,commit_repl,'approval_lifecycle_commit')

# execution_audit_write has its own first commit before approval_create. Scope the
# replacement to the function prefix so only that commit is changed.
start=src.index('def execution_audit_write(')
end=src.index('\ndef _provider_execute',start)
block=src[start:end]
audit_old='''        conn.commit()\n    finally:\n        conn.close()'''
audit_new='''        lifecycle_event_insert(conn, task_id, "AUDITED", previous_stage=None, reason_code="execution_audit_persisted", correlation_id=approval_id)\n        conn.commit()\n    finally:\n        conn.close()'''
if block.count(audit_old)!=1:
    raise SystemExit(f'audit_commit_anchor_count={block.count(audit_old)}')
block=block.replace(audit_old,audit_new,1)
src=src[:start]+block+src[end:]

pathlib.Path(sys.argv[2]).write_text(src)
print('candidate_lifecycle_events=RECEIVED,CLASSIFIED,APPROVAL_PENDING,AUDITED')
print('candidate_assignment_inference=none')
print('candidate_event_transaction=domain_transaction')
print('approval_decision_events=deferred')
print('PHIL_AI_OS_PHASE_2_1H_LIFECYCLE_WRITER_CANDIDATE_BUILD_OK')
