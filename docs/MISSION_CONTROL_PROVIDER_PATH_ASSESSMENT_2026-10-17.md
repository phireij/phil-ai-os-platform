# MC-010 provider path assessment — 17 October 2026

## Decision and observed implementation

**Latest owner decision:** conventional OpenAI API implementation is approved with US$5/day, 4,000 input tokens and 750 generated tokens. Deployment and live calls remain separately gated. The feasibility discussion below is historical; implementation is no longer blocked on provider-route selection.

### Inactive implementation and remaining gates

- `provider_runtime.py` implements an injected runtime and fixed-origin HTTPS transport. Production startup does not construct it: no worker, enable switch, credential discovery or automatic live call is added.
- Only the current CEO message and fixed advisory instructions are sent, never implicit history. No tools, execution, delegation or notifications are supplied. Sensitive-data exclusion remains an operating policy, not an automated classifier.
- The official [input-token endpoint](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count) counts the exact instructions/input before inference. Counts above 4,000 prevent generation. The counting request itself transmits input and needs live-call approval; it is not local counting.
- Generation sets `max_output_tokens=750`, `store=false`, no tools and no retry. Only complete assistant text with matching model and bounded usage is accepted.
- Before either network request, the encrypted store reserves maximum cost for 4,000 input and 750 output tokens using an explicitly injected, reviewed, expiring model/rate policy. No production model/rate is selected here. Integer micro-USD avoids floating-point accounting. Successful requests retain the full reservation conservatively.
- Daily buckets use JST. Unknown/in-flight reservations carry across days; successful requests spanning midnight count on completion day. Deleting a conversation cannot replenish budget. Claim persistence failure prevents network access; restart/final-persistence failure never automatically replays an uncertain attempt.
- Concurrency protection assumes the existing single writer process. This is application-local budgeting, not an account-wide OpenAI cap. Restoring an older snapshot or starting another writer requires reconciliation before activation; neither is safe for an active provider by default.
- Transport uses a fixed TLS origin, no proxies/redirects/retries, bounded socket operations, a body-read deadline and a 256-KiB response limit. Host DNS resolution is not a hard application-wide deadline.
- Offline tests use mocked transports and synthetic fixtures, covering caps, policy expiry, invalid output, fixed origin, disabled default, encrypted response persistence, concurrent budget claims, deletion/restart and persistence failures. Linux CI also runs existing session/storage/Telegram tests and builds an inactive image.

Next: review/merge the dormant implementation, then review pinned model/rates, count-endpoint compatibility and billing, protected credentials, explicit startup/worker enable and kill switches, single-writer enforcement and recovery-budget reconciliation. Include counting-endpoint charges in reservations if applicable; fail closed until verified. Deployment of an exact image and a synthetic live counting/generation test each need separate approval. MC-010 remains in progress until that evidence exists.

Preserve the owner's ChatGPT-first preference. The existing CEO session stores messages with `runtime_unavailable`; it does not yet contain a live provider adapter. The repository is public, but repository visibility alone does not prove client eligibility or account entitlement. No provider request, registration, credential installation, or production activation was performed for this assessment.

## Official documentation findings

- [Sign in with ChatGPT quickstart](https://developers.openai.com/siwc/quickstart): eligible participating apps can use ChatGPT plans with separate user consent; identity-only sign-in does not grant inference access. Availability depends on the app/client class.
- [Plan-usage overview](https://developers.openai.com/siwc/token-sharing-open-source): describes open-source/local clients, distinguishes client registration from persistent host identity, and directs remotely hosted commercial offerings to an interest process.
- [Self-hosted VMs](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms): investigate this documented path for the owner-operated Mission Control VPS before concluding that separate API billing is required.
- [API authentication](https://developers.openai.com/api/reference/overview): conventional API integration uses separately provisioned credentials. That remains an alternative only if the owner selects it.

## Next implementation gates

### Verified compatibility blocker

The [ChatGPT-plan preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) explicitly list `max_output_tokens` as unsupported. The [inference contract](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) requires streaming and a completed terminal event. A prompt instruction, display truncation, or client disconnect cannot be treated as a provider-enforced 750-token generation cap. Therefore this path cannot currently be approved against the unchanged hard-limit contract. The US$5/day mapping to subscription/credit usage also remains unverified.

The conventional [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) supports `max_output_tokens`, including reasoning and visible output. Recommended next owner choice: authorize implementation of the separately billed API path specifically for Mission Control responses while retaining ChatGPT for primary interactive use. Preserve the US$5/day ceiling, 4,000 total input tokens, 750 generated tokens, no tools, and sensitive-data exclusion. Implementation approval would not itself authorize a production deployment or paid test call.

If the owner instead retains plan-only integration, the hard output/spend contract needs an explicitly approved revision; do not silently weaken it. No live provider or account change was made.

### Original proposed conventional-API contract (superseded by approved implementation above)

- Count the complete serialized model input, including instructions/history, with a verified model tokenizer; reject above 4,000 before dispatch.
- Set `max_output_tokens=750`; reject unknown model/pricing combinations and supply no tools. A cap-limited response is incomplete, not silently successful.
- Atomically reserve worst-case input/output cost against a durable US$5 ledger before dispatch; count outstanding reservations against the ceiling. Retain reservations after timeout/ambiguous results, with no automatic retry. Select and document the daily reset timezone before activation.
- Commit dispatch intent before network access; persist the final response in the existing encrypted owner-bound store. Never log prompt, response, or credential content.
- Start disabled, use mocked transport for offline checks, and require separate protected credential configuration and approved deployment/test before live requests.

### Historical ChatGPT-plan feasibility gates (deferred)

1. Establish whether the owner-operated deployment qualifies for the documented self-hosted client flow; do not infer entitlement from repository visibility.
2. Specify registration, callback/PKCE, owner linking, protected token persistence/refresh, and stable host identity while retaining Google as Mission Control's CEO authentication boundary.
3. Verify the request/model contract, 4,000 total input-token ceiling, 750 output-token ceiling, and enforceable mapping of the approved US$5/day limit to plan usage. Fail closed if cost or entitlement cannot be established; never silently substitute a different usage limit.
4. Implement the response lifecycle with no tools, no delegation, no external actions, bounded timeouts, encrypted durable results, and no automatic replay after ambiguous outcomes. Sensitive personal/customer data remains excluded.
5. Verify offline first; present any registration/account requirement and exact deployment for the existing approval gates before live inference.

These plan-route feasibility steps are deferred following API implementation approval. Full MC-010 acceptance still requires an authorized real response and enforced limits.
