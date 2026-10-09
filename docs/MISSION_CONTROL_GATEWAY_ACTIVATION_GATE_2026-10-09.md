# Mission Control gateway activation gate

The authenticated gateway is packaged as a separate immutable image. It must not be exposed publicly until both activation inputs exist:

1. A CEO authentication secret is provisioned through the approved secret-management path and mounted as `MISSION_CONTROL_CEO_TOKEN_FILE`.
2. A dedicated route is selected and verified, either a separate hostname or an explicit `/api` path route that cannot capture existing workloads.

The provisioning record must identify the CEO principal, secret reference, allowed scopes, rotation owner, and expiry without storing the token value. The minimum first activation scope is `mission_control:read` plus `mission_control:decision_request`; `mission_control:delegate` remains a separate explicit gate.

The gateway image runs as UID/GID `10001`. The VPS secret file must therefore be owned by `root:10001` with mode `0640`; it must never be committed to GitHub or passed as a Docker environment variable.

Until those inputs are available:

- the public `miscon.phireij.cloud` preview remains read-only;
- the gateway may be built and published to GHCR but is not deployed publicly;
- delegation remains disabled unless `MISSION_CONTROL_DELEGATION_ENABLED=true` is explicitly set;
- Hermes and existing Hostinger workloads remain untouched.

Successful image publication is not activation. Activation requires a separate isolated deployment change and end-to-end authenticated verification.
