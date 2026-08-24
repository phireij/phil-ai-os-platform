#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, tempfile, time
from pathlib import Path

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def quick_check(path: Path):
    con=sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        qc=con.execute('PRAGMA quick_check').fetchone()[0]
        tables=con.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]
        return qc,tables
    finally: con.close()

def backup(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(src)) as s, sqlite3.connect(str(dst)) as d:
        s.backup(d)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--backup-dir', required=True)
    p.add_argument('--status-file', required=True)
    p.add_argument('--label', default='scheduled')
    args=p.parse_args()
    src=Path(args.source); outdir=Path(args.backup_dir); status=Path(args.status_file)
    if not src.is_file(): raise SystemExit(f'source_missing:{src}')
    ts=time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    final=outdir/f'control-plane-{ts}-{args.label}.db'
    tmp=outdir/f'.{final.name}.tmp'
    outdir.mkdir(parents=True, exist_ok=True)
    if tmp.exists(): tmp.unlink()
    started=int(time.time())
    try:
        backup(src,tmp)
        qc,tables=quick_check(tmp)
        if qc!='ok': raise RuntimeError(f'quick_check={qc}')
        digest=sha256(tmp)
        size=tmp.stat().st_size
        os.replace(tmp,final)
        payload={'ok':True,'timestamp':ts,'backup':str(final),'sha256':digest,'size_bytes':size,'tables':tables,'quick_check':qc,'source':str(src),'label':args.label,'duration_seconds':int(time.time())-started}
    except Exception as exc:
        if tmp.exists(): tmp.unlink()
        payload={'ok':False,'timestamp':ts,'source':str(src),'label':args.label,'error':f'{type(exc).__name__}:{exc}','duration_seconds':int(time.time())-started}
        status.parent.mkdir(parents=True, exist_ok=True); status.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
        print(json.dumps(payload,sort_keys=True))
        return 1
    status.parent.mkdir(parents=True, exist_ok=True); status.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps(payload,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
