#!/usr/bin/env python3
import unittest
from ao_mvp_public_webhook_rate_limit import RateLimitReject, SlidingWindowLimiter

class TestLimiter(unittest.TestCase):
    def test_limit_fails_closed(self):
        x=SlidingWindowLimiter(limit=3,window_seconds=60)
        for t in (100,101,102): x.admit("synthetic-source",t)
        with self.assertRaises(RateLimitReject): x.admit("synthetic-source",103)
    def test_window_recovers(self):
        x=SlidingWindowLimiter(limit=2,window_seconds=60)
        x.admit("a",100); x.admit("a",101); x.admit("a",160)
        self.assertEqual(x.active_count("a",160),2)
    def test_identities_isolated(self):
        x=SlidingWindowLimiter(limit=1,window_seconds=60)
        x.admit("a",100); x.admit("b",100)
        with self.assertRaises(RateLimitReject): x.admit("a",101)
    def test_bad_identity_rejected(self):
        x=SlidingWindowLimiter()
        with self.assertRaises(RateLimitReject): x.admit("",100)

if __name__=="__main__": unittest.main()
