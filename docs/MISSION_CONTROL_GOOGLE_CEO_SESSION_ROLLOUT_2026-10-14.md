# Mission Control CEO session rollout gate

**Status:** guarded deployment workflow and host script prepared for review; no deployment authorized or attempted. The inactive CEO session image was published from exact main `d940f87f5e4cde7aad16708e90351287477c435e` as `sha256:ddf622ab5cfabedba3dd5427fb6ce8012e207804e12340d608cf2685a4eed336` by [run 38513360441](https://github.com/phireij/phil-ai-os-platform/actions/runs/38513360441). The live identity probe remains on its previously activated digest. A merge of this rollout change would publish a new image from its own exact main revision; use that new digest for any later activation request.

## Replacement boundary

The CEO session service must replace the probe on the same `/auth/google` route. Do not allow both routers to answer the callback. Keep the existing read-only gateway, Mission Control UI, Control API, Hermes, and all other containers untouched. The session service uses only the Docker bridge network and port 8093 behind the current HTTPS Traefik entrypoint. It has no conversation route, storage, provider call, or task authority.

The rollout must pin both exact current `main` and the session image digest. Refuse a missing, stopped, or unexpected probe; an already present session or rollback container; another Traefik router claiming this host and `/auth`; or a changed running-workload inventory outside the two identity containers. Stage the existing protected OAuth client secret and CEO `issuer|subject` binding into a new per-run Docker volume using owner-only files for UID 10003. Never print, persist in Git, or expose either value through a Docker label or command argument.

Start a no-network, unrouted preflight container with the final environment and read-only secret mount. Check that the process remains running and that the secret files have exact owner and mode. Then rename and stop the current probe as a rollback container, start the session with its final HTTPS router, and make bounded public checks: health 200 with `conversation_authority=none`, unauthenticated session GET 401, mutation methods 405, and a GET of `/auth/google/start` redirecting only to Google's authorization endpoint. The public checks must not follow the redirect or exchange a code.

On any failure after stopping the probe, remove the candidate session and restart the original probe under its original name. Keep its protected volume intact. On success, keep the stopped probe rollback container and its volume until a later reviewed cleanup; record only non-secret revision, digest, route, and workload-isolation evidence. A later controlled CEO browser sign-in is needed to verify the authorized session end to end. No CI run can substitute for that owner step without copying credentials.

## Release sequence

1. Review a concrete manual deployment workflow and host script implementing the boundary above. Run its offline/policy checks; merge only with explicit owner approval.
2. Recheck exact main, image digest, secret names, and current probe image. Request separate activation approval identifying those values and the rollback command.
3. Dispatch once. Inspect only pass/fail and image identity output. If any check fails, prove the old probe returned and other workloads stayed unchanged before retrying.
4. Ask the CEO to sign in through the new route and inspect `/auth/google/session` in the browser. Never send session cookies, CSRF tokens, codes, or the protected subject through chat.

The session rollout advances MC-006 only. Durable conversations, retention, provider limits, proposals, and execution remain separately gated.
