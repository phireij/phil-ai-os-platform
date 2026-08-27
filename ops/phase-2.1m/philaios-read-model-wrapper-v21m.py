#!/usr/bin/env python3
import json,subprocess

BASE='/opt/phil-ai-os/mission-control/read-model.py.pre-phase21m'
RUNTIME='/opt/phil-ai-os/mission-control/agent-runtime-read-model.py'

def load(path):
    p=subprocess.run(['python3',path],capture_output=True,text=True,timeout=20)
    if p.returncode!=0:
        raise SystemExit(p.stderr.strip() or f'{path} failed')
    return json.loads(p.stdout)

def main():
    data=load(BASE)
    runtime=load(RUNTIME)
    data['schema_version']='2.1m.v1'
    data['agent_runtime']=runtime
    data.setdefault('governance',{})['agent_runtime_presence_authority_effect']='none'
    print(json.dumps(data,sort_keys=True))

if __name__=='__main__':
    main()
