#!/usr/bin/env python3
import copy, unittest
from ao_mvp_public_webhook_isolation import validate_plan

BASE={"apply_changes":False,"dedicated_hostname":None,"shared_components":[],"production_credentials":False,"production_mutation_capability":False,"public_webhook_activation_authorized":False,"authority_effect":"none"}

class TestIsolation(unittest.TestCase):
 def test_inert_plan_passes(self): self.assertEqual(validate_plan(copy.deepcopy(BASE)),[])
 def test_hermes_hostname_rejected(self):
  d=copy.deepcopy(BASE); d["dedicated_hostname"]="ao.hermes.example.invalid"; self.assertTrue(validate_plan(d))
 def test_existing_traefik_reuse_rejected(self):
  d=copy.deepcopy(BASE); d["shared_components"]=["traefik-existing"]; self.assertTrue(validate_plan(d))
 def test_apply_rejected(self):
  d=copy.deepcopy(BASE); d["apply_changes"]=True; self.assertTrue(validate_plan(d))
 def test_prod_credentials_rejected(self):
  d=copy.deepcopy(BASE); d["production_credentials"]=True; self.assertTrue(validate_plan(d))

if __name__=="__main__": unittest.main()
