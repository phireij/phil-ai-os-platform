# Staging durable admission core

**Scope: a local admission bookkeeping library only. Not a Docker controller, runtime retirement authority, deployment package or end-to-end supervisor.** No Docker/API/socket operation, host access, network call, command execution, credential/certificate handling, service installation or permission change is implemented. This module is not wired into any service, image entrypoint or runtime adapter.

This bounded Python standard-library component uses actual `flock`, local files, atomic replacement and fsync. It does not model a lock in memory or claim that a bookkeeping token fences Docker.

## Files and validation

- `staging_durable_admission.py`: importable library, with no CLI or execution entrypoint.
- `test_staging_durable_admission.py`: real local process and temporary-file tests plus explicit syscall fault injection.

Run from the repository root on Linux:

    python3 -I -B ops/mission-control-identity/test_staging_durable_admission.py

The existing `verify-staging-server-source` CI job runs this command. This test uses only the Python standard library; no package installation or runtime connection is required for it. Tests create only temporary local stores/processes. Their five-second process-join/poll bounds are test-harness safeguards, not production lease/watchdog/deadline defaults.

## API and invariants

Callers supply an explicit absolute path to a pre-created, empty, owned directory. There are no production paths, endpoints, timeout numbers or policy defaults.

1. `Session.initialize(path, endpoint_ref=..., daemon_identity=..., reconciliation_ref=...)` is **explicit fresh bootstrap**, not recovery. It refuses any directory entry, including a leftover lock or temporary record. The operator must already have reconciled that no owned generation exists and established exclusive storage/start authority. The audit reference is not evidence or an automated verification of that fact. Bootstrap creates the lock once, syncs it and its directory, then durably writes CLOSED. A partial bootstrap is not automatically retried or repaired.
2. `Session.open(path, endpoint_ref=..., daemon_identity=...)` requires both existing files. It takes a nonblocking exclusive OS lock on the stable, never-replaced `owner.lock` inode. Missing/corrupt/inconsistent journal or lock fails closed. The directory/lock device and inode and lock contents are checked against the journal. Changed daemon binding is recorded as UNKNOWN while retaining the old binding, then denied. Any recovered unfinished generation becomes durable UNKNOWN **before the session is returned**, even after an orderly previous close. Recovery does not reissue a permit.
3. `reserve_generation(revision=..., generation=..., spec_digest=..., policy_digest=..., watchdog_ref=...)` durably records one CREATE_INTENT. It returns a detached bookkeeping snapshot. No create operation is performed and no API authority is conferred.
4. `bind_created(revision=..., full_id=...)` binds exactly one full lowercase 64-hex ID. It records the adapter's candidate binding, not proof of the object's configuration. `register_observer(revision=..., observer_ref=...)` records one prospective registration reference. Both are irreversible in this core.
5. `consume_start(revision=...)` durably sets START_INTENT, the monotonic `start_consumed` flag, random attempt ID and start revision before returning a frozen `StartPermit`. The record includes immutable generation, spec/policy digests, daemon endpoint/identity, full ID, observer and watchdog reference. There is no retry/refund/reissue, even if the holder never sends a request. The descriptor states required external checks. It is not itself runtime evidence or a daemon-enforced capability.
6. `observe(revision=..., observation=...)` is a strict, bounded, untrusted-fact reducer. It binds every event to journal/generation/spec/policy/daemon/full ID/start attempt/start revision/observer. An exact duplicate of the last event is idempotent. Gaps, reordering, mismatches, request errors/loss and observer loss persist UNKNOWN. START_RESPONSE_OK or RUNNING_REPORTED records STARTING bookkeeping only; neither authorizes exposure. EXIT_REPORTED records RETIRING, never RETIRED or a free slot. A late start acknowledgement cannot reopen RETIRING, SEALED or UNKNOWN. Execution reported after a terminal boundary persists UNKNOWN while retaining terminal flags.
7. `seal(revision=...)` creates a permanent **local** SEALED tombstone. It does not mean the runtime has stopped; it does not free the slot. UNKNOWN remains UNKNOWN even when locally sealed. No `retire`, `release`, `reset`, reconcile-to-open or second-generation API exists. This deliberately sacrifices availability until a separately reviewed trusted adapter can supply actual runtime retirement/request-settlement semantics.
8. `snapshot()` is detached from internal state; descriptors are frozen data. Every mutating call requires the exact integer revision (booleans are rejected). The revision cannot wrap. All public session operations, including snapshot and close, reject reentrancy, including signal-handler reentrancy. Internal helpers do not re-enter public operations.

A session belongs to its creator PID and **thread object**, not a recyclable numeric thread ID. Other threads may neither use nor close it. A fork child may close only its inherited descriptors; it never explicitly unlocks the shared flock. A child holding an inherited descriptor can conservatively prolong the lock after its parent dies. This is a liveness limitation, not a takeover lease. There is no implicit destructor, timeout or forced lock release. An abandoned owning thread strands its session until process shutdown; do not build a thread-transfer workflow around it.

`close()` detaches its descriptor ownership before attempting each close once. An ambiguous close failure is not retried against recycled descriptor numbers. Such a failure can retain a descriptor/lock until process exit; it never creates a fresh admission claim.

## Storage protocol and failure behavior

Every mutation checks the live journal against the session's prior record, increments revision, writes a bounded canonical JSON envelope to a new exclusive temporary regular file, fsyncs that file, atomically replaces `journal.json`, fsyncs the parent directory, and checks the resulting record again. Permit return has an additional identity/read check. There is no pickle, YAML object construction, arbitrary object deserialization, dynamic import, command or configured callback. A fixed no-op checkpoint method exists solely for test monkeypatching.

The JSON parser rejects duplicate keys, non-finite constants, unknown fields, wrong types, oversized records, trailing bytes, invalid/inconsistent state and checksum changes. Reads loop to EOF and require the file's stated size to match. Writes handle partial writes; zero progress fails. SHA-256 detects accidental damage, **not a malicious rewrite**.

The directory is opened component by component with no-follow directory descriptors; child files use directory-relative no-follow opens. Files must be regular, single-link, owned by this effective UID and not group/other writable. The final directory must be owned and not group/other writable. Created files request 0600; existing group/world-readable or executable files are not categorically rejected. The contract protects controlled writers, not confidentiality or a strict pre-existing 0600 mode. No chmod/chown is performed. FIFO, symlink, hardlink and replaced lock/directory cases are refused. Interrupted temporary files remain bounded-size forensic leftovers and are never adopted or cleaned automatically; repeated failed invocations can accumulate files, so repeated restart loops are not authorized resource management.

A storage error poisons a live session and returns no permit. If the durable outcome is uncertain, the implementation does **not** pretend another write can always persist UNKNOWN: it denies further use and requires reopen. Reopen either safely validates and durably records UNKNOWN or refuses access. No returned permit relies on a failed fsync. Public storage errors are stable and redacted; raw OS path/error chains are suppressed.

The current-process record comparison detects live rollback/replacement to a different record. **A complete valid old-store rollback across process restarts, coordinated malicious edits, or deletion of the entire store cannot be distinguished from a fresh previously reconciled store using only that store.** There is no external monotonic counter, authenticated log, backup authority or anti-root protection. Operators must never restore stale state or initialize another directory to bypass unresolved work.

## Mandatory trust assumptions and absolute limits

- Linux/POSIX behavior with working `O_NOFOLLOW`, directory descriptors, `flock`, same-directory atomic replace, file fsync and directory fsync. No NFS/distributed filesystem/lease semantics are claimed. Unsupported calls or storage fail closed.
- Honest kernel/filesystem/storage stack reports durability correctly. Local tests exercise process-crash behavior on the filesystem where they run, **not** crash-consistent power-loss behavior of an unverified target filesystem/controller/cache. Hardware corruption, dishonest fsync, kernel failure or lost entire storage exceed the guarantee.
- One protected local storage authority. Path ancestors, namespace/mount topology, this UID's other writers and privileged operators are trusted. Pre/post identity checks reduce accidental replacement risk; they do not defeat a malicious concurrent filesystem writer, privileged mount swap or host root. No implementation can promise progress under indefinite I/O/kernel stalls.
- One actual outside owner must control every authorized runtime start/recreate/restart path. The future adapter must verify daemon identity, immutable config, no previous execution, restart-off, private PID topology, prospectively acknowledged observer and independent pre-armed watchdog. References and JSON fields do not establish these properties.
- Every returned descriptor can be copied by its recipient. The local core issues at most one descriptor; it cannot stop a malicious/buggy holder from submitting it twice to Docker, and Docker does not enforce its revision/token. This remains a critical unimplemented integration boundary.
- No real API responses, namespaces, tasks, init reaping, removal fencing, watchdog actuation, stopped PID1 behavior, TLS/application execution, exposure closure or end-to-end deadlines are verified here. No absolute hard-realtime, power-loss or malicious-host-root claim is made.

## Tests actually performed

The suite includes 33 test methods with subcases:

- Real independently executing contenders; same-process repeated open; stopped owner retaining lock; SIGKILL owner release followed by persistent UNKNOWN.
- Fork-child denial and close-only safety; wrong-thread use/close; recycled numeric thread identifier; actual SIGUSR1 handler reentrancy; nested calls at all 11 relevant commit/return checkpoints.
- 82 real child-process crashes across reserve, bind, observer registration, start, exit reduction, seal, UNKNOWN reduction and UNKNOWN recovery, including immediately before and after permit return. A prior permit may already have been returned for later-state tests; recovery never returns another.
- 13 initialization crash boundaries. A complete durable initial CLOSED may remain usable; an incomplete store never silently reinitializes.
- ENOSPC writes, zero/partial writes, file/directory fsync and rename errors, postcommit errors, recovery fsync failure and ambiguous close. These are explicitly injected syscall faults, not real device failures.
- Missing/truncated/oversized/deep/malformed/duplicate-key/checksum-invalid/type-invalid journals; short-read and valid-prefix/trailing-garbage faults; inode/path/link replacement; schema consistency; immutable snapshots, bindings and descriptors.
- Every observation binding dimension, duplicate/reordered events, errors/observer loss, instant exit before start acknowledgement, late acknowledgements, contradiction after terminal boundary, persistent UNKNOWN and refusal of arbitrary retirement assertions.

Passing these tests does not establish deployment readiness or any runtime-retirement guarantee.
