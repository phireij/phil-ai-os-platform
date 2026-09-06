#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-deploy}"
ROOT=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1
APP="$ROOT/services/core/control-api/app.py"
COMPOSE="$ROOT/infrastructure/core/compose.yml"
SECRET_DIR="$ROOT/infrastructure/core/secrets"
RUNTIME_DIR="$ROOT/runtime"
TOKEN_STAGED=/tmp/ruby_twilio_auth_token.philaios
EXPECTED_SHA=55c596c19b959c1541d1bfac5e1a496ce6fdda4d4aa8d473f568917a11d6ca84
OLD_IMAGE=phil-ai-os/control-api:0.21.2-phase23p5
NEW_IMAGE=phil-ai-os/control-api:0.21.3-twilio-status-callback
CALLBACK_URL=https://hermes-agent-whow.srv1833510.hstgr.cloud/v1/webhooks/twilio/sms-status
LATEST="$RUNTIME_DIR/twilio-status-callback-latest-rollback"

rollback_latest() {
  test -f "$LATEST" || { echo rollback_snapshot_missing=true >&2; return 1; }
  SNAP="$(cat "$LATEST")"
  test -f "$SNAP/app.py" && test -f "$SNAP/compose.yml"
  cp "$SNAP/app.py" "$APP"
  cp "$SNAP/compose.yml" "$COMPOSE"
  if test "$(cat "$SNAP/had_token")" = true; then
    cp "$SNAP/ruby_twilio_auth_token" "$SECRET_DIR/ruby_twilio_auth_token"
  else
    rm -f "$SECRET_DIR/ruby_twilio_auth_token"
  fi
  cd "$ROOT/infrastructure/core"
  docker compose up -d --no-deps control-api
  for attempt in $(seq 1 18); do
    if curl -fsS --max-time 3 http://127.0.0.1:4870/healthz >/dev/null; then
      echo rollback_health=true
      return 0
    fi
    sleep 3
  done
  echo rollback_health=false >&2
  return 1
}

if test "$MODE" = rollback; then
  rollback_latest
  exit 0
fi

test "$MODE" = deploy

test -f "$APP" && test -f "$COMPOSE" && test -f "$TOKEN_STAGED"
test "$(sha256sum "$APP" | awk '{print $1}')" = "$EXPECTED_SHA"
grep -Fq "image: $OLD_IMAGE" "$COMPOSE"
! grep -Fq 'PHIL_AI_OS_TWILIO_STATUS_CALLBACK_V1' "$APP"
! grep -Fq 'philaios-twilio-status' "$COMPOSE"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
SNAP="$RUNTIME_DIR/twilio-status-callback-rollback-$TS"
mkdir -p "$SNAP"
cp "$APP" "$SNAP/app.py"
cp "$COMPOSE" "$SNAP/compose.yml"
if test -f "$SECRET_DIR/ruby_twilio_auth_token"; then
  cp "$SECRET_DIR/ruby_twilio_auth_token" "$SNAP/ruby_twilio_auth_token"
  echo true > "$SNAP/had_token"
else
  echo false > "$SNAP/had_token"
fi
printf '%s\n' "$SNAP" > "$LATEST"

cp "$APP" /tmp/control-api-app.py.candidate
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/control-api-app.py.candidate')
s=p.read_text(encoding='utf-8')

old='from urllib.parse import urlparse, parse_qs\n'
new='from urllib.parse import urlparse, parse_qs, parse_qsl\n'
if s.count(old)!=1:
    raise SystemExit('import anchor mismatch')
s=s.replace(old,new,1)

anchor='DB_PATH = STATE_DIR / "control-plane.db"\n'
block='''DB_PATH = STATE_DIR / "control-plane.db"

# PHIL_AI_OS_TWILIO_STATUS_CALLBACK_V1
TWILIO_STATUS_CALLBACK_PATH = "/v1/webhooks/twilio/sms-status"
TWILIO_STATUS_CALLBACK_URL = os.getenv(
    "PHIL_AI_OS_TWILIO_STATUS_CALLBACK_URL",
    "https://hermes-agent-whow.srv1833510.hstgr.cloud/v1/webhooks/twilio/sms-status",
)
TWILIO_AUTH_TOKEN_FILE = SECRETS_DIR / "ruby_twilio_auth_token"
TWILIO_MAX_BODY_BYTES = 8192
'''
if s.count(anchor)!=1:
    raise SystemExit('DB anchor mismatch')
s=s.replace(anchor,block,1)

anchor='def migrate_model_catalog(conn):\n'
helpers=r'''def _twilio_auth_token():
    try:
        token=TWILIO_AUTH_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return token


def _twilio_signature(url, params, token):
    material=url+"".join(
        f"{name}{value}" for name,value in sorted(params.items(), key=lambda item:item[0])
    )
    digest=hmac.new(token.encode("utf-8"),material.encode("utf-8"),hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _record_twilio_delivery_status(message_sid, message_status, error_code):
    sid_hash=hashlib.sha256(message_sid.encode("utf-8")).hexdigest()[:16]
    conn=db()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS twilio_sms_delivery_events(
            event_id TEXT PRIMARY KEY,
            received_at TEXT NOT NULL,
            message_sid_hash TEXT NOT NULL,
            message_status TEXT NOT NULL,
            error_code TEXT,
            authority_effect TEXT NOT NULL CHECK(authority_effect='none'),
            retry_requested INTEGER NOT NULL CHECK(retry_requested=0)
        )
        """)
        conn.execute(
            "INSERT INTO twilio_sms_delivery_events(event_id,received_at,message_sid_hash,message_status,error_code,authority_effect,retry_requested) VALUES(?,?,?,?,?,'none',0)",
            (str(uuid.uuid4()),now_iso(),sid_hash,message_status,error_code),
        )
        conn.commit()
    finally:
        conn.close()


def twilio_status_callback(headers, body):
    if len(body)>TWILIO_MAX_BODY_BYTES:
        return 413
    content_type=str(headers.get("Content-Type") or "").split(";",1)[0].strip().lower()
    if content_type!="application/x-www-form-urlencoded":
        return 415
    signature=str(headers.get("X-Twilio-Signature") or "").strip()
    if not signature:
        return 403
    token=_twilio_auth_token()
    if not token:
        return 503
    try:
        pairs=parse_qsl(
            body.decode("utf-8"),keep_blank_values=True,strict_parsing=True,
            encoding="utf-8",errors="strict",
        )
    except (UnicodeDecodeError,ValueError):
        return 400
    params={}
    for key,value in pairs:
        if key in params:
            return 400
        params[key]=value
    expected=_twilio_signature(TWILIO_STATUS_CALLBACK_URL,params,token)
    if not hmac.compare_digest(expected,signature):
        return 403
    sid=str(params.get("MessageSid") or "").strip()
    status=str(params.get("MessageStatus") or "").strip().lower()
    error_code=str(params.get("ErrorCode") or "").strip() or None
    if not sid.startswith("SM") or len(sid)>64:
        return 400
    if not status or len(status)>64 or not all(ch.isalnum() or ch in {'_','-'} for ch in status):
        return 400
    if error_code is not None and (len(error_code)>32 or not error_code.isdigit()):
        return 400
    _record_twilio_delivery_status(sid,status,error_code)
    return 204


def migrate_model_catalog(conn):
'''
if s.count(anchor)!=1:
    raise SystemExit('function anchor mismatch')
s=s.replace(anchor,helpers,1)

anchor='''        if path.startswith("/v1/") and not authorized(self.headers):
            self._json(401,{"status":"unauthorized","timestamp":now_iso()}); return
'''
route='''        if path==TWILIO_STATUS_CALLBACK_PATH:
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
            except (TypeError,ValueError):
                self._json(400,{"status":"rejected"}); return
            if length<0 or length>TWILIO_MAX_BODY_BYTES:
                self._json(413,{"status":"rejected"}); return
            body=self.rfile.read(length) if length else b""
            code=twilio_status_callback(self.headers,body)
            if code==204:
                self.send_response(204)
                self.send_header("Cache-Control","no-store")
                self.send_header("Content-Length","0")
                self.end_headers()
            else:
                self._json(code,{"status":"rejected"})
            return

        if path.startswith("/v1/") and not authorized(self.headers):
            self._json(401,{"status":"unauthorized","timestamp":now_iso()}); return
'''
post_anchor='    def do_POST(self):\n'
if s.count(post_anchor)!=1:
    raise SystemExit('do_POST anchor mismatch')
post_pos=s.index(post_anchor)
prefix=s[:post_pos]
post=s[post_pos:]
if post.count(anchor)!=1:
    raise SystemExit('do_POST route anchor mismatch')
post=post.replace(anchor,route,1)
s=prefix+post
p.write_text(s,encoding='utf-8')
PY

python3 -m py_compile /tmp/control-api-app.py.candidate
grep -Fq 'PHIL_AI_OS_TWILIO_STATUS_CALLBACK_V1' /tmp/control-api-app.py.candidate
grep -Fq '_record_twilio_delivery_status' /tmp/control-api-app.py.candidate
grep -Fq 'hmac.compare_digest' /tmp/control-api-app.py.candidate

cp "$COMPOSE" /tmp/control-api-compose.yml.candidate
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/control-api-compose.yml.candidate')
s=p.read_text(encoding='utf-8')
old='    image: phil-ai-os/control-api:0.21.2-phase23p5\n'
new='    image: phil-ai-os/control-api:0.21.3-twilio-status-callback\n'
if s.count(old)!=1:
    raise SystemExit('image anchor mismatch')
s=s.replace(old,new,1)
anchor='      traefik.http.routers.philaios-mission-control.service: philaios-approval\n'
labels='''      traefik.http.routers.philaios-mission-control.service: philaios-approval
      traefik.http.routers.philaios-twilio-status.entrypoints: websecure
      traefik.http.routers.philaios-twilio-status.rule: "Host(`hermes-agent-whow.srv1833510.hstgr.cloud`) && Path(`/v1/webhooks/twilio/sms-status`) && Method(`POST`)"
      traefik.http.routers.philaios-twilio-status.priority: "220"
      traefik.http.routers.philaios-twilio-status.tls.certresolver: letsencrypt
      traefik.http.routers.philaios-twilio-status.service: philaios-approval
'''
if s.count(anchor)!=1:
    raise SystemExit('traefik anchor mismatch')
s=s.replace(anchor,labels,1)
env_anchor='      PHIL_AI_OS_PORT: "4870"\n'
env='''      PHIL_AI_OS_PORT: "4870"
      PHIL_AI_OS_TWILIO_STATUS_CALLBACK_URL: "https://hermes-agent-whow.srv1833510.hstgr.cloud/v1/webhooks/twilio/sms-status"
'''
if s.count(env_anchor)!=1:
    raise SystemExit('environment anchor mismatch')
s=s.replace(env_anchor,env,1)
p.write_text(s,encoding='utf-8')
PY

grep -Fq 'philaios-twilio-status' /tmp/control-api-compose.yml.candidate
grep -Fq "$CALLBACK_URL" /tmp/control-api-compose.yml.candidate

rollback_on_error() {
  code=$?
  echo deployment_failed=true >&2
  rollback_latest || true
  exit "$code"
}
trap rollback_on_error ERR

install -d -m 0750 "$SECRET_DIR"
install -m 0440 -o 10001 -g 10001 "$TOKEN_STAGED" "$SECRET_DIR/ruby_twilio_auth_token"
rm -f "$TOKEN_STAGED"
cp /tmp/control-api-app.py.candidate "$APP"
cp /tmp/control-api-compose.yml.candidate "$COMPOSE"
rm -f /tmp/control-api-app.py.candidate /tmp/control-api-compose.yml.candidate

cd "$ROOT/infrastructure/core"
docker compose config -q
docker compose build control-api
docker image inspect "$NEW_IMAGE" >/dev/null
docker compose up -d --no-deps control-api

for attempt in $(seq 1 18); do
  if curl -fsS --max-time 3 http://127.0.0.1:4870/healthz >/dev/null; then
    break
  fi
  if test "$attempt" -eq 18; then
    echo control_api_health_failed=true >&2
    false
  fi
  sleep 3
done

CID="$(docker ps --filter name=phil-ai-os-core-control-api-1 --format '{{.ID}}')"
test -n "$CID"
test "$(docker inspect "$CID" --format '{{.Config.Image}}')" = "$NEW_IMAGE"
docker exec "$CID" test -r /run/philaios-secrets/ruby_twilio_auth_token
docker exec "$CID" python -m py_compile /app/app.py
docker exec "$CID" grep -Fq 'PHIL_AI_OS_TWILIO_STATUS_CALLBACK_V1' /app/app.py
trap - ERR

echo rollback_snapshot="$SNAP"
echo deployment_image="$NEW_IMAGE"
echo control_api_health=true
echo sms_send=false
echo automatic_retry=false
echo woo_mutation=false
echo payment_mutation=false
echo dns_mutation=false
echo mission_control_mutation=false
