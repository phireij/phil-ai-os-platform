#!/usr/bin/env python3
"""Phil AI OS Phase 1.16 operational safety monitor.

Read-only monitor for Control API health/readiness and Mission Control snapshot.
It sends deduplicated Telegram alerts without polling Telegram or mutating Control API state.
"""
from __future__ import annotations
import argparse, json, os, time, urllib.error, urllib.parse, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = "phil-ai-os-safety-monitor/1.1"

def _env_bool(name, default):
    raw=os.getenv(name); return default if raw is None else raw.strip().lower() in {"1","true","yes","on"}
def _env_int(name, default):
    raw=os.getenv(name); return int(raw) if raw else default
def _read_secret(env_name, file_env_name):
    direct=(os.getenv(env_name) or "").strip()
    if direct: return direct
    path=(os.getenv(file_env_name) or "").strip()
    if not path: return None
    return Path(path).read_text().strip()
def _load_env_file(path):
    values={}
    if not path: return values
    for line in Path(path).read_text().splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line: continue
        k,v=line.split("=",1); values[k.strip()]=v.strip().strip('"').strip("'")
    return values

@dataclass(frozen=True)
class Config:
    base_url:str; health_path:str; ready_path:str; safety_snapshot_url:Optional[str]; auth_token:Optional[str]
    interval_seconds:int; timeout_seconds:int; alert_cooldown_seconds:int; state_path:Path
    telegram_bot_token:Optional[str]; telegram_chat_id:Optional[str]; strict_safety_snapshot:bool
    @staticmethod
    def from_env():
        base=os.getenv("PHIL_AI_OS_CONTROL_API_BASE_URL","http://127.0.0.1:4870").rstrip("/")
        hermes=_load_env_file(os.getenv("PHIL_AI_OS_HERMES_ENV_FILE",""))
        return Config(base, os.getenv("PHIL_AI_OS_HEALTH_PATH","/healthz"), os.getenv("PHIL_AI_OS_READY_PATH","/readyz"),
            os.getenv("PHIL_AI_OS_SAFETY_SNAPSHOT_URL") or None,
            _read_secret("PHIL_AI_OS_CONTROL_API_TOKEN","PHIL_AI_OS_CONTROL_API_TOKEN_FILE"),
            max(30,_env_int("PHIL_AI_OS_MONITOR_INTERVAL_SECONDS",60)), max(1,_env_int("PHIL_AI_OS_MONITOR_TIMEOUT_SECONDS",5)),
            max(60,_env_int("PHIL_AI_OS_ALERT_COOLDOWN_SECONDS",1800)), Path(os.getenv("PHIL_AI_OS_MONITOR_STATE_PATH","/var/lib/phil-ai-os-monitor/state.json")),
            (os.getenv("TELEGRAM_BOT_TOKEN") or hermes.get("TELEGRAM_BOT_TOKEN") or None),
            (os.getenv("TELEGRAM_CHAT_ID") or hermes.get("TELEGRAM_HOME_CHANNEL") or None), _env_bool("PHIL_AI_OS_STRICT_SAFETY_SNAPSHOT",False))

@dataclass(frozen=True)
class Finding:
    key:str; ok:bool; summary:str; detail:str=""

class HttpClient:
    def __init__(self,timeout,auth_token=None): self.timeout=timeout; self.auth_token=auth_token
    def get_json(self,url):
        h={"User-Agent":USER_AGENT,"Accept":"application/json"}
        if self.auth_token: h["Authorization"]="Bearer "+self.auth_token
        req=urllib.request.Request(url,headers=h,method="GET")
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r:
                raw=r.read(); return r.status, json.loads(raw.decode()) if raw else None
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors="replace")
            try: body=json.loads(raw) if raw else None
            except json.JSONDecodeError: body=raw
            return e.code,body

class TelegramNotifier:
    def __init__(self,token,chat_id,timeout): self.token=token; self.chat_id=chat_id; self.timeout=timeout
    @property
    def enabled(self): return bool(self.token and self.chat_id)
    def send(self,text):
        if not self.enabled: print(text,flush=True); return
        payload=json.dumps({"chat_id":self.chat_id,"text":text,"disable_web_page_preview":True}).encode()
        req=urllib.request.Request(f"https://api.telegram.org/bot{self.token}/sendMessage",data=payload,headers={"Content-Type":"application/json","User-Agent":USER_AGENT},method="POST")
        with urllib.request.urlopen(req,timeout=self.timeout) as r:
            if r.status//100!=2: raise RuntimeError(f"Telegram HTTP {r.status}")

def _join(base,path): return f"{base}/{path.lstrip('/')}"
def check_endpoint(client,name,url):
    try: status,_=client.get_json(url)
    except Exception as e: return Finding(name,False,f"{name} unreachable",repr(e))
    return Finding(name,200<=status<300,f"{name} OK" if 200<=status<300 else f"{name} failed",f"HTTP {status}")

def evaluate_safety_snapshot(data,strict=False):
    if not isinstance(data,dict): return [Finding("safety_snapshot_shape",False,"Safety snapshot is not a JSON object")]
    runtime=data.get("runtime") if isinstance(data.get("runtime"),dict) else {}
    checks=[("execution_kill_switch",runtime.get("execution_kill_switch"),True,"Execution kill switch is not enabled"),
            ("routed_execution_enabled",runtime.get("routed_execution_enabled"),False,"Routed execution unexpectedly enabled"),
            ("live_test_enabled",runtime.get("live_test_enabled"),False,"Live test unexpectedly enabled")]
    out=[]
    for key,value,expected,bad in checks:
        if value is None:
            if strict: out.append(Finding(key,False,f"Safety field missing: {key}"))
            continue
        out.append(Finding(key,value==expected,f"{key} OK" if value==expected else bad,f"expected={expected!r}, actual={value!r}"))
    status=data.get("status")
    if status is not None:
        ok=str(status).lower() in {"ok","healthy","ready"}; out.append(Finding("mission_control_status",ok,"Mission Control status OK" if ok else "Mission Control status degraded",f"status={status!r}"))
    return out

def load_state(path):
    try:
        with path.open() as f: data=json.load(f); return data if isinstance(data,dict) else {}
    except Exception: return {}
def save_state(path,state):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(json.dumps(state,indent=2,sort_keys=True)+"\n"); os.replace(tmp,path)
def format_message(f,recovered=False):
    p="✅ PHIL AI OS RECOVERY" if recovered else "🚨 PHIL AI OS SAFETY ALERT"; return "\n".join([p,f"Check: {f.key}",f.summary]+([f.detail] if f.detail else []))
def process_findings(findings,state,notifier,cooldown,now):
    checks=state.setdefault("checks",{})
    for f in findings:
        prev=checks.get(f.key,{}) if isinstance(checks.get(f.key,{}),dict) else {}; prev_ok=prev.get("ok"); last=int(prev.get("last_alert",0) or 0)
        if not f.ok and (prev_ok is not False or now-last>=cooldown): notifier.send(format_message(f)); last=now
        elif f.ok and prev_ok is False: notifier.send(format_message(f,True))
        checks[f.key]={"ok":f.ok,"summary":f.summary,"detail":f.detail,"last_checked":now,"last_alert":last}
    state["last_run"]=now; return state

def run_checks(c):
    client=HttpClient(c.timeout_seconds,c.auth_token); fs=[check_endpoint(client,"control_api_health",_join(c.base_url,c.health_path)),check_endpoint(client,"control_api_ready",_join(c.base_url,c.ready_path))]
    if c.safety_snapshot_url:
        try:
            status,body=client.get_json(c.safety_snapshot_url)
            fs.extend(evaluate_safety_snapshot(body,c.strict_safety_snapshot) if 200<=status<300 else [Finding("safety_snapshot",False,"Safety snapshot request failed",f"HTTP {status}")])
        except Exception as e: fs.append(Finding("safety_snapshot",False,"Safety snapshot unreachable",repr(e)))
    return fs

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--once",action="store_true"); p.add_argument("--print-config",action="store_true"); p.add_argument("--test-alert",action="store_true"); a=p.parse_args(argv); c=Config.from_env(); n=TelegramNotifier(c.telegram_bot_token,c.telegram_chat_id,c.timeout_seconds)
    if a.print_config:
        safe=asdict(c); safe["auth_token"]="***" if c.auth_token else None; safe["telegram_bot_token"]="***" if c.telegram_bot_token else None; safe["telegram_chat_id"]="***" if c.telegram_chat_id else None; safe["state_path"]=str(c.state_path); print(json.dumps(safe,indent=2,sort_keys=True)); return 0
    if a.test_alert:
        if not n.enabled: print("Telegram notifier not configured",file=os.sys.stderr); return 2
        n.send("🧪 PHIL AI OS Phase 1.16 TEST ALERT\nOperational safety monitoring Telegram path is working.\nNo action required."); print("PHIL_AI_OS_PHASE_1_16_TELEGRAM_TEST_OK"); return 0
    while True:
        now=int(time.time()); fs=run_checks(c); state=load_state(c.state_path)
        try: state=process_findings(fs,state,n,c.alert_cooldown_seconds,now); save_state(c.state_path,state)
        except Exception as e:
            print(f"notification failure: {e!r}",file=os.sys.stderr,flush=True)
            if a.once:return 2
        failed=[f for f in fs if not f.ok]; print(json.dumps({"ok":not failed,"failed":[asdict(f) for f in failed],"checks":len(fs)},sort_keys=True),flush=True)
        if a.once:return 1 if failed else 0
        time.sleep(c.interval_seconds)
if __name__=="__main__": raise SystemExit(main())
