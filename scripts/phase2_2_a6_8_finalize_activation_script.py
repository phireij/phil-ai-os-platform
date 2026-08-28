#!/usr/bin/env python3
from pathlib import Path
import sys

p=Path(sys.argv[1])
t=p.read_text()
old="assert h==('L3',1,1) and s==('L1',0,0)"
new="assert tuple(h)==('L3',1,1) and tuple(s)==('L1',0,0)"
assert t.count(old)==1
t=t.replace(old,new,1)
old2="print('active_specialist_workload=0')"
new2="""active=0
for rr in c.execute(\"select distinct task_id from task_lifecycle_events where assigned_agent_id='specialist-worker-01' and stage='ASSIGNED'\"):
    last=c.execute(\"select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1\",(rr[0],)).fetchone()
    if last and last[0] not in ('COMPLETED','FAILED','CANCELLED','DENIED','EXPIRED'):
        active+=1
assert active==0
print('active_specialist_workload=0')"""
assert t.count(old2)==1
t=t.replace(old2,new2,1)
# Canary policy/readiness files are non-secret evidence. They remain root-owned on
# the host and the Control API mount is read-only, but the non-root container user
# must be able to read them.
mode_anchor="os.chmod(tmp,0o600)"
assert t.count(mode_anchor)==3, t.count(mode_anchor)
t=t.replace(mode_anchor,"os.chmod(tmp,0o644)")
# Production-only replay diagnostics. Candidate replay remains strict. These lines
# expose the exact post-accept proof state before an assertion can trigger rollback.
anchor='test "$BEFORE_REPLAY" = 1'
assert t.count(anchor)==1
t=t.replace(anchor,'echo before_replay_target_assignment_count="$BEFORE_REPLAY"\n'+anchor,1)
rep_anchor='REP="$(curl -fsS '
pos=t.rfind(rep_anchor)
assert pos>=0
t=t[:pos]+t[pos:].replace(rep_anchor,'REP="$(curl -sS ',1)
assertion="python3 -c 'import json,sys;assert json.load(sys.stdin).get(\"idempotent_replay\") is True' <<<\"$REP\""
pos=t.rfind(assertion)
assert pos>=0
replacement="python3 -c 'import json,sys;d=json.load(sys.stdin);print(\"replay_response_status=\"+str(d.get(\"status\")));print(\"replay_idempotent_replay=\"+str(d.get(\"idempotent_replay\")));assert d.get(\"idempotent_replay\") is True' <<<\"$REP\""
t=t[:pos]+t[pos:].replace(assertion,replacement,1)
after='test "$AFTER_REPLAY" = 1'
assert t.count(after)==1
t=t.replace(after,'echo after_replay_target_assignment_count="$AFTER_REPLAY"\n'+after,1)
p.write_text(t)
print('PHIL_AI_OS_PHASE_2_2_A6_8_ACTIVATION_SCRIPT_FINALIZED_OK')
