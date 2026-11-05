# Inactive owner-only synthetic inquiry and quote transport

This source increment adds an explicit `owner_quote_binding=None` option to the exact `StagingHTTPApplication`. The default module application, ordinary factory, protected-file loader, image entrypoint and serving configuration remain unchanged and inactive for these operations. There is no new listener, route activation, staff identity or live-data access.

## Trusted composition

A private Ruby factory validates an already-open exact owner-bound Core store, immutable context, synthetic source-retention policy and exact catalog-pinned mapper. It constructs the real `StaffQuoteFinalizationService`, then transfers explicit exclusive store ownership into `StagingOwnerQuoteBinding`. Core imports no private business implementation. The public binding accepts only fixed list, current detail and prepare callbacks plus cleanup, with exact issuer/owner matching and one successful application claim.

Before a successful binding construction, the caller owns its store. Before successful enabled application construction, the caller owns its binding, including cleanup after an application configuration failure. After application construction succeeds, the app owns binding cleanup. A binding cannot be shared with a second application. It is trusted startup code, never a browser-supplied router, identity, catalog, mapper or authority.

The protected startup path does not yet compose this optional binding. Do not subclass or wrap the reviewed worker/application to bypass exact-type checks. An eventual serving composition needs separately reviewed storage/key ownership, protected inputs and lifecycle integration.

## In-process HTTP contract

When explicitly bound to an enabled synthetic app, the existing verified exact-owner sign-in/session boundary admits:

- `GET /api/ruby-owner-inquiries`: bounded current summary, at most 50 entries; marked `bounded_not_complete`, not a complete history or pagination promise.
- `GET /api/ruby-owner-inquiries/<inquiry_id>`: selected normalized inquiry detail, declared/unverified synthetic contact and a source-availability indicator. Original source is read only inside the service and never returned.
- `POST /api/ruby-owner-quotes/prepare`: exact JSON keys `inquiry_id`, `expected_revision_id`, `idempotency_key`, `authored_quote`. The actual retained-source service returns an explicitly selected `prepared_not_recorded` quote review. Original source, private catalog, owner packet, raw request body, scope fingerprint and idempotency key are not response fields.

There is no HTTP record, resolve, customer send, payment, order, inventory or source-retrieval operation. The private composition can prepare with Core quote recording disabled. Existing CX source-less submissions remain unchanged; missing original source is unavailable rather than reconstructed or silently revised.

## Request and session boundary

Existing strict HTTPS WSGI, Host, Origin, Fetch Metadata, path, header and framing checks apply. Authentication and same-origin session CSRF are checked before prepare input is read. Logout stays bodyless. Prepare requires exactly `application/json` and a positive canonical decimal Content-Length at most 64 KiB. The input reader consumes only that declared length, rejects short/non-byte/oversized reads, and never drains an extra byte or subsequent request. The trusted server still owns wire framing and hard read deadlines.

JSON rejects duplicates, invalid UTF-8/surrogates, nonfinite/floating-point/unsafe numeric values, unexpected top-level fields, nesting over 16 levels and more than 8,192 values. Inquiry/revision IDs and the existing private idempotency-key bounds are checked before service invocation. Private authored-quote validation remains the existing real service's responsibility.

One nonblocking workflow slot bounds work without queueing. Body reads and private service calls do not hold the application state lock. The app checks the original session, CSRF and authentication generation after body reading and after service completion. Successful new sign-in, logout, session expiry/rotation, CSRF rotation, close or clock failure invalidates late results. Authorization is revalidated at response completion; already released bytes cannot be recalled.

All success/error responses remain `no-store`, synthetic and without execution or mutation authority. Closed errors distinguish absent source/not found (404), stale revision (409), invalid authoring (400) and unavailable service (503). Unexpected errors never expose exception text. Defense-in-depth response checks reject known private artifact keys and cap the actual serialized response, including escaping and metadata, at 128 KiB.

## Owned cleanup and limits

Close immediately revokes flows and sessions and prevents new work. If workflow work is active, the app defers binding/store cleanup until it unwinds; otherwise it detaches and closes outside the state lock. Cleanup runs once even when callbacks fail. This is best-effort Python resource ownership, not guaranteed erasure, a hard shutdown deadline or process-wide singleton proof.

No browser UI is included in this increment. Tests call the actual WSGI app in-process with the genuine auth backend and synthetic signed cryptographic fixtures, then the actual Node producer, encrypted Core custody and private preparation service. Kernel networking remains denied. The private paired harness separately pins its complete source/data closure.

Secure hosted TLS/ingress, hard deadlines, isolated store/key configuration, process supervision, a combined private/public serving package, browser acceptance and any real-customer retention policy remain separate gates. Owner-only selection does not create staff permissions or authorize quote recording.
