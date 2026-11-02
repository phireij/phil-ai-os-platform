"""Offline contract checks for the disabled-by-default Ruby Gate A fixture."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ruby_review_synthetic import (
    SYNTHETIC_SURFACE_ENV,
    ruby_review_synthetic_surface,
    synthetic_surface_enabled,
)


class RubyReviewSyntheticChecks(unittest.TestCase):
    def test_surface_is_exact_fixture_only_and_non_authorizing(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SYNTHETIC_SURFACE_ENV, None)
            self.assertFalse(synthetic_surface_enabled())
        with patch.dict(os.environ, {SYNTHETIC_SURFACE_ENV: "true"}, clear=False):
            self.assertTrue(synthetic_surface_enabled())
        with patch.dict(os.environ, {SYNTHETIC_SURFACE_ENV: "TRUE"}, clear=False):
            self.assertFalse(synthetic_surface_enabled())

        payload = ruby_review_synthetic_surface()
        self.assertEqual("synthetic_fixture", payload["mode"])
        self.assertEqual("same_origin_session_only", payload["owner_access"])
        self.assertFalse(payload["exports_enabled"])
        self.assertFalse(payload["activation_authorized"])
        self.assertEqual("none", payload["authority_effect"])
        self.assertFalse(payload["execution_authorized"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertEqual(1, len(payload["records"]))
        self.assertEqual(1, len(payload["audit"]))
        self.assertTrue(payload["records"][0]["synthetic"])
        self.assertTrue(payload["audit"][0]["identifier_only"])


if __name__ == "__main__":
    unittest.main()
