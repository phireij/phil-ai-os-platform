# Inactive Ruby staging application and server adapters

This source continuation adds a staging-only WSGI application, fixed synthetic
review records, a bounded Google exchange backend, and three opt-in Gunicorn
adapters. It does not enable a service. The module-level application returns 503;
the script entrypoint reports inactivity and exits. A separate default-off
mounted-file loader is supplied as source below, without host wiring or actual
credentials. There is no listener, deployment command or production import change.

## Application and authority boundary

Only explicit injected configuration can construct an enabled application. The
backend checks real token signatures with the existing pinned Core libraries and
requires exact issuer, audience, owner subject, nonce and time bounds. All tests
use local synthetic signatures and mocked HTTP responses. No live Google identity
or credential has been validated by these tests.

The application uses opaque in-memory sessions, browser-bound one-time login
flows, PKCE, bounded admission/rate budgets, bodyless same-origin CSRF logout,
and fail-closed revocation. Synthetic review responses always retain authority
none with execution and mutation disabled. The lifecycle changes preserve
logout/close revocation while authentication is in flight.

State requires a single persistent process. Restart loses all sessions and login
flows. Application time budgets are cooperative and do not impose a hard DNS or
whole-request deadline. A blocked synchronous worker cannot serve another request.

## Explicit application factory

`create_staging_application` composes the real backend and application without
using test helpers. It is disabled by default and reads no files, environment
variables or command-line inputs. Enabled construction requires explicit config,
request limits, client secret and key-cache lifetime. It does not select their
values or load credentials.

Shared pure lifecycle validators retain the existing bounds. All static app
policy and the initial monotonic clock are checked before backend allocation;
the backend checks its secret, cache lifetime and initial wall clock before
allocating its Session. Later clock failure still fails closed in the components.
The factory owns the backend until successful app construction transfers it.
Failure closes owned resources, redacts ordinary startup exceptions and preserves
control exceptions. Backend initialization also cleans a Session that has already
been returned if later setup is interrupted. Cleanup is best effort during Python
unwinding, not a guarantee under SIGKILL or a constructor that never returns.

The optional provider/owned-worker pair below calls this only after worker fork
and closes the resulting app on shutdown unwinding. Do not preload an enabled
instance in the master. One configured
worker is not by itself a single-state-process guarantee: Gunicorn's SIGTTIN
scaling and HUP reload can create additional or overlapping workers. The factory
does not implement supervisor signals, reload policy, lifecycle hooks, a server
entrypoint or protected configuration loading; the optional mounted-file wrapper
below supplies the latter source boundary. Startup diagnostics outside the
reviewed logger still require a safe runtime boundary.

## Optional single-worker controller

`StagingSingleWorkerArbiter` is a separately selected source component, not a
launcher. It accepts the exact reviewed owned worker/provider/logger, one worker and
thread, positive explicit timeouts, and default process hooks. It rejects
preloading, reload, request-count recycling, daemonization, reuse-port, dirty
pools, control sockets, cached applications and inherited runtime inputs.
`GUNICORN_PID`, `GUNICORN_FD`, `LISTEN_PID`, `LISTEN_FDS`, `LISTEN_FDNAMES`
and `NOTIFY_SOCKET` are refused when present in either the process environment
or configured environment, including empty values. Explicit `fd://` binds are
also refused before upstream setup and rechecked before start/manage/spawn.
The controller neither consumes those inputs nor closes inherited descriptors.
This prevents implicit socket adoption and an upstream readiness notification
before application loading; it does not implement readiness or general FD hygiene.
It does not choose timing, listener, UID, secret, or proxy settings.

The worker target cannot be changed from the literal integer one, including by
the actual control handler's direct property assignment. HUP, USR2, TTIN, TTOU,
WINCH, direct reload/reexec and dirty-pool requests fail with a fixed HaltServer.
In the normal upstream master loop this intentionally shuts down the service;
it does not implement a rolling restart or silently ignore configuration changes.
Repeated setup cannot preload a replacement, and stopping permanently closes
that controller to new workers.

The claim is **at most one registered HTTP worker per guarded arbiter**, not
one state owner across hosts or containers. Instance-local worker/listener
registries are used. A replacement cannot be spawned while any old worker is
registered. Unlike upstream, kill ESRCH retains that entry until the original
waitpid-based reaper observes its exit. An unresolved ECHILD remains closed to
replacement. After ESRCH, no further signal is sent to that numeric PID until
confirmed retirement, avoiding a later signal to an unrelated reused PID.
Changed cleanup hooks are suppressed and the original validated graceful timeout
is used for shutdown even when live configuration is invalid. Detecting such a
change permanently closes that controller to new workers; it does not repair
configuration and resume serving. Raw worker/logger class identities are checked
before Gunicorn's resolving properties can import or run class hooks.
This is a contract for trusted code, not an in-process sandbox
against arbitrary code that edits registries or bypasses methods.

The original heartbeat timeout, abort escalation and reaper are retained. Tests
explicitly retain their limitations: unreadable heartbeat errors are skipped;
master/scheduler/filesystem stalls can defeat a promised deadline; shutdown ends
with SIGKILL attempts and one nonblocking reap, which may leave children alive.
SIGKILL does not execute Python cleanup. The controller must not be described as
a hard request deadline or a complete process supervisor.

Before serving, a trusted launcher must select this controller and the exact
provider/owned-worker pair below. Ordinary Gunicorn CLI selects the original
Arbiter. No such launcher is included. The host
must enforce one master/replica and route to one generation, disallow overlapping
rollouts/autoscaling, and verify the **entire old service process set/cgroup is
empty** before replacement, including after master death. Master exit, readiness
removal and a successful bind are not proof. Socket activation and the inherited
runtime inputs listed above are unsupported. A launcher still needs a reviewed
descriptor policy, command/environment boundary and dirty-runtime exclusions.
Replacement loses sessions, pending flows and caches, and can involve downtime.

The new offline suite uses the actual original controller methods with inert
fork/kill/wait/start boundaries and synthetic PIDs. It exercises refusal, control
scaling, ESRCH/ECHILD, timeout escalation and shutdown; negative controls reproduce
the original TTIN and overlapping reload behavior. The original spawn parent
branch and one-event master-loop signal dispatch also run with inert process and
startup boundaries. No live master, worker, socket or server is started. Real
process lifecycle and hosted acceptance remain
separate tests, along with trusted ingress/TLS, protected mounts and credentials.

## Post-fork application ownership

`StagingPostForkApplication` is a default-off, one-use provider, deliberately not
Gunicorn's cached BaseApplication or a CLI. It holds explicit nonsecret startup
policy and a master PID, never a master-side enabled app or credential. Disabled
construction ignores ownership and generation. Enabled construction requires the
exact immutable file-ownership type, a generation, and matching configured worker
UID/GID; it does not choose those values or inspect actual mounts. Public `load`
and `wsgi` always refuse, including master-side check/print-config loading.

`StagingOwnedWorker` extends the complete canonical parser/error boundary. Its
constructor does not load the app. Its one-use initialization requires the exact
provider, a different child PID, matching worker PID and direct parent, and the
reviewed worker hooks. It delegates the original init ordering, so the protected
loader runs after Gunicorn's identity step. The actual merged file loader/factory
is called at most once. Stale providers, duplicate initialization/loading/run,
wrong-process access and startup callback drift fail closed. Parent loss during
loading prevents starting the serving loop, but does not prevent cleanup of an
already-owned app.

The provider retains ownership until cleanup. On normal return or any failure
during original init/load/run, the worker becomes terminal and detaches its WSGI
callable before one close attempt; the provider first detaches its app and input
references and marks itself closed. Failed cleanup is not retried and cannot
trigger a second load. Ordinary failures are fixed and unchained because upstream
also prints worker errors directly to stderr. Primary control exceptions are
preserved; otherwise a cleanup control exception outranks an ordinary failure.
The code does not render control-exception text. Safe handling of arbitrary
control payloads and unrelated stdout/stderr remains a runtime responsibility.

Abort/signal handlers remain inherited. Cleanup occurs after request/loop
unwinding, including normal return when the existing handler consumes an abort's
SystemExit before or after response headers. Cleanup is never run from inside
the abort signal handler. This does not guarantee cleanup under SIGKILL, process
death, interruption during a resource constructor, blocked cleanup, or secret
erasure. Parent checks do not continuously enforce parent liveness; whole-service
retirement and host supervisor guarantees remain separate.

The offline suite uses actual synthetic protected-file descriptors and the
merged factory for signed-owner review/session revocation, with mocked read-only
mount flags and clocks. Original worker initialization ordering is exercised
with identity changes, pipes, signal installation and the serving loop made inert.
Actual parser/handler abort paths use in-memory HTTP bytes. No real secret path,
worker process, listener, identity change, TLS handshake or Google connection is
used. The image still excludes these runtime modules and remains inactive.

## Optional server boundary

All three components must be reviewed and selected together by a future serving
configuration. No configuration in this change selects them:

- `StagingGunicornLogger` emits fixed events and validated status only. It never
  formats request targets, headers, exception text or tracebacks through its API.
  It does not sanitize other loggers, stdout/stderr, or external proxy logs.
- `StagingSyncWorker` emits fixed, bounded errors and security headers without
  reflecting parser input. Early parser failures without a complete request have
  no response body; known HEAD requests retain representation length without a body. Writes are a single
  nonblocking attempt, not a proven wall-clock delivery deadline.
- `StagingCanonicalWorker` requires the reviewed Python HTTP/1 parser policy,
  underscore-header refusal without forwarding exceptions, and unmodified
  request hooks/SCRIPT_NAME. It rejects noncanonical raw paths before WSGI
  unquoting while preserving query encoding. It never repairs or rewrites input.

A pre-WSGI rejection intentionally does not consume the pending application flow
or clear its cookie. Its original short TTL remains; a canonical retry can still
complete once. Incorrect parser configuration fails closed before parsing/TLS.

The adapter guards recognize Gunicorn 26.2.2, but a version string is not a
runtime provenance check. The artifact actually supplied to any future runtime
must separately match the reviewed official commit. This change does not install
Gunicorn or alter production requirements.

## Offline source tests

The pinned source is official Gunicorn 26.2.2, commit
`8d98faa9a13d3399a7bea81b5169e5cd72225395`, Git tree
`d7108b89eb73974543289b5178197c9998110286`:
https://github.com/benoitc/gunicorn/tree/8d98faa9a13d3399a7bea81b5169e5cd72225395

The new CI job checks out that exact source with persisted credentials disabled.
It uses the existing Core requirements in a test-only environment and never
installs/builds Gunicorn. The offline helper validates the full file set and all
793 SHA-256 hashes before placing the source tree on the import path. `.git`
metadata is excluded; added files, symlinks, missing or changed files fail closed.
The checked-in manifest contains public source hashes, not upstream source code.

Given an already verified local checkout and the existing approved dependencies:

    export RUBY_STAGING_TEST_GUNICORN_SOURCE=/absolute/path/to/pinned/gunicorn
    python3 -I -B ops/mission-control-identity/test_ruby_staging_gunicorn_logging.py
    python3 -I -B ops/mission-control-identity/test_ruby_staging_gunicorn_errors.py
    python3 -I -B ops/mission-control-identity/test_ruby_staging_gunicorn_boundary.py
    python3 -I -B ops/mission-control-identity/test_ruby_staging_gunicorn_integrated.py
    python3 -I -B ops/mission-control-identity/test_ruby_staging_gunicorn_arbiter.py
    python3 -I -B ops/mission-control-identity/test_ruby_staging_gunicorn_application.py

Each command is a separate process. Their import-time audit guard rejects socket,
DNS and process-launch actions. urllib3's import-time IPv6 capability probe is
expected to be rejected before a socket is created. There are no test-phase
network attempts. The guard is not an operating-system sandbox.

The tests exercise the actual upstream parser/handler with in-memory byte
transport. TLS metadata is explicitly mocked; no TLS handshake occurs. Layer
tests retain negative-control observations of unmodified lower layers. Only the
combined adapter suite represents the proposed composed boundary. Do not use
unrestricted test discovery in place of the explicit suites or mistake an
expected lower-layer defect for an accepted composed configuration.

## Image source and CI effects

`Dockerfile.ruby-staging-review` is an existing reviewed inactive source recipe,
pinned to the Core Linux/amd64 Python/Alpine lineage. It copies seven application
modules plus requirements, runs as a non-root user and exits inactive. It omits
Gunicorn and the adapters. It is not a runnable staging-server image. This
image is built temporarily by the separate packaging CI job and is not published
by that job. The requirements contain
version pins, not a complete hash-locked wheel supply chain.

The CEO-session CI adds the three application/backend/runtime suites, a separate
four-suite handler job, and both recipe paths to its PR/main path filters. The
existing production image smoke steps remain unchanged. A future PR can trigger
those existing CI builds. A future merge touching the identity directory also
triggers the two existing production image publishers with commit-SHA tags;
neither image includes the staging adapters. There is no staging publisher and
no automatic deployment in these workflows. External watchers are not verified.

The factory increment adds its offline ownership/initialization suite and a
factory-created signed-session case through the composed real HTTP handler. Its
source is included in the inactive recipe, but the entrypoint still reports
inactivity and exits. No serving path is selected by that inclusion.

The packaging job checks out the exact event SHA and builds from ten allowlisted
files: the recipe, its ignore file, requirements and seven application modules.
It records source hashes and the runner-local image ID, then inspects metadata.
It does not execute the staging app, push an image, upload an artifact or deploy.
The recipe remains pinned to the same Linux/amd64 base; its serving omissions and
host-architecture acceptance remain unchanged.

## Proposed protected mounted-file boundary

`ruby_staging_protected_files.create_staging_application_from_files` is a
startup-only, default-off wrapper around the real factory. Importing it performs
no configuration or credential loading. Disabled calls do not inspect inputs,
read identity, or open files. No environment/CLI loader, actual host identity,
secret installation, permission change or serving entrypoint is provided.

The fixed paths are `/run/secrets/ruby-staging/config.json` and
`/run/secrets/ruby-staging/secret.json`. A trusted final-worker launcher must pass
all four `StagingFileOwnership` IDs and the expected generation explicitly:
`reader_uid`, `reader_gid`, `directory_uid`, and `directory_gid` have no defaults.
The reader UID must be nonzero. Effective UID/GID must match reader expectations;
file ownership must match the same IDs. This does not prove namespace mapping,
capabilities, ACL/MAC policy or trust in the mount provider.

Both files must have exact mode 0400 and one hard link. Every opened directory
must have the supplied directory UID/GID. The leaf directory must be exactly
0555; `/`, `/run` and `/run/secrets` must be exactly 0755 or 0555, with no special
permission bits. The leaf and both files must report ST_RDONLY through fstatvfs.
A different provider layout needs a reviewed contract change, not permissive
fallbacks. No code sets these modes, IDs or mount flags.

The config JSON envelope has exactly `version`, `generation`, `config`, `limits`
and `max_cache_seconds`. Version is integer 1. Generation is a 32-character
lowercase hexadecimal string equal to the trusted launcher's expected generation.
`config` has exactly the seven StagingHTTPConfig fields; `limits` has exactly the
four StagingRequestLimits fields. Their existing types, identity exclusions and
policy bounds still apply. The secret JSON envelope has exactly `version`,
`generation`, and `client_secret`, with the same version/generation requirements
and existing secret validation. No actual identities or deployment policy values
are selected by this schema. Duplicate/unknown keys, nonfinite values, malformed
UTF-8/JSON and wrong types fail closed. Config bytes are capped at 16384 and secret
envelope bytes at 8192, before parsing.

The loader walks individual components using retained O_DIRECTORY/O_NOFOLLOW/
O_CLOEXEC descriptors. It opens final files with O_NOFOLLOW/O_NONBLOCK/O_CLOEXEC,
validates both opened objects before reading either, bounds reads, requires EOF,
and rechecks file identity/metadata plus directory and mount policy. All owned
FDs close before factory allocation. Ordinary errors are fixed and unchained;
control exceptions survive cleanup. Every close is attempted, but an uncertain
close is not retried because its numeric FD could have been reused. No secret or
file content is logged. Dropping Python references is not secure zeroization.

These checks do not establish an atomic two-file transaction. Matching expected
generations catch accidental mixing but cannot prevent a trusted host writer
from reusing a generation or changing data through another writable mount.
ST_RDONLY describes this process's view only. O_NONBLOCK avoids FIFO-open hangs;
it does not bound regular-file I/O or make opening an unexpected device harmless.
Protected ancestors and a trusted mount provider are prerequisites, with startup
I/O deadlines and filesystem behavior still subject to runtime acceptance.

Required lifecycle: publish a complete immutable generation before startup,
mount it read-only, and prohibit writes, replacements, remounts or rotation while
loading or serving. Construct only in the final worker after fork. Close and
terminate the old app before activating a new generation; do not hot-reload or
overlap independent session-state processes. These host guarantees are not
activated or verified by the loader.

The synthetic loader suite uses actual temporary file descriptors and kernel
symlink/FIFO behavior while redirecting the root open to an owned test tree.
Read-only mount flags are simulated; it never opens the real secret paths or
changes a mount. A signed synthetic login/read/logout exercises the loader with
the real factory. No test establishes real host permissions or secret delivery.

## Remaining hosted acceptance gates

- Effective ingress/proxy/TLS configuration and exact request/header forwarding.
  A proxy can normalize raw bytes before this worker sees them. Forwarded scheme
  headers and ordinary Connection headers currently fail closed in the app;
  they require an explicit trusted transport contract, not a broad allowlist.
- Verified host wiring for the supplied default-off protected-file loader:
  namespace identity, mount/provider trust, immutable generation and rotation
  lifecycle, plus actual staging Google client, exact owner binding, callback
  origin and secret delivery. No real credentials or host setup are supplied.
- An approved single-worker supervisor with bounded termination, reaping and
  replacement, plus actual socket/TLS/read/write/request limits. Prior isolated
  signal tests do not establish end-to-end serving deadlines or host behavior.
- Serving-runtime artifact provenance, host architecture, a serving-image build,
  actual Google/browser sign-in and hosted security/availability acceptance.

No runnable server entrypoint is provided until those contracts are resolved.
