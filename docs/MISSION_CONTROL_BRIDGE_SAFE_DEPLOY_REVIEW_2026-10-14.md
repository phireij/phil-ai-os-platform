# Mission Control bridge deployment safeguard review

**Base:** `main` at `f40fe3e2f0c275ab23f753c3356d5765f433e226`.
**Scope:** the manual, isolated agent-posture bridge deployment script and workflow.
**State:** review candidate; no bridge activation authorized by this document.

PR #482 merged the bounded posture v2 bridge and read-only UI consumer. Its six
PR checks and six exact-main workflows passed. The static UI deployed as image
`sha256:83c43240ef7497f0b3fd1ef85c1633f800282bc676119ba94b041f341586502a`;
the public module includes the v2 freshness label and `/healthz` returned 200.
The v2 bridge image was published as
`sha256:7e5b70d2591d0ed146a0b0fdd27e7b4bfe0a266f7e16b0840aa38495fcfb533c`.
The bridge image has not been activated.

## Safeguard added

The prior manual script removed the live bridge before pulling the replacement.
It had no automatic restore path. The revised script validates the digest,
requires a running prior bridge, pulls first, and runs the new image in a
temporary loopback-only preflight container. The preflight reads the existing
protected token inside the container and checks a bounded authenticated v2
response against the host-local read model without printing the token or
response. Only then does it stage the prior bridge under a rollback name and
start the replacement. An activation error attempts to restore the prior
container. The workflow also restores it if public boundary verification fails,
and removes the stopped prior container only after that verification succeeds.

The script compares unrelated running container names/images before and after.
It changes only the named bridge containers. Hermes, Control API, static UI,
and other workloads are outside the changed files and deployment target.

## Evidence and limits

This review does not claim an authenticated production v2 route, deployed bridge
digest, or current agent readiness. Public `401` and mutation `405` checks
remain required after activation. The preflight can fail safely if the existing
secret mount cannot be read by the new image, the local read model is
unavailable, or port 18091 is occupied. That failure leaves the prior bridge
running. The exact production merge and subsequent manual activation each need
their own explicit review and approval under the operational acceptance gate.
