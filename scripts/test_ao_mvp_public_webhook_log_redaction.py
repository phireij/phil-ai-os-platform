#!/usr/bin/env python3
import unittest
from ao_mvp_public_webhook_log_redaction import sanitize_webhook_log

class T(unittest.TestCase):
 def test_body_and_headers_never_logged(self):
  x=sanitize_webhook_log({"request_id":"r1","body":{"email":"customer@example.com"},"headers":{"authorization":"Bearer secret"},"decision":"accepted","kind":"synthetic_canary"})
  self.assertNotIn("body",x); self.assertNotIn("headers",x)
 def test_unknown_fields_dropped(self):
  x=sanitize_webhook_log({"harmless_looking_payload":"secret","decision":"accepted","kind":"synthetic_canary"})
  self.assertNotIn("harmless_looking_payload",x)
 def test_unknown_kind_removed(self):
  x=sanitize_webhook_log({"kind":"production_order","decision":"accepted"})
  self.assertNotIn("kind",x)
 def test_authority_forced_none(self):
  x=sanitize_webhook_log({"authority_effect":"write","decision":"accepted","kind":"synthetic_canary"})
  self.assertEqual(x["authority_effect"],"none")
if __name__=="__main__": unittest.main()
