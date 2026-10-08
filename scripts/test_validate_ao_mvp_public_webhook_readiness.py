#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"scripts/validate_ao_mvp_public_webhook_readiness.py"
spec=importlib.util.spec_from_file_location("validator",P)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

BASE={
 "schema":"phil-ai-os-public-webhook-activation-readiness",
 "authority_effect":"none",
 "private_a1_checkpoint_complete":True,
 "status":"planning_only_not_authorized",
 **{k:False for k in m.DENIED_TRUE},
 "checks":{k:False for k in m.REQUIRED_CHECKS},
}

class TestPublicWebhookReadiness(unittest.TestCase):
 def test_planning_record_passes(self):
  self.assertEqual(m.validate(copy.deepcopy(BASE)),[])
 def test_explicit_approval_advances_only_to_pending_evidence(self):
  d=copy.deepcopy(BASE)
  d["status"]="activation_authorized_pending_operational_evidence"
  d["public_webhook_activation_authorized"]=True
  d["checks"]["phase_specific_ceo_approval_recorded"]=True
  self.assertEqual(m.validate(d),[])
 def test_production_authority_stays_denied(self):
  d=copy.deepcopy(BASE); d["production_mutation_authorized"]=True
  self.assertTrue(m.validate(d))
 def test_hermes_reuse_stays_denied(self):
  d=copy.deepcopy(BASE); d["hermes_reuse_authorized"]=True
  self.assertTrue(m.validate(d))
 def test_missing_check_fails(self):
  d=copy.deepcopy(BASE); del d["checks"]["replay_protection_green"]
  self.assertTrue(m.validate(d))

if __name__=="__main__":
 unittest.main()
