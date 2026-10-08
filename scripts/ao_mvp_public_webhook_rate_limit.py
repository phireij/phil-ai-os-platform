#!/usr/bin/env python3
"""Synthetic in-memory abuse guard for the AO-MVP webhook contract.

This module has no networking or external state. It models the fail-closed
admission rule used by future ingress design.
"""
from collections import deque

class RateLimitReject(Exception):
    pass

class SlidingWindowLimiter:
    def __init__(self, *, limit: int = 10, window_seconds: int = 60):
        if limit < 1 or window_seconds < 1:
            raise ValueError("positive limit/window required")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events = {}

    def admit(self, identity: str, now: int) -> None:
        if not identity or len(identity) > 128:
            raise RateLimitReject("invalid identity")
        q = self._events.setdefault(identity, deque())
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.limit:
            raise RateLimitReject("rate limited")
        q.append(now)

    def active_count(self, identity: str, now: int) -> int:
        q = self._events.get(identity, deque())
        cutoff = now - self.window_seconds
        return sum(1 for t in q if t > cutoff)
