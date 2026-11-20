"""Synthetic #834 backend replacement check. No runtime mutation outside a temp directory."""
import argparse
import contextlib
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

CONV = "conv_0000000000000001"
IDS = [f"message_{i:016d}" for i in range(205)]
COOKIE = "__Host-mc-ceo-session"
BLOBS = {
    "candidate": ("ce219aaec1d4f3fa20d383494c38ee22ce88cfcc", "e212a037059c8e50c763e5a93a80219f16c0c032"),
    "baseline": ("38a995697c8ac936b33c713d389d760ae83cf4fd", "e9583b8029b301eccb4bc43434350b5933baeaf7"),
}

def readout(root):
    return tuple(hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ("state", "ledger"))

def worker(mode, source, root, port):
    for name, expected in zip(("google_ceo_session", "conversation_store"), BLOBS[mode]):
        raw = (source / (name + ".py")).read_bytes()
        assert hashlib.sha1(f"blob {len(raw)}\0".encode()+raw, usedforsecurity=False).hexdigest() == expected
    sys.path.insert(0, str(source))
    from google_ceo_session import SESSION_COOKIE, SessionHandler, SessionStore
    from conversation_store import ConversationConfig, ConversationStore
    assert SESSION_COOKIE == COOKIE
    store = ConversationStore(ConversationConfig(root / "state", root / "ledger", root / "key"),
                              "https://accounts.google.com", "synthetic-rollback-owner")
    class QuietHandler(SessionHandler):
        def log_message(self, *args):
            pass
    try:
        if mode == "candidate":
            now = int(time.time())
            store._live.connection.execute("INSERT INTO conversations VALUES (?,?,?,?)",(CONV,store._owner,now,now))
            for mid in IDS[::2]+IDS[1::2][::-1]:
                store._live.connection.execute("INSERT INTO messages VALUES (?,?,'ceo',?,?)", (mid, CONV, f"Synthetic rollback row {int(mid[-16:]):03d}", now))
            store._live.persist()
        # Deliberately inspect the full decrypted synthetic store independently of pagination.
        actual = store._live.connection.execute("SELECT message_id FROM messages WHERE conversation_id=? ORDER BY message_id",(CONV,)).fetchall()
        assert [r[0] for r in actual] == IDS
        with ThreadingHTTPServer(("127.0.0.1", port), QuietHandler) as server:
            server.sessions = SessionStore()
            server.conversations = store
            server.ruby_review_synthetic_surface_enabled = False
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                print(json.dumps({"port": server.server_port}), flush=True)
                for line in sys.stdin:
                    if line.strip() == "logical":
                        logical = [hashlib.sha256("\n".join(snapshot.connection.iterdump()).encode()).hexdigest()
                                   for snapshot in (store._live, store._ledger)]
                        print(json.dumps({"logical": logical}), flush=True)
                        continue
                    assert line.strip()=="issue"
                    token, _ = server.sessions.issue()
                    # Synthetic token remains in private IPC pipe, never printed by parent.
                    print(json.dumps({"cookie": token}), flush=True)
            finally:
                server.shutdown()
                thread.join(5)
    finally:
        store.close()

def recv(p):
    assert select.select([p.stdout], [], [], 10)[0], "worker response timeout"
    return json.loads(p.stdout.readline())

def ask(p, command, key):
    p.stdin.write(command + "\n")
    p.stdin.flush()
    return recv(p)[key]

def issue(p):
    return ask(p, "issue", "cookie")

@contextlib.contextmanager
def process(mode, path, root, port=0):
    with subprocess.Popen([sys.executable,"-B", __file__,"--worker",mode,str(path),str(root),str(port)],
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True) as p:
        try:
            yield p, recv(p)["port"]
        finally:
            p.stdin.close()
            try:
                assert p.wait(timeout=8)==0, "worker exited nonzero"
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
                raise

def fetch(port,path,cookie):
    c = http.client.HTTPConnection("127.0.0.1",port,timeout=5)
    try:
        c.request("GET",path,headers={"Host":"miscon.phireij.cloud","Cookie":f"{COOKIE}={cookie}"})
        r = c.getresponse()
        return r.status,json.loads(r.read())
    finally:
        c.close()

def ids(page):
    return [row["message_id"] for row in page["messages"]]

def main(candidate, baseline):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "key").write_text("47"*32)
        (root / "key").chmod(0o600)
        resource=f"/api/conversations/{CONV}/messages"
        optin=f"{resource}?pagination=keyset-v1&limit=100"
        with process("candidate", candidate, root) as (p,port):
            old=issue(p)
            code,session=fetch(port,"/auth/google/session",old)
            assert code==200 and session["message_history_pagination"]=="keyset-v1"
            code,page=fetch(port,optin,old)
            assert code==200 and ids(page)==IDS[-100:]
            prior=readout(root)
            prior_logical=ask(p,"logical","logical")
            assert page["next_cursor"]
            stale=optin+"&"+urllib.parse.urlencode({"cursor":page["next_cursor"]})
            code,page=fetch(port,stale,old)
            assert code==200 and ids(page)==IDS[5:105]
            print("PASS candidate capability and cached earlier query")
            assert readout(root)==prior
        with process("baseline",baseline,root,port) as (p,restored_port):
            assert restored_port==port
            baseline_boot=readout(root)
            assert fetch(port,stale,old)==(401,{"error":"unauthorized"})
            assert fetch(port,"/auth/google/session",old)[0]==401
            print("PASS same origin/backend replaced: old session and stale query rejected with 401")
            new=issue(p)
            code,session=fetch(port,"/auth/google/session",new)
            assert code==200 and "message_history_pagination" not in session
            code,page=fetch(port,resource+"?limit=100",new)
            assert code==200 and ids(page)==IDS[:100] and page["next_cursor"] is None
            print("PASS new synthetic session and legacy limit-only oldest 100")
            assert fetch(port,stale,new)==(400,{"error":"invalid_query"})
            print("PASS conditional valid-session stale-query contract is 400 invalid_query (not ordinary restart)")
            assert ask(p,"logical","logical")==prior_logical
            assert readout(root)==baseline_boot
        assert readout(root)==baseline_boot
        print("PASS all 205 rows and logical database/ledger contents preserved; HTTP reads caused no encrypted writes")
        print("NOTE encrypted files refreshed at startup by normal reopen, not byte-identical across restart")

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--worker":
        worker(sys.argv[2],Path(sys.argv[3]),Path(sys.argv[4]),int(sys.argv[5]))
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument("candidate",type=Path)
        parser.add_argument("baseline",type=Path)
        args=parser.parse_args()
        main(args.candidate.resolve(),args.baseline.resolve())
