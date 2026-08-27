#!/usr/bin/env python3
import pathlib,sys
if len(sys.argv)!=3: raise SystemExit('usage: build-read-model-v21i.py BASE_2_1H OUTPUT')
s=pathlib.Path(sys.argv[1]).read_text()
def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}_match_count={n}')
    s=s.replace(old,new,1)
rep('SCHEMA_VERSION = "2.1h.v1"','SCHEMA_VERSION = "2.1i.v1"','schema')
helper=r'''def coordinator_metadata(control: str):
    code = r'''import sqlite3,json
c=sqlite3.connect("/app/state/control-plane.db")
c.row_factory=sqlite3.Row
tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
registry=[dict(r) for r in c.execute("select agent_id,display_name,role,authority_ceiling,enabled,assignable,created_at,source_component from agent_registry order by agent_id")] if "agent_registry" in tables else []
plans=[dict(r) for r in c.execute("select plan_ref,task_id,created_at,created_by,plan_kind,status,supersedes_plan_ref from task_plans order by created_at desc,plan_ref desc limit 100")] if "task_plans" in tables else []
print(json.dumps({"registry":registry,"plans":plans,"registry_present":"agent_registry" in tables,"plans_present":"task_plans" in tables},default=str))'''
    out,_=run(["docker","exec",control,"python3","-c",code])
    data=json.loads(out)
    registry=data.get("registry",[]); plans=data.get("plans",[])
    summary={
        "coordinator_owner":"control-api",
        "registry_state":"active" if data.get("registry_present") else "absent",
        "plan_store_state":"active" if data.get("plans_present") else "absent",
        "registered_agent_count":len(registry),
        "plan_count_observed":len(plans),
        "assignment_semantics":"explicit_authenticated_operation_only",
        "planning_semantics":"server_generated_plan_ref_only",
        "mission_control_mutation":"none",
    }
    return registry,plans,summary

'''
rep('\ndef main():','\n'+helper+'def main():','coordinator_helper')
rep('    durable_links, durable_summary, lifecycle_events = durable_approval_execution_links(control)',
    '    durable_links, durable_summary, lifecycle_events = durable_approval_execution_links(control)\n    coordinator_agents, coordinator_plans, coordinator_summary = coordinator_metadata(control)',
    'coordinator_call')
rep('        "durable_correlation_summary": durable_summary,',
    '        "durable_correlation_summary": durable_summary,\n        "coordinator": {"summary":coordinator_summary,"agent_registry":coordinator_agents,"plans":coordinator_plans},',
    'model_coordinator')
needle='            "agent_assignment_provenance": "explicit_ledger_event_only" if durable_summary.get("lifecycle_ledger") == "append_only" else "authoritative_source_unavailable",'
rep(needle,needle+'\n            "coordinator_registry_state": coordinator_summary.get("registry_state"),\n            "coordinator_plan_store_state": coordinator_summary.get("plan_store_state"),','quality_coordinator')
pathlib.Path(sys.argv[2]).write_text(s)
print('read_model_schema=2.1i.v1')
print('coordinator_owner=control-api')
print('registry_source=agent_registry_safe_columns')
print('plan_source=task_plans_safe_metadata_only')
print('mission_control_mutation=none')
print('secret_column_expansion=none')
print('PHIL_AI_OS_PHASE_2_1I_READ_MODEL_BUILD_OK')
