# Mission Control CEO Google sign-in integration

**Status:** identity-only probe deployed; CEO session and conversation access inactive. **Owner choice:** Google account or Google Workspace, 14 October 2026. The CEO reported a successful controlled probe sign-in; its exact issuer/subject pair is held in protected Actions secret `MISSION_CONTROL_CEO_BINDING`, not in this repository.

The checked-in `contracts/mission-control/google-oidc-session.v1.json` remains an inactive, non-secret configuration record. Its schema pins the selected issuer, callback, and scope while requiring `enabled=false` and `ceo_subject=null`; the live binding stays in a protected file. This contract cannot authorize a live runtime by itself.

`ops/mission-control-identity/google_oidc_config.py` provides a fail-closed configuration guard. It refuses to load unless explicitly enabled and the exact Google issuer/callback, client ID, and protected regular files for the client secret and CEO binding are present. The guard itself performs no OAuth or session action. `google_ceo_session.py` is a separately reviewable, inactive session implementation; it is not deployed or authorized for conversation access.

## Fixed boundary

- Use Google's OIDC discovery document at `https://accounts.google.com/.well-known/openid-configuration`. Accept the exact issuer values documented by Google and pin the expected issuer in configuration; do not accept an arbitrary issuer from a request.
- Register one web OAuth client with the exact redirect URI `https://miscon.phireij.cloud/auth/google/callback`. This path is reserved for the future isolated session service; it is not live now. Keep the client secret in a protected deployment secret, never in repository files, browser code, Docker labels, or workflow logs. Use Authorization Code with PKCE, state, and nonce. Request only `openid email` unless a later reviewed feature needs more.
- Validate the ID token against Google's discovery/JWKS with an explicit algorithm allowlist and verify issuer, audience, expiry, not-before when present, and nonce. Reject missing or duplicate security claims. Store the CEO authorization binding as the exact `(issuer, sub)` pair. Email is display or recovery context only; it must not authorize the CEO.
- The session service must be isolated from the existing read-only bearer gateway. It may issue only an opaque, server-side session cookie using the previously proposed `__Host-` Secure, HttpOnly, SameSite=Lax, Path=/ attributes. Apply server-side idle/absolute expiry, logout and revocation. Strip all incoming identity headers at the trusted proxy boundary before setting any authenticated identity; an untrusted header cannot become a principal.
- Bind conversation ownership and every list/read/write to the validated CEO principal and dedicated `mission_control:conversation` scope. Require exact Origin and CSRF token on writes. The present shared bearer and historical BasicAuth `ceo` password are not valid conversation identities. Keep project status and task authority separate.

## Isolation and rollout

1. Build the OIDC callback/session service and conversation routes on an isolated path and container, disabled by default. Do not modify the current `/api/snapshot` or `/api/agent-posture` routes or Traefik's existing workloads.
2. Before enabling any route, record the non-secret OAuth client ID, exact redirect URI, configured issuer/audience, CEO subject binding through a controlled first sign-in, session expiry settings, and revocation owner. A personal Google account and a Workspace account are both possible; any Workspace domain restriction is an additional policy and cannot replace `sub` binding.
3. Review the exact diff, container image digest, proxy labels, and rollback. Activate only after a separate production approval and evidence for invalid signature/issuer/audience/expiry, replayed state/nonce, cross-principal denial, CSRF/Origin denial, logout/revocation, cookie attributes, and redacted logs. No conversation content or provider request before the storage and provider gates pass.

### CEO account binding

Do not automatically enroll the first Google user who reaches the callback. The first approved rollout is an **identity probe** only: it completes Google OIDC in the isolated service, validates the ID token, and displays the validated issuer and subject to that signed-in browser. It grants no Mission Control session or conversation scope, persists no conversation content, and emits no ID token, authorization code, client secret, or subject into CI logs. The CEO can then provide the issuer and subject through the agreed owner channel; an operator installs that exact binding in a protected file and disables probe mode. The final session service must deny every other subject, including another account with the same email or Workspace domain. Probe deployment and final session activation each require their own reviewed production approval and rollback evidence.

The deployed probe source is `ops/mission-control-identity/google_identity_probe.py`, with a separate `Dockerfile.mission-control-google-identity-probe`. It starts only with `MISSION_CONTROL_GOOGLE_PROBE_ENABLED=true`, the exact registered client ID, and an owner-only protected client-secret file. The approved isolated deployment run is [38509523115](https://github.com/phireij/phil-ai-os-platform/actions/runs/38509523115). Its bounded `/auth/google/healthz` GET reports only probe readiness and `authority_effect=none`; the owner separately reported a successful sign-in. The probe grants no CEO session or conversation scope.

### Inactive CEO session candidate

`google_ceo_session.py` requires the configuration guard and exact protected binding `issuer|subject` before it starts. It reuses the probe's bounded Google token validation, rejects every other subject, and creates only an opaque in-memory server-side session. The `__Host-mc-ceo-session` cookie is Secure, HttpOnly, SameSite=Lax, and has no persistent browser lifetime. Sessions expire after 30 minutes idle or eight hours absolute; logout requires exact Origin and a per-session CSRF token. Restarting the isolated container revokes all sessions. The candidate exposes no conversation route or storage, and `/auth/google/session` reports `conversation_authority=false`.

Its image is built for review only. There is no publish or deployment workflow for this session candidate. A separate reviewed rollout must replace the probe route, stage both protected files without logging their values, verify the exact image digest and host routing, and preserve rollback. A working CEO session still would not activate conversation storage, provider calls, or task authority; those remain separate gates.
Before a probe deployment plan is accepted, inspect the current live Traefik routers for `/auth/google/start` and `/auth/google/callback` collisions, confirm that only the dedicated HTTPS entrypoint can reach the probe, and keep the container off the Control API and Hermes networks. Repository routing text alone does not prove live route availability.

## Configuration that must come from the owner environment

The Google Cloud OAuth web-client registration and exact authorized redirect URI above must exist in an owner-controlled Google Cloud project. The client secret must be installed through the protected runtime mechanism; do not send it in chat. The CEO identity must be bound by a successful controlled Google sign-in, without copying an ID token into chat. Until those steps are evidenced, MC-006 remains open and the 20 October acceptance target remains very high risk.

Primary reference: https://developers.google.com/identity/openid-connect/openid-connect
