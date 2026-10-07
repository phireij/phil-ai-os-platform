#!/usr/bin/env python3
import copy, unittest
from ao_mvp_public_webhook_activation_gate import REQUIRED, decide
BASE={"public_webhook_activation_authorized":True,"production_mutation_authorized":False,"authority_effect":"none","dedicated_hostname":"ao-webhook.example.invalid","hermes_reuse":False,"existing_traefik_reuse":False,"existing_core_workload_reuse":False,"production_credentials_present":False,"production_data_present":False,"twilio_enabled":False,"customer_systems_enabled":False,"payments_enabled":False,"evidence":{k:True for k in REQUIRED},"approval":{"phase":"public_webhook_activation","ceo_explicit_approval":True,"approved_at":"2099-01-01T00:00:00Z","scope":"isolated synthetic-canary ingress only"}}
class T(unittest.TestCase):
 def test_complete_hypothetical_evidence_ready(self): self.assertTrue(decide(copy.deepcopy(BASE))["ready"])
 def test_missing_ceo_approval_fails(self):
  d=copy.deepcopy(BASE); d["approval"]["ceo_explicit_approval"]=False; self.assertFalse(decide(d)["ready"])
 def test_missing_one_check_fails(self):
  d=copy.deepcopy(BASE); d["evidence"]["tls_green"]=False; self.assertFalse(decide(d)["ready"])
 def test_hermes_reuse_fails(self):
  d=copy.deepcopy(BASE); d["dedicated_hostname"]="hermes.example.invalid"; self.assertFalse(decide(d)["ready"])
 def test_production_credentials_fail(self):
  d=copy.deepcopy(BASE); d["production_credentials_present"]=True; self.assertFalse(decide(d)["ready"])
if __name__=="__main__": unittest.main()
