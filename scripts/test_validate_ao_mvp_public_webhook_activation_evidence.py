#!/usr/bin/env python3
import copy, importlib.util, unittest
from pathlib import Path
P=Path(__file__).resolve().parent/"validate_ao_mvp_public_webhook_activation_evidence.py"
s=importlib.util.spec_from_file_location("v",P); v=importlib.util.module_from_spec(s); s.loader.exec_module(v)
BASE={"schema":"phil-ai-os-public-webhook-activation-evidence","status":"template_not_authorized","public_webhook_activation_authorized":False,"production_mutation_authorized":False,"authority_effect":"none","dedicated_hostname":None,"hermes_reuse":False,"existing_traefik_reuse":False,"existing_core_workload_reuse":False,"production_credentials_present":False,"production_data_present":False,"twilio_enabled":False,"customer_systems_enabled":False,"payments_enabled":False,"evidence":{k:False for k in v.REQUIRED_EVIDENCE},"approval":{"phase":"public_webhook_activation","ceo_explicit_approval":False,"approved_at":None,"scope":None}}
class T(unittest.TestCase):
 def test_template_passes(self): self.assertEqual(v.validate_template(copy.deepcopy(BASE)),[])
 def test_a1_cannot_imply_public_approval(self):
  d=copy.deepcopy(BASE); d["public_webhook_activation_authorized"]=True; self.assertTrue(v.validate_template(d))
 def test_approval_prepopulation_rejected(self):
  d=copy.deepcopy(BASE); d["approval"]["ceo_explicit_approval"]=True; self.assertTrue(v.validate_template(d))
 def test_hostname_preselection_rejected(self):
  d=copy.deepcopy(BASE); d["dedicated_hostname"]="ao.example.invalid"; self.assertTrue(v.validate_template(d))
if __name__=="__main__": unittest.main()
