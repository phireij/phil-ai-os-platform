#!/usr/bin/env python3
"""Add a bounded read-only policy ledger projection to Mission Control."""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "2.3-p5.policy-ledger.v1"
ROWS_ANCHOR = "def rows(q,args=()): return [dict(r) for r in c.execute(q,args).fetchall()]\nout={\n"
AUDIT_ANCHOR = " 'audits':rows('select id,task_id,approval_id,response_id,outcome,detail,occurred_at from execution_audit order by occurred_at,id'),\n"
MAIN_ANCHOR = "\ndef main():\n"
HANDOFF_ANCHOR = "    handoffs = handoff_projection(db, task_latest, set(registry))\n"

DB_PREP = "def rows(q,args=()): return [dict(r) for r in c.execute(q,args).fetchall()]\npolicy_decisions_installed = c.execute(\"select count(*) from sqlite_master where type='table' and name='policy_decisions'\").fetchone()[0] == 1\nout={\n"
DB_FIELDS = AUDIT_ANCHOR + " 'policy_decisions_installed':policy_decisions_installed,\n 'policy_decisions':rows('select * from policy_decisions order by evaluated_at,policy_decision_id') if policy_decisions_installed else [],\n"

FUNCTION = r'''
def policy_decision_projection(db):
    decisions=[]
    for source in db.get('policy_decisions') or []:
        row=dict(source)
        for key,default in (
            ('scope_constraints_json',{}),('evidence_refs_json',[]),('reason_codes_json',[]),
        ):
            raw=row.pop(key,None)
            try:
                row[key[:-5]]=json.loads(raw) if raw else default
            except Exception:
                row[key[:-5]]=default
        row['human_approval_required']=bool(row.get('human_approval_required'))
        row['approval_consumption_required']=bool(row.get('approval_consumption_required'))
        row['execution_preconditions_satisfied']=bool(row.get('execution_preconditions_satisfied'))
        decisions.append(row)
    authority_safe=all(d.get('authority_effect')=='none' for d in decisions)
    return {
        'schema_version':'2.3-p5.policy-ledger.v1',
        'installed':bool(db.get('policy_decisions_installed')),
        'count':len(decisions),
        'decisions':decisions,
        'read_only':True,
        'authority_effect':'none',
        'authority_invariant_satisfied':bool(authority_safe),
    }

'''

MAIN_INSERT = HANDOFF_ANCHOR + "    data['policy_decisions'] = policy_decision_projection(db)\n"


def patch(text: str) -> str:
    if MARKER in text:
        raise SystemExit("read model already contains P5 projection")
    for anchor,label in (
        (ROWS_ANCHOR,"db rows"),(AUDIT_ANCHOR,"audit field"),(MAIN_ANCHOR,"main"),(HANDOFF_ANCHOR,"handoff"),
    ):
        count=text.count(anchor)
        if count!=1:
            raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    text=text.replace(ROWS_ANCHOR,DB_PREP,1)
    text=text.replace(AUDIT_ANCHOR,DB_FIELDS,1)
    text=text.replace(MAIN_ANCHOR,"\n"+FUNCTION+"def main():\n",1)
    text=text.replace(HANDOFF_ANCHOR,MAIN_INSERT,1)
    return text


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("--output")
    args=ap.parse_args(); src=Path(args.source); out=Path(args.output) if args.output else src
    out.write_text(patch(src.read_text(encoding="utf-8")),encoding="utf-8")


if __name__=="__main__":
    main()
