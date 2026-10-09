# Mission Control control-plane gateway

`control-plane-gateway.py` is the authenticated backend boundary for the Mission Control MVP. It is separate from the public static preview and is not deployed by the current read-only image.

## Routes

- `GET /api/healthz` — public health only; returns `authority_effect: none`.
- `GET /api/snapshot` — CEO-authenticated Control API snapshot.
- `GET /api/approvals` — CEO-authenticated recent approvals.
- `GET /api/executions` — CEO-authenticated recent executions.
- `POST /api/decision-requests` — CEO-authenticated request routed to the governed approval endpoint.
- `POST /api/tasks/{task_id}/assign` — disabled unless `MISSION_CONTROL_DELEGATION_ENABLED=true` is explicitly set.

CEO authentication uses a bearer token read from `MISSION_CONTROL_CEO_TOKEN_FILE`. The gateway never logs the token. Control API credentials remain separate and are read by the existing adapter.

The gateway performs no provider calls, customer replies, payment operations, inventory changes, publication, or task execution.
