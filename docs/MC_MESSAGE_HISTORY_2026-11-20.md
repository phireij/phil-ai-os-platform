# Mission Control: bounded, earlier message history

This new history-only candidate is based on upstream main `7aa9c3948bf9c920705cff6004ee00d325fba905` (#832). It selectively reuses the reviewed November 9 history logic, not the V2 store work or the unrecovered November 11 UI archive. No existing encrypted store format, startup or backup code, storage migrations, schemas, write paths, or recovery scripts are changed. History reads still execute the pre-existing due-maintenance path; a filtered-out record is not proof of physical erasure.

## Behavior and compatibility

- Existing limit-only reads preserve row shape and null cursor. They intentionally select the newest bounded conversation/message window, displayed oldest to newest. Conversations select by creation time, not latest activity. Audit and notification cursor behavior does not change.
- Existing same-origin authenticated list endpoints support `?pagination=keyset-v1&limit=100` (optional limit, 1–100, default 50), with optional opaque `cursor` supplied only in this opt-in mode. Each page is chronological; prepend it. `next_cursor: null` means no earlier rows remain. Current ownership and retention are checked independently before rows can be returned.
- The authenticated `/auth/google/session` advertises `message_history_pagination: "keyset-v1"` only when conversation storage is active. The UI sends no new query to a legacy session without that capability. The cursor is bound to the owner and route, and to the selected conversation for message history. It is authenticated-encrypted with a purpose-separated key and fixed 15-minute lifetime. It is navigation, not authentication. Expiry/key rotation or older clock requires refreshing the latest page.
- Results are a live traversal, not a snapshot: new records newer than the anchor are visible on a refreshed latest read, older additions can appear in later pages, and retention/deletion can remove unseen records. Fixed time/ID sorting avoids shifting offset boundaries.
- Load earlier messages is read-only. Existing transcript rows remain in the DOM during prepend. The button stays focused/announces busy/exhaustion via a polite status, and a visible old row is used to preserve viewport position. One in-flight page at a time. Old requests, including old unauthorized responses, cannot overwrite or sign out a newer conversation/session. On send, the newest page is reloaded and earlier traversal restarts; previously paged messages supply no extra proposal-source choices, decision evidence, or execution authority. Audit and notifications remain separate and unchanged.

## Verification

Local commands from this selected-source tree, with the existing pinned identity requirements installed, are:

```sh
node --check apps/operations-hub/mission-control/mission-control.mjs
node apps/operations-hub/tests/test_mission_control_conversation_ui.mjs
node apps/operations-hub/tests/test_mission_control_posture_ui.mjs
(cd ops/mission-control-identity && python -B -m unittest -q test_google_ceo_session test_conversation_store)
```

The wire test binds only loopback and uses a temporary synthetic session and encrypted store. It asserts all 205 IDs across pages of 100, 100 and 5, equal timestamps and nonchronological insertion, anonymous denial, capability, latest default selection and unchanged V1 bytes over reads without maintenance due. It is not an actual owner/Google sign-in, production/proxy test, or production rollback drill. Validation of browser UI is a separate check; release coordination must account for the existing static frontend main-branch auto-deploy and the separate session runtime.
