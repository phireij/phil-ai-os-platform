# Synthetic original-source custody

This inactive source extension retains the canonical original Ruby handoff in the same encrypted snapshot and atomic transaction as its accepted inquiry revision, receipt and audit. It adds no route, live identity, staff grant, provider, network transport or activation. Real customer data and reference images remain unsupported.

## Explicit local composition

Both `RubyInquiryPolicy.source_handoff_retention_enabled is True` and a trusted server-injected `ConversationStore(..., ruby_inquiry_source_mapper=...)` are required. The mapper receives detached source and contact dictionaries and must return the exact normalized inquiry. Private Ruby supplies its existing strict mapper and a pinned catalog; Core does not import private application code or accept a callback/catalog from a request.

`create_ruby_inquiry`, `revise_ruby_inquiry` and `resolve_ruby_inquiry_receipt` accept the optional keyword-only `source_handoff_body` as strict JSON bytes. Omission preserves the legacy request format and canonical request fingerprint. A new source-backed write uses an internal, closed `ruby.inquiry-source-custody.v1` envelope containing the original normalized request and source. That complete envelope participates in the existing accepted request hash and idempotency identity. The envelope is not a new accepted wire request schema.

Source JSON must be an object, with finite safe integers (no floating-point values), at most 16 nesting levels and 8,192 values. Duplicate keys, invalid UTF-8, surrogates and unsupported values fail closed. Each input and the combined canonical envelope are bounded by the existing 128 KiB request limit. The trusted private mapper rejects unsupported source fields, images and authority claims and must reproduce the normalized inquiry exactly. Canonical original means JSON values, not original whitespace or encoding.

A same-key replay must supply the same normalized request and canonical source. Changed or absent source conflicts. Original replay/resolution and source reads do not remap against a newer catalog; new writes use the current trusted mapper and Core catalog policy. The existing CX synthetic adapter is deliberately unchanged: it still uses source-less requests and fingerprints only its request body. Do not silently attach source in that adapter.

## Exact private read

`get_ruby_inquiry_source(context, inquiry_id, expected_revision_id)` checks the existing exact owner binding, project/source scope, synthetic policy and both source opt-ins. It requires the current revision and verifies its complete request hash, revision shape, matching receipt and atomic audit before returning the source and its canonical SHA-256 fingerprint with `cache_control: no-store` and unchanged no-authority flags. This is a trusted in-process method, not independent authentication or a browser endpoint.

Ordinary inquiry detail, lists, receipts and audits do not expose the original handoff or its fingerprint. Legacy revisions explicitly lack source; stale reads fail rather than return an older source. A legacy inquiry can gain source only through an explicit new accepted revision. Once source-backed, a new revision must supply a newly validated source; there is no silent downgrade or inheritance.

## Custody and recovery

There is no separate source ledger or post-acceptance attachment. Source follows the existing inquiry revision lifetime in encrypted custody, with no new retention period or deletion behavior. SQL faults roll back all components. Ambiguous persistence fences the whole store; authorized disk reconciliation and original receipt resolution apply unchanged. Missing or contradictory history never reconstructs source or mints a replacement receipt. Full source JSON is never included in errors or logs.

The finalized-quote implementation unwraps the internal envelope before using the retained contact, while checking the full accepted request hash. Quote authority and policy remain unchanged. Private Ruby can retrieve exact source and then use its existing prepare operation, which rereads the current revision; Core's atomic check still protects later recording.

This source does not authorize live retention. Before using real customer information, separately review data scope, consent, retention/deletion, access and delivery. Audience selection and secure hosted composition remain distinct work.

## Tests

`test_ruby_inquiry_source.py` covers bounds, default-off policy, canonical replay, legacy compatibility, no default exposure, exact revision and scope, immutable source, corrupted/missing evidence, rollback, persistence uncertainty, real child-process crash/restart and source-less downgrade rejection. The existing CEO CI unit-test step invokes it without changing any workflow triggers, permissions, builds or publication conditions. Local task evidence also runs the unchanged inquiry/quote/custody/consent suites with inherited kernel network denial. Private paired acceptance uses the actual JavaScript producer and Ruby normalization/preparation source; it is maintained separately from public Core.
