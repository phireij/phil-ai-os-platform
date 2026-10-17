# MC-010 provider activation contract — 17 October 2026

The implementation in PR #582 wires the response runtime into the CEO session behind protected configuration. The staged-rollout follow-up adds a separate dispatch gate. The current production container has no API configuration or worker. A storage-preserving deployment and a live test remain separate decisions.

## Reviewed defaults and ceiling

The only permitted model is `gpt-6-luna`. Its [published model page](https://developers.openai.com/api/docs/models/gpt-6-luna) lists Standard text rates of US$0.10 input and US$0.50 output per million tokens and supports `reasoning.effort=none`. The activation policy must reserve at least four times those rates: 400,000 and 2,000,000 micro-USD per million tokens. The reservation covers two full 4,000-token input charges (input counting plus generation) and 750 output tokens, or at least US$0.0047 per request at those floor rates. It is retained even when usage is lower. An expiring policy file is required, with at most seven days of validity when the process starts. Model/pricing and the counting endpoint must be reviewed again before the first live call and at every renewal.

The [input-count endpoint](https://developers.openai.com/api/docs/guides/token-counting) counts the complete request, including instructions and framing. The count call transmits the CEO's text to OpenAI. The [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) enforces `max_output_tokens=750`, including nonvisible output. Tools are excluded; output is advisory text only. No sensitive personal/customer data is permitted in the initial use. There is no automated content classifier.

The application cap is US$5 per JST day across this single Mission Control process. It is separate from account-wide usage. Neither deployment nor this code grants provider authority to assign, execute, delegate, notify or change external systems.

## Protected configuration

Configuration requires `MISSION_CONTROL_OPENAI_ENABLED=true`, storage enabled, and both protected files below. It validates the files but keeps responses unavailable. Dispatch additionally requires `MISSION_CONTROL_OPENAI_DISPATCH_ENABLED=true`; the controlled upgrade workflow cannot set this second flag. The defaults are disabled and invalid values fail startup. The storage-preserving read-only image preflight never starts a provider worker.

| Environment variable | Value when explicitly activated |
| --- | --- |
| `MISSION_CONTROL_OPENAI_API_KEY_FILE` | Absolute path to a private API key file, mounted read-only and never logged. |
| `MISSION_CONTROL_OPENAI_POLICY_FILE` | Absolute path to a private JSON policy file, mounted read-only. |

Policy schema: `{"model":"gpt-6-luna","input_rate":400000,"output_rate":2000000,"valid_until":<Unix seconds>}`. Those rates are minimums, not defaults supplied by the app; the operator must review and provide a current policy. The policy must be unexpired and no more than seven days ahead when dispatch starts. A stop/restart is required to replace it. The runtime checks expiry before each queued dispatch. A protected single-writer lock prevents a second dispatching process from using the same encrypted state concurrently.

The manual storage-preserving upgrade accepts `configure_openai` (default false). With explicit approval, it checks the mounted `openai/api_key` and `openai/policy.json` files under the existing secret volume without printing their contents, validates the policy offline, preserves the encrypted state and rollback, and carries only the configuration setting. It cannot turn on dispatch. An active configuration is preserved across later upgrades; an active dispatching process blocks this workflow pending a separately reviewed procedure.

The encrypted conversation state directory also holds a private HMAC budget anchor outside the conversation backup package. It records the reserved attempts and their charged JST day. Startup fails if a restored snapshot drops or alters those reservations, or if the anchor disappears after an attempt. The provider worker stops on persistence errors and does not replay uncertain requests. No automatic reconciliation or release of unknown reservations is provided. Recovery with a mismatched anchor requires a separately reviewed manual procedure.

## Remaining deployment and acceptance gates

1. Merge this reviewed implementation and verify the CI image and offline tests.
2. Confirm the API account, project key, current pricing, counting-endpoint billing, processing region and applicable terms; prepare the two protected files without placing secrets in the repository or chat.
3. Review an exact storage-preserving deployment plan that carries configuration only, protects the files, preserves the encrypted volume and budget anchor, and retains rollback. Obtain explicit deployment approval.
4. Review a separate one-call dispatch procedure and obtain approval for a synthetic live input-count and generation acceptance. Observe 4,000/750 limits, daily reservation, response persistence and no tool activity before closing MC-010.

The current status is implementation under review; live provider acceptance remains outstanding.
