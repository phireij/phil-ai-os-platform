# Mission Control dedicated Telegram delivery contract

## Purpose

MC-015 adds a bounded, outbound-only notification path for the dedicated
Mission Control Telegram bot selected by the owner. It is not a Telegram
command channel and does not add provider, assignment, delegation, execution,
or other mutation authority.

## Default state

Delivery is disabled unless all of the following are true:

1. `MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED=true` is set in the reviewed
   CEO-session deployment.
2. `MISSION_CONTROL_TELEGRAM_BOT_TOKEN_FILE` and
   `MISSION_CONTROL_TELEGRAM_CHAT_ID_FILE` name distinct absolute protected
   files, owned and mode-restricted by the deployed secret volume.
3. Encrypted conversation storage is enabled.

An absent or invalid delivery configuration fails closed. Existing
`not_configured` outbox entries remain `not_configured` after an image upgrade;
they are never retroactively sent.

## Content and transport boundary

The only supported outbound API is Telegram `sendMessage` over HTTPS. Each
message contains the event name, the Mission Control notification identifier,
decision identifier, proposal identifier, and `authority effect: none`. It
does not contain conversation text, proposal scope, decision rationale,
credentials, review links, or execution instructions.

The session process does not poll Telegram, accept a webhook, or process an
inbound Telegram message.

## Delivery state machine

New CEO decisions create an outbox entry as `pending` only while the explicit
delivery configuration is enabled. A dispatcher within the existing CEO
session process claims and durably records `in_flight` before it makes a
network request. Confirmed Telegram success becomes `delivered`.

One failed attempt becomes `retry_wait` for exactly 15 minutes. A second
failure becomes `dead_letter`. If the process stops while an item is
`in_flight`, the next dispatcher run marks it `dead_letter` without resending:
this intentionally favors no duplicate notification over uncertain delivery.

The authenticated Mission Control notification view exposes only identifiers,
delivery state, attempt count, and timestamps. It exposes no Telegram secret,
destination, response payload, conversation body, or decision rationale.

## Activation gate

This contract and implementation do not deploy the image, enable the flag,
mount the dedicated secrets, or directly send a Telegram message. Enablement
requires a reviewed storage-preserving deployment procedure. The dedicated
activation workflow is deliberately no-send: only a new authenticated CEO
decision can enqueue normal identifier-only delivery through the durable
outbox. Recipient-confirmed MC-015 delivery acceptance already exists, so
re-enablement alone does not justify replaying or creating another test
notification.
