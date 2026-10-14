# Mission Control CEO conversation UI candidate

**Status:** inactive review candidate. No UI, route, storage, key, provider, or production service is activated by this branch.

## Browser flow

The existing Mission Control page keeps its synthetic transcript while conversation storage is unavailable. It checks the same-origin Google CEO session without reading the HttpOnly cookie. The CEO may open the established Google sign-in flow in a popup; the main window polls only the sanitized session endpoint and closes the popup after authentication.

An authenticated session with `conversation_authority=false` displays **signed in · storage inactive** and keeps all message controls disabled. If a later separately approved service returns `conversation_authority=true`, the page may list the CEO's conversations, open the latest one, create a new empty conversation only after a button press, submit a bounded message with the session CSRF value and a per-operation idempotency key, and render stored messages using text nodes.

The browser stores no cookie, CSRF value, message, token, conversation, or response in local storage, session storage, IndexedDB, or a fixture. It sends cookies only to same-origin routes. Message text never becomes task, approval, delegation, or execution authority.

## Failure behavior

- Missing or expired sessions return the view to disabled sample mode.
- Popup blocking, cancellation, and timeout remain visible without retrying indefinitely.
- API failures keep typed text in the composer and do not fabricate a response.
- A stored CEO message may display `runtime_unavailable`; the UI does not claim that the Chief of Staff answered.
- Sign-out requires the live CSRF token and exact same-origin browser request.

## Rollout boundary

The static Mission Control workflow deploys UI changes automatically after a merge. Therefore this UI must receive focused browser-contract verification and a separate explicit merge/deploy approval. Conversation API routing, persistent volumes, runtime key creation, recovery-vault confirmation, and storage activation remain later guarded changes.

## Verification evidence

Focused conversation UI, existing posture UI, static preview, CEO session, workflow policy, and repository workflow-policy unit checks passed locally on 14 October 2026. The workflow-policy unit test required an unrestricted process only because the managed Windows sandbox denied writes to its temporary test directories; the same seven tests then passed without source changes.

This evidence covers the inactive browser and server contracts. It does not establish a deployed conversation API, durable storage, a production encryption key, recovery-key custody, provider responses, or runtime acceptance.
