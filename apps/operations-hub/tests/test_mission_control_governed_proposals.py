import sys
import tempfile
import unittest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations_hub.mission_control_governed_proposals import GovernedProposalError, GovernedProposalStore


def payload(message_id="message-a"):
    return {
        "source_message_id": message_id,
        "project_id": "phil-ai-os",
        "task_class": "general",
        "scope": "Review one bounded design artifact.",
        "expected_result": "A non-authorizing review note.",
        "required_authority": "A1",
        "source_evidence_refs": ["evidence:immutable:one"],
    }


class GovernedProposalStoreTests(unittest.TestCase):
    def setUp(self):
        self.db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.db.close()
        self.store = GovernedProposalStore(self.db.name)
        self.store.initialize()
        self.store.seed_conversation("ceo-a", "conversation-a", "message-a")
        self.store.seed_conversation("ceo-b", "conversation-b", "message-b")

    def tearDown(self):
        Path(self.db.name).unlink(missing_ok=True)

    def test_draft_is_idempotent_and_never_assigns_or_executes(self):
        created = self.store.create_proposal("ceo-a", "conversation-a", payload(), "same-key")
        replayed = self.store.create_proposal("ceo-a", "conversation-a", payload(), "same-key")
        self.assertEqual(created, replayed)
        self.assertEqual("draft", created["proposal_state"])
        self.assertIsNone(created["approval_id"])
        self.assertIsNone(created["assigned_agent_id"])
        self.assertIsNone(created["assignment_id"])
        self.assertFalse(created["execution_authorized"])
        self.assertFalse(created["mutation_authorized"])
        self.assertEqual("none", created["authority_effect"])
        changed = payload()
        changed["scope"] = "Different bounded scope."
        with self.assertRaisesRegex(GovernedProposalError, "idempotency_conflict"):
            self.store.create_proposal("ceo-a", "conversation-a", changed, "same-key")

    def test_owner_and_source_message_boundaries_fail_closed(self):
        with self.assertRaisesRegex(GovernedProposalError, "conversation_or_source_message_not_found"):
            self.store.create_proposal("ceo-b", "conversation-b", payload(), "key")
        self.store.seed_conversation("ceo-a", "conversation-c", "message-c", sender="chief_of_staff")
        with self.assertRaisesRegex(GovernedProposalError, "source_message_must_be_ceo_authored"):
            self.store.create_proposal("ceo-a", "conversation-c", payload("message-c"), "key")

    def test_attributable_decision_is_immutable_scoped_and_non_authorizing(self):
        proposal = self.store.create_proposal("ceo-a", "conversation-a", payload(), "key")
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        decision = self.store.record_decision("ceo-a", proposal["proposal_id"], "approved", "Proceed only through a separate gate.", expiry)
        self.assertEqual(proposal["proposal_id"], decision["proposal_id"])
        self.assertEqual({"project_id": "phil-ai-os", "required_authority": "A1"}, decision["decision_scope"])
        self.assertEqual("none", decision["authority_effect"])
        self.assertIsNone(decision["assignment_id"])
        self.assertFalse(decision["execution_authorized"])
        self.assertFalse(decision["mutation_authorized"])
        with self.assertRaisesRegex(GovernedProposalError, "decision_already_recorded"):
            self.store.record_decision("ceo-a", proposal["proposal_id"], "rejected", "Change it.", expiry)

    def test_expired_or_cross_owner_decision_is_rejected(self):
        proposal = self.store.create_proposal("ceo-a", "conversation-a", payload(), "key")
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(GovernedProposalError, "decision_expired"):
            self.store.record_decision("ceo-a", proposal["proposal_id"], "approved", "Too late.", expired)
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(GovernedProposalError, "proposal_not_found"):
            self.store.record_decision("ceo-b", proposal["proposal_id"], "approved", "Not mine.", future)

    def test_contract_keeps_approval_non_authorizing(self):
        root = Path(__file__).resolve().parents[3]
        contract = json.loads((root / "contracts/mission-control/ceo-governed-proposals-api.v1.json").read_text(encoding="utf-8"))
        self.assertEqual("design_only_inactive", contract["status"])
        self.assertFalse(contract["activation_authorized"])
        self.assertEqual("none", contract["authority_effect"])
        self.assertIn("must not create an assignment, execution, mutation", contract["invariants"]["separate_authority_gate"])


if __name__ == "__main__":
    unittest.main()

