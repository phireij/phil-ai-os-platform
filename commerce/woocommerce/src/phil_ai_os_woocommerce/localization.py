from __future__ import annotations

from dataclasses import dataclass

from .models import ContractValidationError, LocalizedText


SUPPORTED_LOCALES = ("en", "ja")


@dataclass(frozen=True)
class LocalizationPolicy:
    """Explicit bilingual projection policy for Sprint 3.

    Canonical commerce data requires both English and Japanese. There is no
    silent cross-language fallback: missing canonical translations and unknown
    locales fail closed instead of producing ambiguous storefront content.
    """

    required_locales: tuple[str, ...] = SUPPORTED_LOCALES
    missing_translation_behavior: str = "reject"
    unsupported_locale_behavior: str = "reject"
    implicit_fallback: bool = False

    def assert_safe(self) -> None:
        if self.required_locales != SUPPORTED_LOCALES:
            raise ContractValidationError("Sprint 3 requires canonical English and Japanese")
        if self.missing_translation_behavior != "reject":
            raise ContractValidationError("missing translations must fail closed")
        if self.unsupported_locale_behavior != "reject":
            raise ContractValidationError("unsupported locales must fail closed")
        if self.implicit_fallback:
            raise ContractValidationError("implicit localization fallback is not permitted")


DEFAULT_LOCALIZATION_POLICY = LocalizationPolicy()


def project_localized(text: LocalizedText, locale: str) -> str:
    """Project one canonical bilingual field under the strict Sprint 3 policy."""

    DEFAULT_LOCALIZATION_POLICY.assert_safe()
    if locale == "en":
        return text.en
    if locale == "ja":
        return text.ja
    raise ContractValidationError(f"unsupported locale: {locale}")
