# Ruby quote staff declarations: source-only body extension

## Scope and non-authority

This extension retains explicit operator declarations in the existing encrypted
ConversationStore quote body. It introduces no route, actor authentication, staff
role, production policy, customer acceptance, order, payment eligibility,
inventory, dispatch, sending, publication, or provider action. Existing opt-ins
and owner/project/source policy checks remain required and synthetic-only.

An operator reference is a declared opaque reference, not a verified identity.
A source-review fingerprint is retained consistency metadata, not proof that
Core checked the source review, an operator's role, or a physical fulfillment
plan. The calling workflow must bind its review to the retained inquiry before
submitting the quote. Core still binds the quote to its exact inquiry revision.

All existing `NO_QUOTE_AUTHORITY` outputs are unchanged. In particular,
`date_verified`, `packing_verified`, `shipping_verified`, `customer_accepted`,
`payment_request_authorized`, `payment_execution_authorized`, and
`ready_for_payment_request_review` remain false even when every declaration is
true, after readback and after a synthetic customer response.

## Exact request and receipt versions

Legacy request bodies remain `ruby.finalized-quote-record.v1` with their existing
closed field set. They cannot contain `staff_declaration`.

The new body version is `ruby.finalized-quote-record.v2`, exported as
`STAFF_SCHEMA`. Its closed top-level field set is exactly:

- `schema_version`
- `expected_revision_id`
- `source_quote_ref`
- `currency`
- `items`
- `shipping_yen`
- `total_yen`
- `fulfillment`
- `staff_declaration`

All eight legacy fields retain their existing validators, arithmetic checks and
bounds. The existing JSON body limit, duplicate-key rejection, integer limits,
item bounds and fulfillment contract are unchanged.

`staff_declaration` is a required closed object containing exactly:

| Field | Contract |
| --- | --- |
| `operator_ref` | Existing opaque reference validator: 1–120 ASCII characters from `[A-Za-z0-9_.:-]`. |
| `source_review_fingerprint` | Exact lowercase `sha256:` followed by 64 lowercase hexadecimal characters. |
| `date_confirmed` | Literal JSON `true`: the operator explicitly declared the quote's date/window reviewed and confirmed. |
| `packing_confirmed` | Literal JSON `true`: the operator explicitly declared the quote's packing reference and description reviewed and confirmed. |
| `shipping_confirmed` | Literal JSON `true`: the operator explicitly declared the quote's shipping method and amount reviewed and confirmed, including zero-fee pickup. |
| `packing_description` | Required nonblank text, at most 200 Unicode characters using the existing item-description text bound; no control characters, leading/trailing whitespace, or silent normalization. |
| `verification` | Exact string `unverified_operator_declaration`. |

Missing declarations, `false`, string booleans and numeric booleans are rejected.
Declarations are not inferred from a draft or defaulted on the caller's behalf.
Packing text preserves the operator's supplied box/packing details; it does not
validate carton dimensions, physical fit, packed weight or carrier feasibility.
No new shipping, packing, date, pricing or role policy is invented here.

Both request versions deliberately retain the original response receipt schema,
`ruby.finalized-quote-record.v1`, exported as `SCHEMA`. This is the existing
receipt envelope, not a claim that the request was V1. Its unchanged
`request_fingerprint` binds the entire exact request, including its body version
and declarations. The retained quote returned by `get_ruby_finalized_quote`
contains the actual request body's version. Do not infer request-body version
from receipt version.

## Custody and compatibility

No table, ledger, receipt format, audit operation, or authority field changes.
The declarations live only within the existing canonical `request_json` and are
included in the existing `request_hash` retained across event, receipt and audit.
The existing receipt/audit tables do not gain operator or packing-text content.

All existing recovery and conflict behavior remains in force:

- Replaying the same request/key returns the immutable original receipt.
- Changing operator, review fingerprint, packing text, or body version under the
  same key conflicts. Invalid/false declarations are rejected before append.
- A new key cannot append against a stale inquiry revision. An already recorded
  historical request can still recover its original receipt after revision.
- Missing fragments yield unknown without reconstruction or replacement. Any
  retained fragment continues reserving the key.
- Retained-body/hash mismatch rejects recovery; returned object mutation does
  not mutate retained evidence.
- Existing quote selection, consent projection and bound synthetic responses
  can consume either body version, without granting customer/payment authority.

## Focused local checks

`test_ruby_staff_quote_declarations.py` contains 13 direct tests against actual
ConversationStore temporary encrypted storage, including V2 readback, ciphertext
checks, close/reopen recovery, V1 compatibility, strict declaration validation,
existing bounds, duplicate-key rejection, immutable conflicts, stale revisions,
retained-body tampering, partial evidence, isolation, and V2 selection/consent/
bound synthetic response recovery. Socket entry points are blocked in each new
test. All data, owner contexts and verifier results are synthetic.

The existing `test_ruby_finalized_quote.py` imports the new test class, so its
standard unittest invocation also collects all 13 cases without a CI workflow
change. The standalone declaration module avoids circular quote/custody fixture
imports.

The companion local evidence runner selects those 13 tests and 61 inspected
legacy quote/custody/consent tests. It additionally blocks socket audit events and
child-process entry points, and excludes four known subprocess test methods and
all inherited inquiry tests. It uses only already-installed Python packages.
The checked restart is a new store instance loading encrypted temporary files,
not a fresh operating-system process. This is focused regression evidence, not
the full repository suite, a production execution test or deployment evidence.
