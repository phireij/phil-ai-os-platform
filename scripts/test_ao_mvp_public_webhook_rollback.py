#!/usr/bin/env python3
import copy, unittest
from ao_mvp_public_webhook_rollback import REQUIRED_ACTIONS, validate_rollback
BASE={"authority_effect":"none","production_mutation":False,"touch_hermes":False,"actions":list(REQUIRED_ACTIONS),"fail_closed_on_unknown":True}
class TestRollback(unittest.TestCase):
 def test_exact_plan_passes(self): self.assertEqual(validate_rollback(copy.deepcopy(BASE)),[])
 def test_hermes_touch_rejected(self):
  d=copy.deepcopy(BASE); d["touch_hermes"]=True; self.assertTrue(validate_rollback(d))
 def test_missing_action_rejected(self):
  d=copy.deepcopy(BASE); d["actions"]=d["actions"][:-1]; self.assertTrue(validate_rollback(d))
 def test_prod_mutation_rejected(self):
  d=copy.deepcopy(BASE); d["production_mutation"]=True; self.assertTrue(validate_rollback(d))
if __name__=="__main__": unittest.main()
