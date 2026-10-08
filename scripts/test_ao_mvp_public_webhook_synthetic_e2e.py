#!/usr/bin/env python3
import unittest
from ao_mvp_public_webhook_synthetic_e2e import run_synthetic_canary
class T(unittest.TestCase):
 def test_network_free_canary(self):
  x=run_synthetic_canary()
  self.assertTrue(x["synthetic_e2e_green"]); self.assertFalse(x["network_used"]); self.assertFalse(x["production_mutation"]); self.assertEqual(x["authority_effect"],"none")
if __name__=="__main__": unittest.main()
