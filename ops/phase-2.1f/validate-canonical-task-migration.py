#!/usr/bin/env python3
import argparse
import sqlite3
import sys
import uuid


def cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def quick_check(conn):
    row = conn.execute("PRAGMA quick_check").fetchone()
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        assert quick_check(conn) == "ok"
        base_approvals = conn.execute("SELECT count(*) FROM approval_requests").fetchone()[0]
        base_audits = conn.execute("SELECT count(*) FROM execution_audit").fetchone()[0]

        if "task_id" not in cols(conn, "approval_requests"):
            conn.execute("ALTER TABLE approval_requests ADD COLUMN task_id TEXT")
        if "task_id" not in cols(conn, "execution_audit"):
            conn.execute("ALTER TABLE execution_audit ADD COLUMN task_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_requests_task_id_nonnull "
            "ON approval_requests(task_id) WHERE task_id IS NOT NULL"
        )
        conn.commit()

        assert quick_check(conn) == "ok"
        assert conn.execute("SELECT count(*) FROM approval_requests WHERE task_id IS NOT NULL").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM execution_audit WHERE task_id IS NOT NULL").fetchone()[0] == 0

        task_id = "tsk_" + uuid.uuid4().hex
        approval_id = "apr_phase21f_" + uuid.uuid4().hex
        audit_id_before = conn.execute("SELECT coalesce(max(id),0) FROM execution_audit").fetchone()[0]

        conn.execute(
            "INSERT INTO approval_requests(approval_id,created_at,updated_at,expires_at,state,source,requester,task_text,task_class,confidence,profile,primary_provider,primary_model,fallback_provider,fallback_model,requested_by,task_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                approval_id,
                "2099-01-01T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                "2099-01-01T01:00:00+00:00",
                "approved",
                "phase-2.1f-isolated-test",
                "validator",
                "isolated canonical task migration test",
                "general",
                1.0,
                "validation",
                None,
                None,
                None,
                None,
                "validator",
                task_id,
            ),
        )
        resolved = conn.execute(
            "SELECT task_id FROM approval_requests WHERE approval_id=?", (approval_id,)
        ).fetchone()[0]
        assert resolved == task_id

        conn.execute(
            "INSERT INTO execution_audit(occurred_at,source,task_class,provider_id,model_id,route_path,response_id,compatibility_pass,execution_mode,outcome,detail,approval_id,task_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "2099-01-01T00:01:00+00:00",
                "phase-2.1f-isolated-test",
                "general",
                None,
                None,
                "/v1/execute",
                None,
                1,
                "validation_only",
                "success",
                "isolated migration validation row",
                approval_id,
                resolved,
            ),
        )
        conn.commit()

        audit = conn.execute(
            "SELECT approval_id,task_id FROM execution_audit WHERE id>? ORDER BY id DESC LIMIT 1",
            (audit_id_before,),
        ).fetchone()
        assert audit is not None
        assert audit["approval_id"] == approval_id
        assert audit["task_id"] == task_id

        duplicate_failed = False
        try:
            conn.execute(
                "INSERT INTO approval_requests(approval_id,created_at,updated_at,expires_at,state,source,task_text,task_class,requested_by,task_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "apr_phase21f_dup_" + uuid.uuid4().hex,
                    "2099-01-01T00:02:00+00:00",
                    "2099-01-01T00:02:00+00:00",
                    "2099-01-01T01:02:00+00:00",
                    "pending",
                    "phase-2.1f-isolated-test",
                    "duplicate task id test",
                    "general",
                    "validator",
                    task_id,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            duplicate_failed = True
        assert duplicate_failed

        conn.execute("DELETE FROM execution_audit WHERE source='phase-2.1f-isolated-test'")
        conn.execute("DELETE FROM approval_requests WHERE source='phase-2.1f-isolated-test'")
        conn.commit()

        assert conn.execute("SELECT count(*) FROM approval_requests").fetchone()[0] == base_approvals
        assert conn.execute("SELECT count(*) FROM execution_audit").fetchone()[0] == base_audits
        assert quick_check(conn) == "ok"

        print("quick_check_before=ok")
        print("quick_check_after=ok")
        print(f"base_approval_rows={base_approvals}")
        print(f"base_execution_audit_rows={base_audits}")
        print("historical_task_ids_remain_null=true")
        print("server_generated_task_id_format=tsk_uuid4_hex")
        print("approval_task_id_persistence=validated")
        print("execution_audit_task_id_propagation=validated")
        print("nonnull_task_id_unique_index=validated")
        print("test_rows_removed=true")
        print("PHIL_AI_OS_PHASE_2_1F_ISOLATED_MIGRATION_VALIDATION_OK")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"validation_error={type(exc).__name__}:{exc}", file=sys.stderr)
        sys.exit(1)
