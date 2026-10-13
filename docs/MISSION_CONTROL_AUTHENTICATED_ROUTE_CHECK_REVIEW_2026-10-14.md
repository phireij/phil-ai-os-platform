# Mission Control authenticated route check review

**Base:** `main` at `b6d72b9eb9a3b3485a3e75f84c4c2f79ba2cae58`.
**Scope:** manually dispatched, read-only verification of the existing CEO bearer route.
**State:** review candidate; no workflow run or production merge is authorized by this note.

The host-local v2 bridge preflight passed during approved deployment run
[38470803100](https://github.com/phireij/phil-ai-os-platform/actions/runs/38470803100).
That does not prove a CEO token succeeds through the public HTTPS route. The
new workflow checks the expected active bridge digest, running state, host
network, and read-only root filesystem. It then runs a bounded Python probe
inside that container, where the existing protected token is already mounted.

The probe makes only two GETs to the pinned public Mission Control hostname:
`/api/snapshot` and `/api/agent-posture`. It validates HTTPS certificates,
refuses redirects and proxies, caps each response at 1 MiB, checks the v2
posture authority and privacy shape, and emits only pass/fail markers. It does
not print the token or response data, write project status, send a provider
request, or change any container or route. No credential setup is requested.

A passing run would establish bearer-authenticated public read behavior on the
exact workflow revision and image digest. It would not establish that the
owner's separate `ceo` password maps to this bearer principal, that a durable
conversation identity exists, or that source-reported agent readiness is
currently fresh. Those acceptance items remain open.
