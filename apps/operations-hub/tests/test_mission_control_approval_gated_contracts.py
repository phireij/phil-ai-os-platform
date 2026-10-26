import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = {
    "mission": "approval-gated-mission.v1.schema.json",
    "risk": "risk-assessment.v1.schema.json",
    "plan": "execution-plan.v1.schema.json",
    "approval": "approval-packet.v1.schema.json",
    "capability": "action-capability.v1.schema.json",
    "worker": "worker-registry.v1.schema.json",
    "lease": "execution-lease-preview.v1.schema.json",
    "audit": "approval-gated-audit-event.v2.schema.json",
    "github_sandbox_adapter": "github-sandbox-issue-adapter.v1.schema.json",
}


class ApprovalGatedContractTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / "contracts" / "mission-control"
        self.contracts = {name: json.loads((root / filename).read_text(encoding="utf-8")) for name, filename in CONTRACTS.items()}

    def test_contracts_are_versioned_json_schemas(self):
        for name, contract in self.contracts.items():
            with self.subTest(name=name):
                self.assertEqual("https://json-schema.org/draft/2020-12/schema", contract["$schema"])
                self.assertIn(".v", contract["$id"])
                self.assertFalse(contract["additionalProperties"])

    def test_pre_activation_pack_cannot_grant_authority(self):
        for name, contract in self.contracts.items():
            with self.subTest(name=name):
                properties = contract["properties"]
                self.assertEqual("design_only_inactive", properties["activation_state"]["const"])
                self.assertEqual("none", properties["authority_effect"]["const"])
        self.assertFalse(self.contracts["mission"]["properties"]["execution_authorized"]["const"])
        self.assertFalse(self.contracts["plan"]["properties"]["execution_authorized"]["const"])
        self.assertFalse(self.contracts["approval"]["properties"]["execution_authorized"]["const"])
        self.assertFalse(self.contracts["capability"]["properties"]["dispatch_authorized"]["const"])
        self.assertFalse(self.contracts["lease"]["properties"]["dispatch_authorized"]["const"])
        self.assertFalse(self.contracts["github_sandbox_adapter"]["properties"]["network_authorized"]["const"])
        self.assertFalse(self.contracts["github_sandbox_adapter"]["properties"]["token_request_authorized"]["const"])
        self.assertFalse(self.contracts["github_sandbox_adapter"]["properties"]["dispatch_authorized"]["const"])

    def test_plan_approval_and_lease_are_bound_and_inert(self):
        self.assertEqual("^sha256:[a-f0-9]{64}$", self.contracts["plan"]["properties"]["plan_digest"]["pattern"])
        self.assertEqual("^sha256:[a-f0-9]{64}$", self.contracts["approval"]["properties"]["plan_digest"]["pattern"])
        self.assertEqual("^sha256:[a-f0-9]{64}$", self.contracts["lease"]["properties"]["plan_digest"]["pattern"])
        self.assertEqual("awaiting_decision", self.contracts["approval"]["properties"]["decision_state"]["const"])
        self.assertEqual("not_issued", self.contracts["lease"]["properties"]["lease_state"]["const"])

    def test_risk_policy_blocks_r4_and_requires_typed_r3_confirmation(self):
        rules = self.contracts["risk"]["allOf"]
        self.assertEqual("R4", rules[0]["if"]["properties"]["risk_level"]["const"])
        self.assertEqual("blocked", rules[0]["then"]["properties"]["required_gate"]["const"])
        self.assertEqual("R3", rules[1]["if"]["properties"]["risk_level"]["const"])
        self.assertEqual("ceo_typed_confirmation", rules[1]["then"]["properties"]["required_gate"]["const"])

    def test_github_sandbox_adapter_contract_pins_scope_without_credentials(self):
        adapter = self.contracts["github_sandbox_adapter"]
        properties = adapter["properties"]
        self.assertEqual("mission-control-sandbox-pilot", properties["github_app_slug"]["const"])
        self.assertEqual("phireij/mission-control-github-sandbox", properties["target_repository"]["const"])
        self.assertEqual("create_labelled_issue", properties["permitted_operation"]["const"])
        self.assertEqual("mission-control-sandbox-pilot", properties["required_label"]["const"])
        self.assertEqual("external_owner_managed_not_read_by_adapter", properties["credential_boundary"]["const"])
        self.assertEqual("one_selected_repository", properties["installation_scope"]["const"])
        forbidden_fields = {"private_key", "installation_token", "authorization_header", "webhook_secret"}
        self.assertFalse(forbidden_fields & set(properties))


if __name__ == "__main__":
    unittest.main()
