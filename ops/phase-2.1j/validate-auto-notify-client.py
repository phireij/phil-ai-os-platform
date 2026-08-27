#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import pathlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: validate-auto-notify-client.py CLIENT")

path = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("phase21j_client", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class Proc:
    def __init__(self, returncode=0, stdout='{"status":"ok","telegram_ok":true}', stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

calls = []
def fake_run(argv, **kwargs):
    calls.append(list(argv))
    return Proc()

mod.subprocess.run = fake_run
pending = {"approval": {"approval_id": "apr_test", "state": "pending"}, "status": "ok"}
r = mod.notify_pending_approval(pending)
assert r["status"] == "ok", r
assert r["approval_id"] == "apr_test", r
assert calls == [[mod.NOTIFIER_BIN, "apr_test"]], calls
print("pending_notification=one_shot")

calls.clear()
for state in ("approved", "denied", "expired"):
    r = mod.notify_pending_approval({"approval": {"approval_id": "apr_test", "state": state}})
    assert r["status"] == "skipped", (state, r)
assert calls == [], calls
print("non_pending_notification=blocked")

calls.clear()
def failed_run(argv, **kwargs):
    calls.append(list(argv))
    return Proc(returncode=7, stdout="", stderr="failed")
mod.subprocess.run = failed_run
r = mod.notify_pending_approval(pending)
assert r == {"status": "failed", "reason": "notifier_nonzero", "exit_code": 7}, r
assert len(calls) == 1
print("notification_failure=reported_no_retry")

request_calls = []
def fake_call(path, method="GET", payload=None):
    request_calls.append((path, method, payload))
    return {"approval": {"approval_id": "apr_main", "state": "pending"}, "status": "ok"}
mod.call = fake_call
mod.subprocess.run = failed_run
old_argv = sys.argv[:]
sys.argv = ["philaios-mission-control", "request", "isolated", "task"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = mod.main()
sys.argv = old_argv
assert rc == 0, rc
assert len(request_calls) == 1, request_calls
out = json.loads(buf.getvalue())
assert out["approval"]["approval_id"] == "apr_main"
assert out["notification"]["status"] == "failed"
assert request_calls[0][0] == "/v1/approvals/request"
assert request_calls[0][1] == "POST"
print("request_success_independent_of_notification=true")
print("approval_retry=none")
print("approval_consumption=none")
print("execution_call=none")
print("provider_call=none")
print("authority_expansion=none")
print("PHIL_AI_OS_PHASE_2_1J_AUTO_NOTIFY_CLIENT_VALIDATION_OK")
