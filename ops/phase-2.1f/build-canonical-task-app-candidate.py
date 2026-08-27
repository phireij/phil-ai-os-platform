#!/usr/bin/env python3
import pathlib
import re
import sys


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"anchor_{label}_count={count}")
    return text.replace(old, new, 1)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: build-canonical-task-app-candidate.py INPUT_APP OUTPUT_APP")
    src = pathlib.Path(sys.argv[1]).read_text()

    # Generate the canonical task identity exactly once, at approval creation.
    src = replace_once(
        src,
        '    approval_id = "apr_" + uuid.uuid4().hex\n',
        '    approval_id = "apr_" + uuid.uuid4().hex\n    task_id = "tsk_" + uuid.uuid4().hex\n',
        'approval_id_generation',
    )

    # Persist task_id with the approval record. Existing historical rows remain nullable
    # and are handled by the separately validated migration contract.
    src = replace_once(
        src,
        '                approval_id,\n                created_at,',
        '                approval_id,\n                task_id,\n                created_at,',
        'approval_insert_columns',
    )
    src = replace_once(
        src,
        "                ?,?,?,?,'pending',\n",
        "                ?,?,?,?,?,'pending',\n",
        'approval_insert_values',
    )
    src = replace_once(
        src,
        '            approval_id,\n            created_at,',
        '            approval_id,\n            task_id,\n            created_at,',
        'approval_insert_tuple',
    )
    src = replace_once(
        src,
        '            "approval_id": approval_id,\n            "state": "pending",',
        '            "approval_id": approval_id,\n            "task_id": task_id,\n            "state": "pending",',
        'approval_response',
    )

    # execution_audit_write intentionally does NOT accept a caller-supplied task_id.
    # It derives task_id authoritatively from approval_id before writing the audit row.
    audit_anchor = '''def execution_audit_write(\n    source,\n    task_class=None,\n    provider=None,\n    model=None,\n    route_path=None,\n    response_id=None,\n    compatibility_pass=False,\n    execution_mode="controlled",\n    outcome="unknown",\n    detail=None,\n    approval_id=None,\n):\n    conn = db()\n'''
    audit_replacement = '''def execution_audit_write(\n    source,\n    task_class=None,\n    provider=None,\n    model=None,\n    route_path=None,\n    response_id=None,\n    compatibility_pass=False,\n    execution_mode="controlled",\n    outcome="unknown",\n    detail=None,\n    approval_id=None,\n):\n    task_id = None\n    if approval_id:\n        lookup = db()\n        try:\n            row = lookup.execute(\n                "SELECT task_id FROM approval_requests WHERE approval_id=?",\n                (approval_id,),\n            ).fetchone()\n            if row is not None:\n                try:\n                    task_id = row["task_id"]\n                except (KeyError, IndexError, TypeError):\n                    task_id = None\n        finally:\n            lookup.close()\n    conn = db()\n'''
    src = replace_once(src, audit_anchor, audit_replacement, 'audit_function')

    src = replace_once(
        src,
        '             approval_id)\n            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        '             approval_id,task_id)\n            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
        'audit_insert_columns_values',
    )
    src = replace_once(
        src,
        '            execution_mode, outcome, detail, approval_id\n',
        '            execution_mode, outcome, detail, approval_id, task_id\n',
        'audit_insert_tuple',
    )

    pathlib.Path(sys.argv[2]).write_text(src)
    print('candidate_task_id_generation=approval_create_server_side')
    print('candidate_task_id_format=tsk_uuid4_hex')
    print('candidate_audit_task_id_source=approval_id_lookup')
    print('caller_supplied_task_id_trusted=false')
    print('PHIL_AI_OS_PHASE_2_1F_APP_CANDIDATE_BUILD_OK')


if __name__ == '__main__':
    main()
