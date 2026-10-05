#!/usr/bin/env python3
"""AO-1/AO-5 bounded Mission Control project projection patch.

This patch only reads the committed master project status file and exposes it
inside the existing Mission Control read model. It grants no authority.
"""
from __future__ import annotations
import argparse
from pathlib import Path

MARKER = "ao-mvp.master-projects.v1"
MAIN_ANCHOR = "\ndef main():\n"
LOAD_ANCHOR = "    data = load_base()\n"

FUNCTION = r'''
def master_project_projection():
    path = pathlib.Path('/opt/phil-ai-os/current/ops/project-state/master-project-status.v1.json')
    if not path.exists():
        return {
            'schema_version':'ao-mvp.master-projects.v1',
            'status':'unknown',
            'evidence_complete':False,
            'projects':[],
            'authority_effect':'none',
            'mutation_authorized':False,
        }
    try:
        source=json.loads(path.read_text(encoding='utf-8'))
        safe=(
            source.get('authority_effect') == 'none' and
            source.get('autonomy_ceiling') == 'A0' and
            all((p.get('authority') or {}).get('mutation_authorized') is False for p in source.get('projects',[]))
        )
        if not safe:
            raise ValueError('master project status violates A0 read-only boundary')
        return {
            'schema_version':'ao-mvp.master-projects.v1',
            'status':source.get('overall_status','unknown'),
            'evidence_complete':True,
            'projects':source.get('projects',[]),
            'authority_effect':'none',
            'mutation_authorized':False,
        }
    except Exception:
        return {
            'schema_version':'ao-mvp.master-projects.v1',
            'status':'unknown',
            'evidence_complete':False,
            'projects':[],
            'authority_effect':'none',
            'mutation_authorized':False,
        }

'''

def patch(text: str) -> str:
    if MARKER in text:
        raise SystemExit("read model already contains AO-MVP project projection")
    for anchor,label in ((MAIN_ANCHOR,"main"),(LOAD_ANCHOR,"load_base")):
        if text.count(anchor) != 1:
            raise SystemExit(f"expected exactly one {label} anchor")
    text=text.replace(MAIN_ANCHOR,"\n"+FUNCTION+"def main():\n",1)
    text=text.replace(LOAD_ANCHOR,LOAD_ANCHOR+"    data['master_projects'] = master_project_projection()\n",1)
    return text

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("--output")
    args=ap.parse_args(); src=Path(args.source); out=Path(args.output) if args.output else src
    out.write_text(patch(src.read_text(encoding="utf-8")),encoding="utf-8")

if __name__=="__main__":
    main()
