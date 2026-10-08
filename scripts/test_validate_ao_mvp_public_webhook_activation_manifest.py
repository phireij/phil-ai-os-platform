#!/usr/bin/env python3
import copy,importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/"validate_ao_mvp_public_webhook_activation_manifest.py"
s=importlib.util.spec_from_file_location("v",P);v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
BASE=json.loads((Path(__file__).resolve().parents[1]/"ops/runtime/ao-mvp-public-webhook-activation-manifest.v1.json").read_text())
class T(unittest.TestCase):
 def test_prepared_manifest_passes(self):self.assertEqual(v.validate(copy.deepcopy(BASE)),[])
 def test_hostname_preselection_fails(self):
  d=copy.deepcopy(BASE);d["ingress"]["hostname"]="example.invalid";self.assertTrue(v.validate(d))
 def test_hermes_reuse_fails(self):
  d=copy.deepcopy(BASE);d["ingress"]["reuse_hermes_hostname"]=True;self.assertTrue(v.validate(d))
 def test_activation_preapproval_fails(self):
  d=copy.deepcopy(BASE);d["public_webhook_activation_authorized"]=True;self.assertTrue(v.validate(d))
if __name__=="__main__":unittest.main()
