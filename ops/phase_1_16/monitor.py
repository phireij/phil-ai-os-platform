#!/usr/bin/env python3
"""Phil AI OS operational safety monitor."""
from __future__ import annotations
import argparse,json,os,time,urllib.error,urllib.request
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Optional
USER_AGENT="phil-ai-os-safety-monitor/1.2"
def _env_bool(n,d):
 r=os.getenv(n); return d if r is None else r.strip().lower() in {"1","true","yes","on"}
def _env_int(n,d):
 r=os.getenv(n); return int(r) if r else d
def _read_secret(n,fn):
 v=(os.getenv(n) or "").strip()
 if v:return v
 p=(os.getenv(fn) or "").strip(); return Path(p).read_text().strip() if p else None
def _load_env_file(path):
 out={}
 if not path:return out
 for line in Path(path).read_text().splitlines():
  if not line or line.lstrip().startswith("#") or "=" not in line:continue
  k,v=line.split("=",1);out[k.strip()]=v.strip().strip('"').strip("'")
 return out
@dataclass(frozen=True)
class Config:
 base_url:str;health_path:str;ready_path:str;safety_snapshot_url:Optional[str];auth_token:Optional[str];interval_seconds:int;timeout_seconds:int;alert_cooldown_seconds:int;state_path:Path;telegram_bot_token:Optional[str];telegram_chat_id:Optional[str];strict_safety_snapshot:bool;backup_status_file:Optional[Path];backup_max_age_seconds:int
 @staticmethod
 def from_env():
  base=os.getenv("PHIL_AI_OS_CONTROL_API_BASE_URL","http://127.0.0.1:4870").rstrip("/");h=_load_env_file(os.getenv("PHIL_AI_OS_HERMES_ENV_FILE",""));b=(os.getenv("PHIL_AI_OS_BACKUP_STATUS_FILE") or "").strip()
  return Config(base,os.getenv("PHIL_AI_OS_HEALTH_PATH","/healthz"),os.getenv("PHIL_AI_OS_READY_PATH","/readyz"),os.getenv("PHIL_AI_OS_SAFETY_SNAPSHOT_URL") or None,_read_secret("PHIL_AI_OS_CONTROL_API_TOKEN","PHIL_AI_OS_CONTROL_API_TOKEN_FILE"),max(30,_env_int("PHIL_AI_OS_MONITOR_INTERVAL_SECONDS",60)),max(1,_env_int("PHIL_AI_OS_MONITOR_TIMEOUT_SECONDS",5)),max(60,_env_int("PHIL_AI_OS_ALERT_COOLDOWN_SECONDS",1800)),Path(os.getenv("PHIL_AI_OS_MONITOR_STATE_PATH","/var/lib/phil-ai-os-monitor/state.json")),os.getenv("TELEGRAM_BOT_TOKEN") or h.get("TELEGRAM_BOT_TOKEN") or None,os.getenv("TELEGRAM_CHAT_ID") or h.get("TELEGRAM_HOME_CHANNEL") or None,_env_bool("PHIL_AI_OS_STRICT_SAFETY_SNAPSHOT",False),Path(b) if b else None,max(300,_env_int("PHIL_AI_OS_BACKUP_MAX_AGE_SECONDS",18000)))
@dataclass(frozen=True)
class Finding:key:str;ok:bool;summary:str;detail:str=""
class HttpClient:
 def __init__(self,t,a=None):self.timeout=t;self.auth_token=a
 def get_json(self,url):
  h={"User-Agent":USER_AGENT,"Accept":"application/json"}
  if self.auth_token:h["Authorization"]="Bearer "+self.auth_token
  req=urllib.request.Request(url,headers=h,method="GET")
  try:
   with urllib.request.urlopen(req,timeout=self.timeout) as r:return r.status,json.loads(r.read().decode())
  except urllib.error.HTTPError as e:return e.code,None
class TelegramNotifier:
 def __init__(self,t,c,to):self.token=t;self.chat_id=c;self.timeout=to
 @property
 def enabled(self):return bool(self.token and self.chat_id)
 def send(self,text):
  if not self.enabled:print(text,flush=True);return
  raw=json.dumps({"chat_id":self.chat_id,"text":text,"disable_web_page_preview":True}).encode();req=urllib.request.Request(f"https://api.telegram.org/bot{self.token}/sendMessage",data=raw,headers={"Content-Type":"application/json"},method="POST")
  with urllib.request.urlopen(req,timeout=self.timeout) as r:
   if r.status//100!=2:raise RuntimeError(f"Telegram HTTP {r.status}")
def _join(b,p):return f"{b}/{p.lstrip('/')}"
def check_endpoint(c,n,u):
 try:s,_=c.get_json(u)
 except Exception as e:return Finding(n,False,f"{n} unreachable",repr(e))
 return Finding(n,200<=s<300,f"{n} OK" if 200<=s<300 else f"{n} failed",f"HTTP {s}")
def evaluate_safety_snapshot(d,strict=False):
 if not isinstance(d,dict):return [Finding("safety_snapshot_shape",False,"Safety snapshot is not a JSON object")]
 r=d.get("runtime") if isinstance(d.get("runtime"),dict) else {};out=[]
 for k,v,e,bad in [("execution_kill_switch",r.get("execution_kill_switch"),True,"Execution kill switch is not enabled"),("routed_execution_enabled",r.get("routed_execution_enabled"),False,"Routed execution unexpectedly enabled"),("live_test_enabled",r.get("live_test_enabled"),False,"Live test unexpectedly enabled")]:
  if v is None:
   if strict:out.append(Finding(k,False,f"Safety field missing: {k}"))
  else:out.append(Finding(k,v==e,f"{k} OK" if v==e else bad,f"expected={e!r}, actual={v!r}"))
 s=d.get("status")
 if s is not None:
  ok=str(s).lower() in {"ok","healthy","ready"};out.append(Finding("mission_control_status",ok,"Mission Control status OK" if ok else "Mission Control status degraded",f"status={s!r}"))
 return out
def check_backup(c,now):
 if not c.backup_status_file:return []
 try:d=json.loads(c.backup_status_file.read_text())
 except Exception as e:return [Finding("backup_status",False,"Backup status unavailable",repr(e))]
 if d.get("ok") is not True:return [Finding("backup_status",False,"Latest backup failed",str(d.get("error","unknown error"))[:400])]
 ts=str(d.get("timestamp", ""))
 try:age=now-int(time.mktime(time.strptime(ts,"%Y%m%dT%H%M%SZ")))
 except Exception:return [Finding("backup_status",False,"Backup timestamp invalid",f"timestamp={ts!r}")]
 ok=age<=c.backup_max_age_seconds
 return [Finding("backup_status",ok,"Backup status OK" if ok else "Latest backup is stale",f"age_seconds={age}, max_age_seconds={c.backup_max_age_seconds}, quick_check={d.get('quick_check')}, tables={d.get('tables')}")]
def load_state(p):
 try:
  d=json.loads(p.read_text());return d if isinstance(d,dict) else {}
 except Exception:return {}
def save_state(p,s):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+".tmp");t.write_text(json.dumps(s,indent=2,sort_keys=True)+"\n");os.replace(t,p)
def msg(f,rec=False):return "\n".join(["✅ PHIL AI OS RECOVERY" if rec else "🚨 PHIL AI OS SAFETY ALERT",f"Check: {f.key}",f.summary]+([f.detail] if f.detail else []))
def process(fs,state,n,cool,now):
 checks=state.setdefault("checks",{})
 for f in fs:
  p=checks.get(f.key,{}) if isinstance(checks.get(f.key,{}),dict) else {};po=p.get("ok");last=int(p.get("last_alert",0) or 0)
  if not f.ok and (po is not False or now-last>=cool):n.send(msg(f));last=now
  elif f.ok and po is False:n.send(msg(f,True))
  checks[f.key]={"ok":f.ok,"summary":f.summary,"detail":f.detail,"last_checked":now,"last_alert":last}
 state["last_run"]=now;return state
def run_checks(c,now):
 cli=HttpClient(c.timeout_seconds,c.auth_token);fs=[check_endpoint(cli,"control_api_health",_join(c.base_url,c.health_path)),check_endpoint(cli,"control_api_ready",_join(c.base_url,c.ready_path))]
 if c.safety_snapshot_url:
  try:s,b=cli.get_json(c.safety_snapshot_url);fs.extend(evaluate_safety_snapshot(b,c.strict_safety_snapshot) if 200<=s<300 else [Finding("safety_snapshot",False,"Safety snapshot request failed",f"HTTP {s}")])
  except Exception as e:fs.append(Finding("safety_snapshot",False,"Safety snapshot unreachable",repr(e)))
 fs.extend(check_backup(c,now));return fs
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--once",action="store_true");p.add_argument("--print-config",action="store_true");a=p.parse_args(argv);c=Config.from_env();n=TelegramNotifier(c.telegram_bot_token,c.telegram_chat_id,c.timeout_seconds)
 if a.print_config:
  d=asdict(c);d["auth_token"]="***" if c.auth_token else None;d["telegram_bot_token"]="***" if c.telegram_bot_token else None;d["telegram_chat_id"]="***" if c.telegram_chat_id else None;d["state_path"]=str(c.state_path);d["backup_status_file"]=str(c.backup_status_file) if c.backup_status_file else None;print(json.dumps(d,indent=2,sort_keys=True));return 0
 while True:
  now=int(time.time());fs=run_checks(c,now);state=load_state(c.state_path)
  try:state=process(fs,state,n,c.alert_cooldown_seconds,now);save_state(c.state_path,state)
  except Exception as e:
   print(f"notification failure: {e!r}",file=os.sys.stderr,flush=True)
   if a.once:return 2
  failed=[f for f in fs if not f.ok];print(json.dumps({"ok":not failed,"failed":[asdict(f) for f in failed],"checks":len(fs)},sort_keys=True),flush=True)
  if a.once:return 1 if failed else 0
  time.sleep(c.interval_seconds)
if __name__=="__main__":raise SystemExit(main())
