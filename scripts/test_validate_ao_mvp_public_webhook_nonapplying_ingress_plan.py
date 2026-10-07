#!/usr/bin/env python3
import copy, importlib.util, unittest
from pathlib import Path
P=Path(__file__).resolve().parent/"validate_ao_mvp_public_webhook_nonapplying_ingress_plan.py"
s=importlib.util.spec_from_file_location("v",P);v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
BASE={"status":"planned_not_applied","apply_changes":False,"authority_effect":"none","public_webhook_activation_authorized":False,"dedicated_ingress_identity":{"hostname":None,"must_not_reuse_hermes":True,"must_not_reuse_existing_traefik":True,"must_not_reuse_phil_ai_os_core":True},"dns":{"reviewed_not_applied":True,"record_type":None,"record_name":None,"target":None,"ttl":None},"route_and_port":{"reviewed_not_applied":True,"dedicated_route_required":True,"public_port":None,"existing_route_reuse":False,"existing_public_port_change":False},"tls":{"plan_defined":True,"hostname_binding":None,"plaintext_fallback":False},"credentials_and_data":{"production_credentials":False,"production_data":False,"twilio":False,"customer_systems":False,"payments":False}}
class T(unittest.TestCase):
 def test_inert_plan_passes(self): self.assertEqual(v.validate(copy.deepcopy(BASE)),[])
 def test_hostname_before_approval_fails(self):
  d=copy.deepcopy(BASE);d["dedicated_ingress_identity"]["hostname"]="ao.example.invalid";self.assertTrue(v.validate(d))
 def test_dns_application_detail_fails(self):
  d=copy.deepcopy(BASE);d["dns"]["record_type"]="A";self.assertTrue(v.validate(d))
 def test_route_reuse_fails(self):
  d=copy.deepcopy(BASE);d["route_and_port"]["existing_route_reuse"]=True;self.assertTrue(v.validate(d))
 def test_plaintext_fallback_fails(self):
  d=copy.deepcopy(BASE);d["tls"]["plaintext_fallback"]=True;self.assertTrue(v.validate(d))
if __name__=="__main__":unittest.main()
