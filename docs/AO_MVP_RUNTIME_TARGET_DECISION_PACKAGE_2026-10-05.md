# AO-MVP Runtime Target Decision Package

Status: RECOMMENDATION ONLY — NO DEPLOYMENT

## Recommended target
Use the existing Hostinger VPS class already aligned with the program baseline: Ubuntu 24.04, 2 vCPU, 8 GB RAM, 100 GB storage, with Docker/Compose for the bounded orchestrator.

## Why this is the preferred first target
- It matches the existing Phil AI OS VPS baseline and avoids introducing another provider.
- Hostinger supports an Ubuntu 24.04 Docker VPS template and Docker Compose.
- Docker Manager supports host-mounted persistent volumes and explicit restart policies, which directly map to the AO activation evidence requirements.
- 2 vCPU / 8 GB / 100 GB corresponds to Hostinger's KVM 2 class and is ample for the current lightweight Python orchestration contracts; this is a sizing assumption to validate empirically, not a production-capacity guarantee.

## Initial deployment shape
- one container only;
- no public application port required initially;
- host-mounted state directory for durable queue/ledger/lifecycle evidence;
- restart policy: unless-stopped;
- no production credentials;
- network egress disabled by default where practical, otherwise narrowly allowlisted;
- read-only GitHub/project evidence only after separately provisioning least-privilege credentials;
- Mission Control remains read-only;
- activation scope remains bounded A1.

## Alternatives
1. Existing Hostinger VPS — preferred: lowest operational change and best match to current baseline.
2. New dedicated Hostinger VPS — stronger isolation but adds cost/management.
3. Another cloud/container service — defer unless Hostinger fails persistence, restart, observability, or isolation acceptance.

## Decision required before activation
CEO must explicitly approve the runtime target and hosted A1 activation scope. Approval of this recommendation is not inferred from earlier A1 repository authorization.

No server changes, purchases, deployments, DNS changes, or credential changes are performed by this decision package.
