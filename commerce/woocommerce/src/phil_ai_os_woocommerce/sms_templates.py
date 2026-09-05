from __future__ import annotations

from dataclasses import dataclass

from .payment_link_sms import PaymentLinkSmsRequest


SUPPORTED_SMS_TEMPLATE_LOCALES = frozenset({"en", "ja", "bilingual"})


@dataclass(frozen=True)
class TransactionalSmsTemplate:
    """Fail-closed transactional SMS copy for the Ruby alphanumeric sender.

    The configured Japan alphanumeric sender is one-way, so the copy deliberately
    never instructs a recipient to reply STOP/HELP. A separate support/opt-out
    contact is mandatory before production rendering.
    """

    locale: str = "bilingual"
    support_contact: str = ""
    brand_name: str = "Ruby's Cake Delights"

    def validate(self) -> None:
        if self.locale not in SUPPORTED_SMS_TEMPLATE_LOCALES:
            raise ValueError("unsupported SMS template locale")
        support_contact = self.support_contact.strip()
        if not support_contact:
            raise ValueError("support_contact is required for SMS help/opt-out readiness")
        if "\n" in support_contact or "\r" in support_contact or len(support_contact) > 120:
            raise ValueError("support_contact must be a concise single-line value")
        brand_name = self.brand_name.strip()
        if not brand_name or "\n" in brand_name or "\r" in brand_name:
            raise ValueError("brand_name must be a non-empty single-line value")

    def render_payment_link(self, sms_request: PaymentLinkSmsRequest) -> str:
        self.validate()
        support_contact = self.support_contact.strip()
        brand_name = self.brand_name.strip()
        japanese = (
            f"{brand_name}｜ご注文{sms_request.order_number}を確認しました。"
            f"お支払い: {sms_request.payment_url} "
            f"お問い合わせ・配信停止: {support_contact}（この送信元へは返信できません）"
        )
        english = (
            f"{brand_name} | Order {sms_request.order_number} confirmed. "
            f"Pay: {sms_request.payment_url} "
            f"Help/opt-out: {support_contact} (this sender cannot receive replies)"
        )
        return self._select(japanese=japanese, english=english)

    def render_help_notice(self) -> str:
        self.validate()
        support_contact = self.support_contact.strip()
        brand_name = self.brand_name.strip()
        japanese = (
            f"{brand_name}｜お問い合わせ: {support_contact}。"
            "この送信元へは返信できません。"
        )
        english = (
            f"{brand_name} | Help: {support_contact}. "
            "This sender cannot receive replies."
        )
        return self._select(japanese=japanese, english=english)

    def render_opt_out_notice(self) -> str:
        self.validate()
        support_contact = self.support_contact.strip()
        brand_name = self.brand_name.strip()
        japanese = (
            f"{brand_name}｜SMS配信停止をご希望の場合: {support_contact}。"
            "この送信元へは返信できません。"
        )
        english = (
            f"{brand_name} | To opt out of SMS: {support_contact}. "
            "This sender cannot receive replies."
        )
        return self._select(japanese=japanese, english=english)

    def _select(self, *, japanese: str, english: str) -> str:
        if self.locale == "ja":
            return japanese
        if self.locale == "en":
            return english
        return f"{japanese}\n{english}"
