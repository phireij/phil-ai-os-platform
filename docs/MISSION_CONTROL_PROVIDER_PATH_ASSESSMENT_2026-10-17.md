# MC-010 provider path assessment — 17 October 2026

## Decision and observed implementation

Preserve the owner's ChatGPT-first preference. The existing CEO session stores messages with `runtime_unavailable`; it does not yet contain a live provider adapter. The repository is public, but repository visibility alone does not prove client eligibility or account entitlement. No provider request, registration, credential installation, or production activation was performed for this assessment.

## Official documentation findings

- [Sign in with ChatGPT quickstart](https://developers.openai.com/siwc/quickstart): eligible participating apps can use ChatGPT plans with separate user consent; identity-only sign-in does not grant inference access. Availability depends on the app/client class.
- [Plan-usage overview](https://developers.openai.com/siwc/token-sharing-open-source): describes open-source/local clients, distinguishes client registration from persistent host identity, and directs remotely hosted commercial offerings to an interest process.
- [Self-hosted VMs](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms): investigate this documented path for the owner-operated Mission Control VPS before concluding that separate API billing is required.
- [API authentication](https://developers.openai.com/api/reference/overview): conventional API integration uses separately provisioned credentials. That remains an alternative only if the owner selects it.

## Next implementation gates

1. Establish whether the owner-operated deployment qualifies for the documented self-hosted client flow; do not infer entitlement from repository visibility.
2. Specify registration, callback/PKCE, owner linking, protected token persistence/refresh, and stable host identity while retaining Google as Mission Control's CEO authentication boundary.
3. Verify the request/model contract, 4,000 total input-token ceiling, 750 output-token ceiling, and enforceable mapping of the approved US$5/day limit to plan usage. Fail closed if cost or entitlement cannot be established; never silently substitute a different usage limit.
4. Implement the response lifecycle with no tools, no delegation, no external actions, bounded timeouts, encrypted durable results, and no automatic replay after ambiguous outcomes. Sensitive personal/customer data remains excluded.
5. Verify offline first; present any registration/account requirement and exact deployment for the existing approval gates before live inference.

The next work is feasibility and a reviewable implementation contract, not an API activation request. Full MC-010 acceptance still requires an authorized real response and enforced limits.
