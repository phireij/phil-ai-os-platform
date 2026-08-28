import unittest

from phil_ai_os_woocommerce.auth import (
    AuthenticationBoundary,
    CredentialBoundaryError,
    CredentialReference,
    NoCredentialsProvider,
    SPRINT3_AUTH_BOUNDARY,
)
from phil_ai_os_woocommerce.localization import DEFAULT_LOCALIZATION_POLICY, project_localized
from phil_ai_os_woocommerce.models import ContractValidationError, LocalizedText


class AuthenticationBoundaryTests(unittest.TestCase):
    def test_default_provider_exposes_no_credentials(self):
        self.assertIsNone(NoCredentialsProvider().get_reference())

    def test_raw_consumer_key_reference_is_rejected(self):
        with self.assertRaises(CredentialBoundaryError):
            CredentialReference(
                identity_alias="fixture-only",
                secret_ref="ck_fixture_value",
            )

    def test_raw_consumer_secret_reference_is_rejected(self):
        with self.assertRaises(CredentialBoundaryError):
            CredentialReference(
                identity_alias="fixture-only",
                secret_ref="cs_fixture_value",
            )

    def test_opaque_reference_is_contract_only(self):
        ref = CredentialReference(
            identity_alias="future-integration",
            secret_ref="secretref:woocommerce/future-integration",
            access_mode="read_only",
            environment="isolated",
        )
        self.assertEqual(ref.secret_ref, "secretref:woocommerce/future-integration")

    def test_default_sprint3_auth_boundary_is_inert(self):
        SPRINT3_AUTH_BOUNDARY.assert_inert()

    def test_authority_bearing_auth_boundary_fails_closed(self):
        with self.assertRaises(CredentialBoundaryError):
            AuthenticationBoundary(resolution_authorized=True).assert_inert()


class LocalizationPolicyTests(unittest.TestCase):
    def test_default_policy_requires_en_and_ja_without_fallback(self):
        DEFAULT_LOCALIZATION_POLICY.assert_safe()
        self.assertEqual(DEFAULT_LOCALIZATION_POLICY.required_locales, ("en", "ja"))
        self.assertFalse(DEFAULT_LOCALIZATION_POLICY.implicit_fallback)

    def test_projection_is_explicit_per_locale(self):
        text = LocalizedText(en="Cake", ja="ケーキ")
        self.assertEqual(project_localized(text, "en"), "Cake")
        self.assertEqual(project_localized(text, "ja"), "ケーキ")

    def test_unsupported_locale_fails_closed(self):
        with self.assertRaises(ContractValidationError):
            project_localized(LocalizedText(en="Cake", ja="ケーキ"), "fr")


if __name__ == "__main__":
    unittest.main()
