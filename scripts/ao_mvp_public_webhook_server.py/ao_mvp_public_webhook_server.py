import hashlib,hmac,json,os,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
MAX=16384; FRESH=300; WINDOW=60; LIMIT=30
SECRET=os.environ.get('AO_MVP_PUBLIC_WEBHOOK_SECRET')
if not SECRET: raise SystemExit('AO_MVP_PUBLIC_WEBHOOK_SECRET is required')
seen={}; hits={}; lock=threading.Lock()
def audit(event,**kw):
    print(json.dumps({'event':event,**{k:v for k,v in kw.items() if k in {'path','status','reason','event_type'}}},sort_keys=True),flush=True)
def reject(h,code,reason):
    audit('webhook_rejected',path=h.path,status=code,reason=reason); b=json.dumps({'accepted':False,'reason':reason}).encode(); h.send_response(code); h.send_header('Content-Type','application/json'); h.send_header('Content-Length',str(len(b))); h.end_headers(); h.wfile.write(b)
class Handler(BaseHTTPRequestHandler):
    server_version='ao-mvp-public-webhook/1'
    def log_message(self,*args): return
    def do_GET(self):
        if self.path!='/healthz': return reject(self,404,'not_found')
        b=b'{"status":"ok","mode":"synthetic_only"}'; self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        if self.path!='/webhook': return reject(self,404,'not_found')
        try: n=int(self.headers.get('Content-Length','-1'))
        except ValueError: n=-1
        if n<0 or n>MAX: return reject(self,413,'body_too_large')
        if self.headers.get('Content-Type','').split(';',1)[0].lower()!='application/json': return reject(self,415,'unsupported_content_type')
        raw=self.rfile.read(n)
        if len(raw)!=n: return reject(self,400,'incomplete_body')
        ts=self.headers.get('X-AO-Timestamp',''); nonce=self.headers.get('X-AO-Nonce',''); sig=self.headers.get('X-AO-Signature','')
        try: age=abs(int(time.time())-int(ts))
        except ValueError: return reject(self,401,'invalid_timestamp')
        if age>FRESH: return reject(self,401,'stale_request')
        if not nonce or len(nonce)>128: return reject(self,401,'invalid_nonce')
        expected='sha256='+hmac.new(SECRET.encode(),(ts+'.'+nonce+'.').encode()+raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,sig): return reject(self,401,'invalid_signature')
        with lock:
            now=time.time()
            if nonce in seen: return reject(self,409,'replay_rejected')
            seen[nonce]=now; ip=self.client_address[0]; recent=[x for x in hits.get(ip,[]) if now-x<WINDOW]
            if len(recent)>=LIMIT: hits[ip]=recent; return reject(self,429,'rate_limited')
            recent.append(now); hits[ip]=recent
            for k,v in list(seen.items()):
                if now-v>FRESH: del seen[k]
        try: payload=json.loads(raw)
        except json.JSONDecodeError: return reject(self,400,'malformed_json')
        if not isinstance(payload,dict) or set(payload)!={'event_type','canary_id'} or payload.get('event_type')!='synthetic_canary' or not isinstance(payload.get('canary_id'),str) or not payload['canary_id']: return reject(self,422,'unsupported_event')
        audit('webhook_accepted',path=self.path,status=202,event_type='synthetic_canary'); b=b'{"accepted":true,"event_type":"synthetic_canary"}'; self.send_response(202); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
if __name__=='__main__':
    server=ThreadingHTTPServer((os.environ.get('AO_MVP_PUBLIC_WEBHOOK_BIND','0.0.0.0'),int(os.environ.get('AO_MVP_PUBLIC_WEBHOOK_PORT','8080'))),Handler); audit('webhook_started',path='/webhook',status=200); server.serve_forever()
