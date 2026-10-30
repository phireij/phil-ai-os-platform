from pathlib import Path
import unittest


class ConversationStorageMonitorChecks(unittest.TestCase):
    def test_legacy_storage_probe_remains_networkless_read_only_and_content_free(self) -> None:
        script = (Path(__file__).parent / "monitor-conversation-storage.sh").read_text(encoding="utf-8")
        for marker in (
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--user 10003:10003",
            "conversations.enc",
            "deletion-ledger.enc",
            "dst=/mnt/conversation-backup,readonly",
            "BACKUP_MAGIC",
            "BACKUP_MAX_AGE_SECONDS",
            "conversation_backup_missing",
            "conversation_backup_expired",
            "backup_content_exposed=false",
            "state_content_exposed=false",
            "authority_effect=none",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker start",
            "docker stop",
            "docker rm",
            "docker volume create",
            "docker volume rm",
            "docker pull",
            "--privileged",
            "unlink(",
            "os.remove",
            "os.unlink",
        ):
            self.assertNotIn(prohibited, script)
        self.assertIn(r'Z\.enc", path.name)', script)
        self.assertNotIn(r'Z\\.enc", path.name)', script)

    def test_workflow_is_scheduled_and_checks_the_active_session_boundary(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-storage-monitor.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "schedule:",
            "17,47 * * * *",
            "phil-ai-os-mission-control-google-ceo-session",
            "ReadonlyRootfs",
            "CapDrop",
            "session_ready;conversation_authority=enabled",
            "session_status",
            "test \"$session_status\" = 401",
            "authority_effect=none",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker start",
            "docker stop",
            "docker rm",
            "docker volume create",
            "docker volume rm",
            "docker pull",
            "actions/upload-artifact",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
