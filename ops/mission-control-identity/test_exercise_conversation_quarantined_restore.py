from pathlib import Path
import unittest


class QuarantinedRestoreExerciseChecks(unittest.TestCase):
    def test_exercise_has_tmpfs_quarantine_and_resumes_same_session(self) -> None:
        script = (Path(__file__).parent / "exercise-conversation-quarantined-restore.sh").read_text(encoding="utf-8")
        for marker in (
            "docker stop --time 20",
            "resume_session",
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--user 10003:10003",
            "--tmpfs /work:rw,noexec,nosuid,size=384m,mode=0700,uid=10003,gid=10003",
            "create_backup(config, backup)",
            "restore_to_quarantine",
            "test \"$(docker inspect \"$SESSION\" --format '{{.Id}}')\" = \"$SESSION_ID\"",
            "live_state_replaced=false",
            "offline_recovery_package_exercised=false",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker rename",
            "docker rm -f $SESSION",
            "docker volume rm",
            "docker pull",
            "--privileged",
            "conversation-key-recovery.v1.json",
        ):
            self.assertNotIn(prohibited, script)

    def test_workflow_requires_typed_approval_and_checks_public_boundary(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-quarantined-restore.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "APPROVE_QUARANTINED_RESTORE",
            "exercise-conversation-quarantined-restore.sh",
            "healthz",
            "unauthenticated_session=401",
            "offline_recovery_package_exercised=false",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker volume rm",
            "docker pull",
            "actions/upload-artifact",
            "MISSION_CONTROL_CONVERSATION_RECOVERY_PASSPHRASE",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
