# Mission Control CEO Google sign-in integration

**Status:** design selected; inactive. **Owner choice:** Google account or Google Workspace, 14 October 2026. This selects Google as the OIDC issuer direction; it does not establish a configured OAuth client, a CEO subject, or a working session.

The checked-in `contracts/mission-control/google-oidc-session.v1.json` is an inactive, non-secret configuration record. Its schema pins the selected issuer, callback, and scope while requiring `enabled=false`. The owner supplied the web client ID only; CEO subject remains unset. It cannot be used as a live runtime configuration until a separately reviewed contract and implementation replace it.

`ops/mission-control-identity/google_oidc_config.py` provides an inactive configuration guard for the future service. It refuses to load unless explicitly enabled and the exact Google issuer/callback, a syntactically valid client ID, and protected regular files for the client secret and CEO subject are present. It does not perform OAuth, create sessions, or grant access. The identity service image, routes, verification logic, and secure installation remain to be implemented and reviewed.

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

## Configuration that must come from the owner environment

The Google Cloud OAuth web-client registration and exact authorized redirect URI above must exist in an owner-controlled Google Cloud project. The client secret must be installed through the protected runtime mechanism; do not send it in chat. The CEO identity must be bound by a successful controlled Google sign-in, without copying an ID token into chat. Until those steps are evidenced, MC-006 remains open and the 20 October acceptance target remains very high risk.

Primary reference: https://developers.google.com/identity/openid-connect/openid-connect
