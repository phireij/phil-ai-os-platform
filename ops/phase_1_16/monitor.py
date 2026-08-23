#!/usr/bin/env python3
"""Phil AI OS Phase 1.16 operational safety monitor.

Read-only monitor for Control API health/readiness and an optional safety snapshot.
It sends deduplicated Telegram alerts without polling Telegram or mutating Control API state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

USER_AGENT = "phil-ai-os-safety-monitor/1.0"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Config:
    base_url: str
    health_path: str
    ready_path: str
    safety_snapshot_url: Optional[str]
    auth_token: Optional[str]
    interval_seconds: int
    timeout_seconds: int
    alert_cooldown_seconds: int
    state_path: Path
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    strict_safety_snapshot: bool

    @staticmethod
    def from_env() -> "Config":
        base_url = os.getenv("PHIL_AI_OS_CONTROL_API_BASE_URL", "http://127.0.0.1:4870").rstrip("/")
        return Config(
            base_url=base_url,
            health_path=os.getenv("PHIL_AI_OS_HEALTH_PATH", "/healthz"),
            ready_path=os.getenv("PHIL_AI_OS_READY_PATH", "/readyz"),
            safety_snapshot_url=os.getenv("PHIL_AI_OS_SAFETY_SNAPSHOT_URL") or None,
            auth_token=os.getenv("PHIL_AI_OS_CONTROL_API_TOKEN") or None,
            interval_seconds=max(30, _env_int("PHIL_AI_OS_MONITOR_INTERVAL_SECONDS", 60)),
            timeout_seconds=max(1, _env_int("PHIL_AI_OS_MONITOR_TIMEOUT_SECONDS", 5)),
            alert_cooldown_seconds=max(60, _env_int("PHIL_AI_OS_ALERT_COOLDOWN_SECONDS", 1800)),
            state_path=Path(os.getenv("PHIL_AI_OS_MONITOR_STATE_PATH", "/var/lib/phil-ai-os-monitor/state.json")),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            strict_safety_snapshot=_env_bool("PHIL_AI_OS_STRICT_SAFETY_SNAPSHOT", False),
        )


@dataclass(frozen=True)
class Finding:
    key: str
    ok: bool
    summary: str
    detail: str = ""


class HttpClient:
    def __init__(self, timeout: int, auth_token: Optional[str] = None) -> None:
        self.timeout = timeout
        self.auth_token = auth_token

    def get_json(self, url: str) -> Tuple[int, Any]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                if data and ("json" in content_type or data[:1] in (b"{", b"[")):
                    return resp.status, json.loads(data.decode("utf-8"))
                return resp.status, data.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(body) if body else None
            except json.JSONDecodeError:
                payload = body
            return exc.code, payload


class TelegramNotifier:
    def __init__(self, token: Optional[str], chat_id: Optional[str], timeout: int) -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> None:
        if not self.enabled:
            print(text, flush=True)
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text, "disable_web_page_preview": "true"}).encode()
        req = urllib.request.Request(url, data=payload, headers={"User-Agent": USER_AGENT}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status // 100 != 2:
                raise RuntimeError(f"Telegram returned HTTP {resp.status}")


def _join(base: str, path: str) -> str:
    return f"{base}/{path.lstrip('/')}"


def check_endpoint(client: HttpClient, name: str, url: str) -> Finding:
    try:
        status, body = client.get_json(url)
    except Exception as exc:
        return Finding(name, False, f"{name} unreachable", repr(exc))
    if 200 <= status < 300:
        return Finding(name, True, f"{name} OK", f"HTTP {status}")
    return Finding(name, False, f"{name} failed", f"HTTP {status}: {body!r}"[:500])


def _pick(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def evaluate_safety_snapshot(data: Any, strict: bool = False) -> List[Finding]:
    if not isinstance(data, dict):
        return [Finding("safety_snapshot_shape", False, "Safety snapshot is not a JSON object", repr(data)[:500])]

    findings: List[Finding] = []
    checks: List[Tuple[str, Iterable[str], Any, str]] = [
        ("audit_consistency", ("audit_consistency", "auditConsistency"), "CONSISTENT", "Audit consistency degraded"),
        ("audit_issues", ("audit_issues", "issues", "auditIssues"), 0, "Audit issues detected"),
        ("audit_integrity", ("audit_integrity", "auditIntegrity"), "PASS", "Audit integrity failed"),
        ("unknown_approval_links", ("unknown_approval_links", "unknownApprovalLinks"), 0, "Unknown approval links detected"),
        ("multiple_successes_per_approval", ("multiple_successes_per_approval", "multipleSuccessesPerApproval"), 0, "Multiple successes per approval detected"),
        ("execution_kill_switch", ("execution_kill_switch", "executionKillSwitch"), True, "Execution kill switch is not enabled"),
        ("routed_execution_enabled", ("routed_execution_enabled", "routedExecutionEnabled"), False, "Routed execution unexpectedly enabled"),
        ("live_test_enabled", ("live_test_enabled", "liveTestEnabled"), False, "Live test unexpectedly enabled"),
    ]

    for key, aliases, expected, bad_summary in checks:
        value = _pick(data, *aliases)
        if value is None:
            if strict:
                findings.append(Finding(key, False, f"Safety field missing: {key}"))
            continue
        ok = str(value).upper() == str(expected).upper() if isinstance(expected, str) else value == expected
        findings.append(Finding(key, ok, f"{key} OK" if ok else bad_summary, f"expected={expected!r}, actual={value!r}"))

    if not findings and strict:
        findings.append(Finding("safety_snapshot_empty", False, "No recognized safety fields found"))
    return findings


def load_state(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def format_message(finding: Finding, recovered: bool = False) -> str:
    prefix = "✅ PHIL AI OS RECOVERY" if recovered else "🚨 PHIL AI OS SAFETY ALERT"
    body = [prefix, f"Check: {finding.key}", finding.summary]
    if finding.detail:
        body.append(finding.detail)
    return "\n".join(body)


def process_findings(findings: List[Finding], state: Dict[str, Any], notifier: TelegramNotifier, cooldown: int, now: int) -> Dict[str, Any]:
    checks = state.setdefault("checks", {})
    for finding in findings:
        prev = checks.get(finding.key, {}) if isinstance(checks.get(finding.key, {}), dict) else {}
        prev_ok = prev.get("ok")
        last_alert = int(prev.get("last_alert", 0) or 0)

        if not finding.ok:
            should_alert = prev_ok is not False or (now - last_alert) >= cooldown
            if should_alert:
                notifier.send(format_message(finding))
                last_alert = now
        elif prev_ok is False:
            notifier.send(format_message(finding, recovered=True))

        checks[finding.key] = {
            "ok": finding.ok,
            "summary": finding.summary,
            "detail": finding.detail,
            "last_checked": now,
            "last_alert": last_alert,
        }
    state["last_run"] = now
    return state


def run_checks(config: Config) -> List[Finding]:
    client = HttpClient(config.timeout_seconds, config.auth_token)
    findings = [
        check_endpoint(client, "control_api_health", _join(config.base_url, config.health_path)),
        check_endpoint(client, "control_api_ready", _join(config.base_url, config.ready_path)),
    ]

    if config.safety_snapshot_url:
        try:
            status, body = client.get_json(config.safety_snapshot_url)
            if 200 <= status < 300:
                findings.extend(evaluate_safety_snapshot(body, config.strict_safety_snapshot))
            else:
                findings.append(Finding("safety_snapshot", False, "Safety snapshot request failed", f"HTTP {status}: {body!r}"[:500]))
        except Exception as exc:
            findings.append(Finding("safety_snapshot", False, "Safety snapshot unreachable", repr(exc)))
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phil AI OS read-only operational safety monitor")
    parser.add_argument("--once", action="store_true", help="Run one check cycle and exit")
    parser.add_argument("--print-config", action="store_true", help="Print non-secret configuration and exit")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.print_config:
        safe = asdict(config)
        safe["auth_token"] = "***" if config.auth_token else None
        safe["telegram_bot_token"] = "***" if config.telegram_bot_token else None
        safe["state_path"] = str(config.state_path)
        print(json.dumps(safe, indent=2, sort_keys=True))
        return 0

    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id, config.timeout_seconds)
    while True:
        now = int(time.time())
        findings = run_checks(config)
        state = load_state(config.state_path)
        try:
            state = process_findings(findings, state, notifier, config.alert_cooldown_seconds, now)
        except Exception as exc:
            print(f"notification failure: {exc!r}", file=sys.stderr, flush=True)
            if args.once:
                return 2
        else:
            save_state(config.state_path, state)

        failed = [f for f in findings if not f.ok]
        print(json.dumps({"ok": not failed, "failed": [asdict(f) for f in failed], "checks": len(findings)}, sort_keys=True), flush=True)
        if args.once:
            return 1 if failed else 0
        time.sleep(config.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
