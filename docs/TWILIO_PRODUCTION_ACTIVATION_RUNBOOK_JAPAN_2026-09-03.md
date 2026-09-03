# Twilio Production Activation Runbook — Japan — 2026-09-03

**Program:** Phil AI OS Platform / Ruby's Cake Delights  
**Selected provider:** Twilio — CEO approved 2026-09-03  
**Current state:** Provider selected; live sending remains disabled and fail-closed.

## Purpose

Provide the shortest safe path from provider selection to a verified, controlled production SMS capability without exposing credentials or authorizing live sends prematurely.

## A. Ruby / CEO account-side actions

These actions require access to the Twilio and GitHub account UIs and cannot be substituted by repository code:

1. Create or verify the Twilio account used by Ruby's Cake Delights and ensure it is under Ruby's authorized ownership/control.
2. Complete any Twilio account/business verification requested for the exact Japan transactional SMS use case.
3. Confirm the sender/origination identity that Twilio makes available for the account and Japan destination traffic. Do not assume a sender type until Twilio shows it as available/approved for the account.
4. Obtain the Twilio Account SID and Auth Token from the authorized account.
5. Store them directly as GitHub Actions repository secrets named:
   - `RUBY_TWILIO_ACCOUNT_SID`
   - `RUBY_TWILIO_AUTH_TOKEN`
6. Never paste either value into ChatGPT, GitHub issues/PRs, source files, WordPress, screenshots, or documentation.

## B. CTO automated no-send validation

After the two GitHub secrets are present, run the existing manual workflow:

`.github/workflows/commerce-twilio-production-readonly-preflight.yml`

Input:

`confirm_no_send = true`

The workflow must prove:

- both secret references are present without printing values;
- the Twilio account identity is active/readable;
- no Twilio Messages POST endpoint is present in the preflight path;
- no SMS is sent.

Required markers:

- `PHIL_AI_OS_TWILIO_PRODUCTION_SECRET_REFS_PRESENT`
- successful read-only account verification from `tools_twilio_production_readonly_preflight.py`
- `PHIL_AI_OS_TWILIO_PREFLIGHT_NO_SEND_BOUNDARY_GREEN`

A GREEN read-only preflight does **not** authorize SMS sending.

## C. Message-template acceptance

Before a controlled live test:

1. Approve the final transactional EN/JA message copy.
2. Confirm the message contains no card/payment credentials or sensitive customer data.
3. Keep the payment action limited to the secure WooCommerce payment URL.
4. Verify expected SMS segmentation/cost from the final text in the actual Twilio account/tooling.
5. Confirm the message is only eligible after Ruby approval when the order is in the payment-required state defined by the existing SMS contract.

## D. Delivery-status/webhook acceptance

Before production readiness can become GREEN:

1. Configure the approved delivery-status callback endpoint.
2. Verify Twilio callback authenticity/signature handling.
3. Verify provider delivery states map into the Phil AI OS audit model without exposing secrets or full payment links.
4. Preserve deterministic idempotency and duplicate suppression.
5. Keep automatic retry disabled for V1 unless separately designed and approved.

## E. Controlled handset test

This is the first step that can send an SMS and therefore remains a separate live-test gate.

When all preceding checks are GREEN:

1. Use only an explicitly approved test recipient number.
2. Send one controlled transactional message.
3. Confirm handset receipt.
4. Confirm the WooCommerce payment link opens correctly.
5. Confirm only one SMS was sent for the idempotency key/order event.
6. Confirm delivery status is recorded correctly.
7. Confirm no sensitive credential or payment-link leakage in normal logs.

Do not proceed to customer production sending if any step fails.

## F. Production sending readiness

Mark production SMS readiness GREEN only when all are true:

- Twilio formally selected — **GREEN**;
- Ruby-owned/authorized Twilio account — GREEN;
- credentials in approved GitHub secret boundary — GREEN;
- Japan sender identity/account eligibility verified — GREEN;
- final bilingual template approved — GREEN;
- delivery-status webhook verification — GREEN;
- controlled handset/payment-link test — GREEN;
- duplicate/idempotency behavior — GREEN;
- final launch/Go-No-Go gates permit the SMS lane.

Until then:

- `production_sending_ready = false`
- `live_sms_authorized_by_readiness = false`
- `automatic_retry = false`

## Current next action

**Account-side action:** create/verify the Ruby-owned Twilio account, complete the applicable Twilio verification/sender setup, and save the Account SID/Auth Token directly into GitHub Actions secrets using the two names above. Once that is done, the CTO can run the existing non-sending preflight autonomously.
