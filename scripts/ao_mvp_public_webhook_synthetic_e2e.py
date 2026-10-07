#!/usr/bin/env python3
"""Network-free synthetic end-to-end webhook canary harness."""
import json
from ao_mvp_public_webhook_contract import evaluate_request, synthetic_headers
from ao_mvp_public_webhook_rate_limit import SlidingWindowLimiter
from ao_mvp_public_webhook_log_redaction import sanitize_webhook_log

def run_synthetic_canary():
 secret=b"synthetic-e2e-secret"
 now=1791359000
 body=json.dumps({"event_id":"e2e-canary-1","kind":"synthetic_canary"},separators=(",",":")).encode()
 headers=synthetic_headers(secret,now,"e2e-nonce-1",body)
 limiter=SlidingWindowLimiter(limit=2,window_seconds=60)
 limiter.admit("synthetic-e2e",now)
 accepted=evaluate_request(secret=secret,headers=headers,body=body,now=now)
 log=sanitize_webhook_log({**accepted,"request_id":"synthetic-r1","decision":"accepted","status_code":202,"body":body.decode(),"headers":headers})
 assert accepted["authority_effect"]=="none"
 assert "body" not in log and "headers" not in log
 return {"synthetic_e2e_green":True,"network_used":False,"production_mutation":False,"authority_effect":"none","log":log}

if __name__=="__main__":
 print(json.dumps(run_synthetic_canary(),sort_keys=True))
