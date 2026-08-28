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
p.write_text(t)
print('PHIL_AI_OS_PHASE_2_2_A6_8_ACTIVATION_SCRIPT_FINALIZED_OK')
