# Mission Control CTO and ChatGPT-plan feasibility — 17 October 2026

## Owner intent and decision boundary

The owner wants Codex/ChatGPT to serve as a governed CTO working with Mission Control. Using the owner's ChatGPT subscription is preferred where supported; a Pro $100 purchase is **not** a prerequisite for the next design step. The previously approved OpenAI API implementation remains inactive. This assessment authorizes no credential staging, connection, provider request, deployment, assignment, execution, delegation, or external mutation.

## Supported paths to evaluate

| Path | What it would accomplish | Eligibility and primary gap | First safe pilot |
|---|---|---|---|
| Codex/ChatGPT-side Mission Control connector | Let the CTO workflow read owner-scoped Mission Control status, evidence, and proposal identifiers while the owner works in ChatGPT/Codex. This uses the owner's existing product session, not Mission Control-hosted inference. | Requires a narrowly scoped authenticated MCP tool surface, per-request authorization, data minimization, and a supported private connection. It does not embed a standing agent in the Mission Control server. | Design read-only `get_status` / `get_evidence` contracts using fixture data; review exposure and auth before any connection. |
| Mission Control-hosted ChatGPT-plan usage | Let the Mission Control interface request eligible AI responses using owner-authorized ChatGPT-plan usage. | OpenAI documents open-source/local flows and selected private/commercial access. A remotely hosted private production app must confirm eligibility; OAuth consent, scoped token custody/refresh, host identity, supported models, usage limits, and failure behavior need review. Do not repurpose ChatGPT cookies or Codex credentials. | Obtain an eligibility determination and design only; no live OAuth registration or token transfer. |
| Conventional OpenAI API fallback | Use the already merged bounded response path with the approved US$5/day and per-request token caps. | API charges are separate from a ChatGPT subscription. Protected key staging was blocked by automatic approval review and requires distinct authority; deployment and live calls remain separate gates. | Keep the runtime disabled pending the owner’s provider-path decision. |

## Recommendation

Start with the **read-only CTO context design**, because the owner's objective is a governed CTO workflow rather than a generic chat response. In parallel, determine whether Mission Control's deployment and distribution qualify for the documented ChatGPT-plan flow. Compare actual plan-usage rules and existing subscription capacity before recommending Pro $100. If direct plan usage is unavailable, present the API fallback and its separately billed cost without silently activating it.

The first acceptance gate is a reviewed architecture: exact read fields and provenance, owner authentication, absence of write tools, redaction, audit of connector reads, explicit missing-source coverage, and a revocation path. Later connection, OAuth consent, provider use, and production deployment each require their own approval and evidence. No claim of “Codex residing in Mission Control” is justified by a read-only connector alone; that phrase describes the product objective, not present runtime capability.

## Official documentation reviewed

- [OpenAI: build an MCP server for ChatGPT and Codex](https://developers.openai.com/plugins/build/mcp-server) — tool surface, private-data authentication, read-only annotations, and private deployment considerations.
- [OpenAI: Sign in with ChatGPT quickstart](https://developers.openai.com/siwc/quickstart) — separate identity and plan-usage scopes; limited commercial access.
- [OpenAI: ChatGPT-plan usage overview](https://developers.openai.com/siwc/token-sharing-open-source) — open-source/local-host flow, host identity, and remotely hosted app eligibility warning.
- [OpenAI: Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server) — documented OAuth plan-token route for a host app, not a blanket entitlement for Mission Control.
