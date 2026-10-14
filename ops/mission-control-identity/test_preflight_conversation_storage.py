from pathlib import Path
import unittest


class ConversationStoragePreflightChecks(unittest.TestCase):
    def test_preflight_is_networkless_read_only_and_non_activating(self) -> None:
        script = (Path(__file__).parent / "preflight-conversation-storage.sh").read_text(encoding="utf-8")
        for marker in (
            "--network none",
            "--read-only",
            "storage_initialized=false",
            "MISSION_CONTROL_CONVERSATION_ENABLED=true",
            "conversation_key",
        ):
            self.assertIn(marker, script)
        self.assertNotIn("docker start", script)
        self.assertNotIn("--restart", script)


if __name__ == "__main__":
    unittest.main()
