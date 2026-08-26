#!/usr/bin/env python3
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.getenv('PHIL_AI_OS_MC_HOST', '127.0.0.1')
PORT = int(os.getenv('PHIL_AI_OS_MC_PORT', '4881'))
READ_MODEL = os.getenv('PHIL_AI_OS_MC_READ_MODEL', '/tmp/philaios-mission-control-read-model-phase21a.py')

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Phil AI OS Mission Control — Read Only</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#162033}
header{padding:20px 24px;background:#111827;color:#fff;display:flex;justify-content:space-between;align-items:center}
main{padding:20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:#fff;border:1px solid #dbe2ea;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
h2{font-size:16px;margin:0 0 12px}.kv{display:grid;grid-template-columns:1fr auto;gap:8px;margin:6px 0}.muted{color:#667085}.badge{padding:3px 8px;border-radius:999px;background:#eef2f6;font-size:12px}.warn{color:#9a6700}.err{color:#b42318}.ok{color:#067647}ul{padding-left:18px}button{display:none}
footer{padding:0 20px 20px;color:#667085;font-size:12px}
</style>
</head>
<body>
<header><strong>Phil AI OS Mission Control</strong><span class="badge">READ ONLY · Phase 2.1B</span></header>
<main>
<section class="card"><h2>System Health</h2><div id="health">Loading…</div></section>
<section class="card"><h2>Governance</h2><div id="governance">Loading…</div></section>
<section class="card"><h2>Agents</h2><div id="agents">Loading…</div></section>
<section class="card"><h2>Tasks & Approvals</h2><div id="approvals">Loading…</div></section>
<section class="card"><h2>Executions & Audit</h2><div id="executions">Loading…</div></section>
<section class="card"><h2>Recovery & Data Quality</h2><div id="recovery">Loading…</div></section>
</main>
<footer>No mutation controls are present. Existing Control API and Telegram approval mechanisms remain authoritative.</footer>
<script>
const esc=x=>String(x??'unknown').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kv=(k,v)=>`<div class="kv"><span class="muted">${esc(k)}</span><strong>${esc(v)}</strong></div>`;
fetch('/api/read-model',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}).then(d=>{
 document.getElementById('health').innerHTML=kv('Overall',d.overall_state)+kv('Control API',d.platform?.control_api_health)+kv('Readiness',d.platform?.control_api_readiness)+kv('Monitoring',d.platform?.monitoring_state)+kv('Generated',d.generated_at);
 document.getElementById('governance').innerHTML=kv('Allowed classes',(d.governance?.execution_allowed_task_classes||[]).join(', '))+kv('Enforcement',d.governance?.execution_enforcement_mode)+kv('Scope',d.governance?.execution_enforcement_scope)+kv('Kill switch',d.governance?.kill_switch_state)+kv('Authority expansion',d.governance?.authority_expansion_state);
 document.getElementById('agents').innerHTML='<ul>'+(d.agents||[]).map(a=>`<li><strong>${esc(a.display_name)}</strong> — ${esc(a.role)} / ${esc(a.authority_level)} / ${esc(a.status)}</li>`).join('')+'</ul>';
 document.getElementById('approvals').innerHTML=kv('Canonical tasks',(d.tasks||[]).length)+kv('Recent approvals',(d.approvals||[]).length)+kv('Correlation',d.data_quality?.correlation_quality);
 document.getElementById('executions').innerHTML=kv('Recent executions',(d.executions||[]).length)+kv('Direct provider bypass',d.governance?.direct_provider_bypass_allowed);
 document.getElementById('recovery').innerHTML=kv('Backup timer',d.recovery?.backup_timer_state)+kv('Self-heal',d.recovery?.backup_self_heal_state)+kv('Restore validation',d.recovery?.restore_validation_status)+kv('Freshness',d.data_quality?.freshness)+'<ul class="warn">'+(d.data_quality?.warnings||[]).map(w=>`<li>${esc(w)}</li>`).join('')+'</ul>';
}).catch(e=>{document.querySelectorAll('main .card div').forEach(x=>x.innerHTML='<span class="err">Unavailable: '+esc(e.message)+'</span>')});
</script>
</body></html>'''

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type):
        payload = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._send(200, HTML, 'text/html; charset=utf-8')
            return
        if self.path == '/api/read-model':
            p = subprocess.run(['python3', READ_MODEL], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                data = json.loads(p.stdout)
            except Exception:
                data = {'schema_version':'2.1a.v1','overall_state':'unknown','data_quality':{'partial':True,'warnings':['read model unavailable']}}
                p = type('P', (), {'returncode':1})()
            code = 200 if p.returncode == 0 else 503
            self._send(code, json.dumps(data, sort_keys=True), 'application/json; charset=utf-8')
            return
        self._send(404, json.dumps({'status':'not_found'}), 'application/json; charset=utf-8')

    def do_POST(self):
        self._send(405, json.dumps({'status':'read_only','message':'mutation_not_available'}), 'application/json; charset=utf-8')

    def do_PUT(self): self.do_POST()
    def do_PATCH(self): self.do_POST()
    def do_DELETE(self): self.do_POST()

    def log_message(self, fmt, *args):
        pass

if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'PHIL_AI_OS_PHASE_2_1B_READ_ONLY_DASHBOARD_LISTENING host={HOST} port={PORT}', flush=True)
    server.serve_forever()
