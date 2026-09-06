from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from urllib import parse, request

from phil_ai_os_woocommerce.payment_link_sms import PaymentLinkSmsRequest
from phil_ai_os_woocommerce.sms_templates import TransactionalSmsTemplate
from phil_ai_os_woocommerce.twilio_sms import TWILIO_STATUS_CALLBACK_PATH


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "twilio-production-message-readiness-candidate.json"


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: {name.lower()}_missing")
    return value


def _callback_probe(callback_url: str, auth_token: str) -> None:
    unsigned_fields = {
        "MessageSid": "SM00000000000000000000000000000000",
        "MessageStatus": "delivered",
    }
    unsigned_payload = parse.urlencode(unsigned_fields).encode("utf-8")
    unsigned_request = request.Request(
        callback_url,
        data=unsigned_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        request.urlopen(unsigned_request, timeout=10.0)
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code != 403:
            raise SystemExit(
                f"PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: callback_unsigned_http_{code or 'error'}"
            ) from exc
    else:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: callback_unsigned_not_rejected")

    signed_fields = {"MessageStatus": "delivered"}
    material = callback_url + "".join(
        f"{name}{value}" for name, value in sorted(signed_fields.items())
    )
    signature = base64.b64encode(
        hmac.new(auth_token.encode("utf-8"), material.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    signed_payload = parse.urlencode(signed_fields).encode("utf-8")
    signed_request = request.Request(
        callback_url,
        data=signed_payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature,
        },
        method="POST",
    )
    try:
        request.urlopen(signed_request, timeout=10.0)
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code != 400:
            raise SystemExit(
                f"PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: callback_signed_incomplete_http_{code or 'error'}"
            ) from exc
    else:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: callback_signed_incomplete_not_rejected")


def main() -> int:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if record.get("provider_enabled") is not False:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: provider_must_remain_disabled")
    if record.get("controlled_handset_test_executed") is not False:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: handset_test_already_marked_executed")

    account_sid = _required("RUBY_TWILIO_ACCOUNT_SID")
    api_key_sid = _required("RUBY_TWILIO_API_KEY_SID")
    _required("RUBY_TWILIO_API_KEY_SECRET")
    messaging_service_sid = _required("RUBY_TWILIO_MESSAGING_SERVICE_SID")
    auth_token = _required("RUBY_TWILIO_AUTH_TOKEN")
    test_to = _required("RUBY_TWILIO_TEST_TO")

    if not (account_sid.startswith("AC") and len(account_sid) == 34):
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: account_sid_shape_invalid")
    if not (api_key_sid.startswith("SK") and len(api_key_sid) == 34):
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: api_key_sid_shape_invalid")
    if not (messaging_service_sid.startswith("MG") and len(messaging_service_sid) == 34):
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: messaging_service_sid_shape_invalid")
    if not (test_to.startswith("+") and test_to[1:].isdigit() and 8 <= len(test_to[1:]) <= 15):
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: controlled_destination_shape_invalid")

    callback_url = str(record.get("status_callback_url") or "")
    parsed = parse.urlsplit(callback_url)
    if parsed.scheme != "https" or parsed.path != TWILIO_STATUS_CALLBACK_PATH or parsed.query or parsed.fragment:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: callback_contract_invalid")

    template = TransactionalSmsTemplate(
        locale=str(record.get("template_locale") or ""),
        support_contact=str(record.get("support_contact") or ""),
    )
    template.validate()
    rendered = template.render_payment_link(
        PaymentLinkSmsRequest(
            order_id=1,
            order_number="RCD-CONTROLLED-TEST",
            order_status="pending",
            customer_phone="+810000000000",
            amount_minor=1000,
            currency="JPY",
            payment_url="https://www.rubyscakedelights.shop/controlled-test-placeholder",
        )
    )
    if "お問い合わせ・配信停止" not in rendered or "Help/opt-out" not in rendered:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: bilingual_help_opt_out_copy_missing")
    if "Reply STOP" in rendered or "Reply HELP" in rendered:
        raise SystemExit("PHIL_AI_OS_TWILIO_CONTROLLED_TEST_PREFLIGHT_BLOCKED: one_way_sender_reply_instruction_present")

    _callback_probe(callback_url, auth_token)

    print(
        "PHIL_AI_OS_TWILIO_CONTROLLED_TEST_NO_SEND_PREFLIGHT_GREEN "
        "restricted_credentials_present=true callback_live=true bilingual_template=true "
        "support_opt_out=true controlled_destination_present=true provider_enabled=false "
        "message_send=false automatic_retry=false test_authority=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
