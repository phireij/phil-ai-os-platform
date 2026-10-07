#!/usr/bin/env python3
import json
import unittest
from ao_mvp_public_webhook_contract import Reject, evaluate_request, synthetic_headers, MAX_BODY_BYTES

SECRET=b"synthetic-test-secret"
NOW=1791359000

def body(kind="synthetic_canary"):
    return json.dumps({"event_id":"evt-test-1","kind":kind},separators=(",",":")).encode()

class TestWebhookContract(unittest.TestCase):
    def good(self):
        b=body(); return b, synthetic_headers(SECRET,NOW,"nonce-1",b)
    def test_valid_synthetic_canary_has_no_authority(self):
        b,h=self.good(); out=evaluate_request(secret=SECRET,headers=h,body=b,now=NOW)
        self.assertEqual(out["authority_effect"],"none"); self.assertNotIn("payload",out)
    def test_bad_signature_fails_closed(self):
        b,h=self.good(); h["x-ao-signature"]="0"*64
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW)
    def test_stale_request_fails_closed(self):
        b,h=self.good()
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW+301)
    def test_replay_fails_closed(self):
        b,h=self.good()
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW,seen_nonces={"nonce-1"})
    def test_oversized_fails_closed(self):
        b=b"x"*(MAX_BODY_BYTES+1); h=synthetic_headers(SECRET,NOW,"nonce-2",b)
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW)
    def test_wrong_content_type_fails_closed(self):
        b,h=self.good(); h["content-type"]="text/plain"
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW)
    def test_unknown_schema_fails_closed(self):
        b=json.dumps({"event_id":"x","kind":"synthetic_canary","extra":"no"}).encode()
        h=synthetic_headers(SECRET,NOW,"nonce-3",b)
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW)
    def test_non_canary_kind_fails_closed(self):
        b=body("production_order"); h=synthetic_headers(SECRET,NOW,"nonce-4",b)
        with self.assertRaises(Reject): evaluate_request(secret=SECRET,headers=h,body=b,now=NOW)

if __name__=="__main__": unittest.main()
