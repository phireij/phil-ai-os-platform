"""Offline admission/rate/concurrency/bodyless-logout regressions.

Only mocked HTTPS and in-process WSGI calls. No listener or container is used.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace, FrozenInstanceError
import base64
import hashlib
import json
from pathlib import Path
import re
import threading
import unittest
from unittest.mock import patch

import test_ruby_staging_http_app as support
from ruby_staging_http_app import StagingHTTPApplication, StagingRequestLimits, StagingHTTPConfigurationError
from ruby_staging_lifecycle import SESSION_COOKIE

ORIGIN=support.ORIGIN
LIMITS=support.LIMITS


class UnreadableInput:
    def __init__(self):self.read_count=0
    def read(self,*_args):
        self.read_count+=1
        raise AssertionError("request_body_must_not_be_read")


class RuntimeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.HTTPApplicationTests.setUpClass()
        cls.key=support.HTTPApplicationTests.key
        cls.signer=support.HTTPApplicationTests.signer

    def csrf(self,a,cookie):
        status,_,body=self.call(a,"/api/session",cookie=cookie)
        self.assertEqual(status,200);return json.loads(body)["csrf_token"]

    def logout(self,a,cookie,csrf,**changes):
        return self.call(a,"/auth/logout",method="POST",cookie=cookie,
            HTTP_ORIGIN=ORIGIN,HTTP_X_CSRF_TOKEN=csrf,**changes)

    def blocked_auth(self,a,flow,cookie,probe):
        entered=threading.Event();release=threading.Event();original=a._authenticator.authenticate
        def authenticate(**kw):
            entered.set()
            if not release.wait(5):raise AssertionError("test_release_missing")
            return original(**kw)
        with ThreadPoolExecutor(max_workers=4) as pool, patch.object(a._authenticator,"authenticate",side_effect=authenticate):
            pending=pool.submit(self.callback,a,flow,cookie)
            try:
                self.assertTrue(entered.wait(2))
                result=pool.submit(probe).result(timeout=2)
            finally:
                release.set()
            callback=pending.result(timeout=3)
        return result,callback

    def test_explicit_frozen_limits_required_and_bounded(self):
        for value in (None,object(),{"max_inflight_requests":1}):
            with self.assertRaises(StagingHTTPConfigurationError):self.make(auth=None,limits=value)
        for name,bad in (("max_inflight_requests",0),("max_inflight_requests",65),("max_inflight_requests",True),
                         ("max_login_starts",0),("max_login_starts",1025),("max_callback_attempts",0),
                         ("max_callback_attempts",1025),("window_seconds",0),("window_seconds",3601),
                         ("window_seconds",float("nan"))):
            with self.assertRaises(StagingHTTPConfigurationError):self.make(auth=None,limits=replace(LIMITS,**{name:bad}))
        with self.assertRaises(FrozenInstanceError):LIMITS.window_seconds=3

    def test_global_login_start_budget_bounds_state_and_resets_at_window(self):
        a=self.make(limits=StagingRequestLimits(4,2,4,10))
        self.start(a);self.start(a)
        self.assertEqual(self.call(a,"/auth/google/start")[0],429)
        self.assertEqual(len(a._login_starts),2);self.assertEqual(len(a._flows._flows),2)
        self.mono+=10;self.start(a)
        self.assertEqual(len(a._login_starts),1);self.assertEqual(len(a._flows._flows),1)
        self.assertEqual(self.sent,[])

    def test_callback_rate_rejection_consumes_admitted_pending_flow(self):
        a=self.make(limits=StagingRequestLimits(4,8,2,10))
        for _ in range(2):
            self.assertEqual(self.call(a,"/auth/google/callback",query="state="+"X"*64+"&code=x")[0],401)
        flow,cookie=self.start(a)
        status,headers,_=self.callback(a,flow,cookie)
        self.assertEqual(status,429);self.assert_clear(headers)
        self.assertEqual(len(a._flows._flows),0);self.assertEqual(len(a._callback_attempts),2)
        self.assertEqual(self.sent,[])
        self.mono+=10
        self.assertEqual(self.callback(a,flow,cookie)[0],401)

    def test_slow_upstream_does_not_block_existing_owner_reads(self):
        a=self.make();session,_,_,_=self.login(a)
        flow,cookie=self.start(a);self.queue(flow,cert=False)
        read,callback=self.blocked_auth(a,flow,cookie+"; "+session,
            lambda:self.call(a,"/api/ruby-review-synthetic",cookie=session))
        self.assertEqual(read[0],200);self.assertEqual(callback[0],303)
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],401)

    def test_second_authentication_fails_fast_consumes_flow_and_never_queues(self):
        a=self.make();flow,cookie=self.start(a);self.queue(flow)
        other={}
        def probe():
            f,c=self.start(a);other.update(flow=f,cookie=c)
            return self.callback(a,f,c)
        busy,completed=self.blocked_auth(a,flow,cookie,probe)
        self.assertEqual(busy[0],503);self.assertEqual(json.loads(busy[2])["error"],"authentication_busy")
        self.assert_clear(busy[1]);self.assertEqual(completed[0],303)
        self.assertEqual(self.callback(a,other["flow"],other["cookie"])[0],401)
        self.assertEqual(len(self.sent),2)

    def test_logout_during_authentication_prevents_late_session_issuance(self):
        a=self.make();session,_,_,_=self.login(a);csrf=self.csrf(a,session)
        flow,cookie=self.start(a);self.queue(flow,cert=False)
        pending_flow,pending_cookie=self.start(a)
        logout,callback=self.blocked_auth(a,flow,cookie+"; "+session,lambda:self.logout(a,session,csrf))
        self.assertEqual(logout[0],200);self.assertEqual(callback[0],503)
        self.assertFalse(any(k=="Set-Cookie" and v.startswith(SESSION_COOKIE+"=") for k,v in callback[1]))
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],401)
        self.assertEqual(self.callback(a,pending_flow,pending_cookie)[0],401)
        self.assertEqual(len(a._sessions._sessions),0)
        fresh,_,_,_=self.login(a,cert=False)
        self.assertEqual(self.call(a,"/api/session",cookie=fresh)[0],200)

    def test_close_during_authentication_revokes_without_waiting_and_defers_cleanup(self):
        a=self.make();session,_,_,_=self.login(a);flow,cookie=self.start(a);self.queue(flow,cert=False)
        def probe():
            a.close()
            return a._closed,a._sessions._closed,a._authenticator._closed,self.call(a,"/healthz")[0]
        state,callback=self.blocked_auth(a,flow,cookie,probe)
        self.assertEqual(state,(True,True,False,503))
        self.assertEqual(callback[0],503);self.assertTrue(a._authenticator._closed)
        self.assertEqual(len(a._sessions._sessions),0)
        self.assertFalse(a._auth_slot.locked())

    def test_clock_failure_during_upstream_closes_without_waiting(self):
        a=self.make();session,_,_,_=self.login(a);flow,cookie=self.start(a);self.queue(flow,cert=False)
        def probe():
            self.mono-=1
            return self.call(a,"/api/session",cookie=session)
        failed,callback=self.blocked_auth(a,flow,cookie,probe)
        self.assertEqual(failed[0],503);self.assertEqual(callback[0],503)
        self.assertTrue(a._closed);self.assertTrue(a._authenticator._closed)
        self.assertEqual(len(a._login_starts),0);self.assertEqual(len(a._callback_attempts),0)

    def test_request_admission_rejects_without_waiting_for_server_response_hook(self):
        a=self.make(auth=None,limits=StagingRequestLimits(1,2,2,10))
        entered=threading.Event();release=threading.Event()
        def slow_response(_status,_headers):
            entered.set()
            if not release.wait(5):raise AssertionError("test_release_missing")
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending=pool.submit(a,self.environ("/healthz"),slow_response)
            try:
                self.assertTrue(entered.wait(2))
                status,_,body=pool.submit(self.call,a,"/healthz").result(timeout=2)
                self.assertEqual(status,503);self.assertEqual(json.loads(body)["error"],"request_capacity_reached")
            finally:release.set()
            pending.result(timeout=3)
        self.assertEqual(self.call(a,"/healthz")[0],200)

    def test_server_response_hook_does_not_hold_application_state_lock(self):
        a=self.make(auth=None,limits=StagingRequestLimits(2,2,2,10))
        entered=threading.Event();release=threading.Event()
        def slow_response(_status,_headers):
            entered.set();release.wait(5)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending=pool.submit(a,self.environ("/healthz"),slow_response)
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(pool.submit(self.call,a,"/healthz").result(timeout=2)[0],200)
            finally:release.set()
            pending.result(timeout=3)

    def test_start_response_exception_releases_request_admission(self):
        a=self.make(auth=None,limits=StagingRequestLimits(1,2,2,10))
        def broken(*_args):raise RuntimeError("server_hook_failure")
        with self.assertRaises(RuntimeError):a(self.environ("/healthz"),broken)
        self.assertEqual(self.call(a,"/healthz")[0],200)

    def test_unexpected_authenticator_failure_releases_both_slots(self):
        a=self.make();flow,cookie=self.start(a)
        with patch.object(a._authenticator,"authenticate",side_effect=RuntimeError("SECRET_UPSTREAM")):
            status,headers,body=self.callback(a,flow,cookie)
        self.assertEqual(status,503);self.assert_clear(headers);self.assertNotIn("SECRET",body.decode())
        self.assertFalse(a._auth_slot.locked())
        session,_,_,_=self.login(a)
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],200)

    def test_outer_admission_callback_is_unprocessed_but_flow_cookie_is_cleared(self):
        a=self.make(limits=StagingRequestLimits(1,4,4,60));flow,cookie=self.start(a)
        self.assertTrue(a._admission.acquire(blocking=False))
        try:
            status,headers,_=self.callback(a,flow,cookie)
            self.assertEqual(status,503);self.assert_clear(headers)
            self.assertEqual(len(a._callback_attempts),0);self.assertEqual(len(a._flows._flows),1)
            self.assertEqual(self.sent,[])
        finally:a._admission.release()

    def test_bodyless_logout_never_touches_wsgi_input(self):
        a=self.make();session,_,_,_=self.login(a);csrf=self.csrf(a,session);body=UnreadableInput()
        status,_,_=self.logout(a,session,csrf,**{"wsgi.input":body})
        self.assertEqual(status,200);self.assertEqual(body.read_count,0)

    def test_all_routes_and_rejected_framing_leave_request_stream_unread(self):
        a=self.make();session,_,_,_=self.login(a);csrf=self.csrf(a,session)
        for length in ("1","99999999","00","+0","-0"," 0","0,0"):
            body=UnreadableInput()
            self.assertEqual(self.logout(a,session,csrf,CONTENT_LENGTH=length,**{"wsgi.input":body})[0],400)
            self.assertEqual(body.read_count,0)
        for path,changes in (("/api/session",{}),("/healthz",{}),("/unknown",{}),
                             ("/auth/google/callback",{"query":"state=x&code=y"})):
            body=UnreadableInput();self.call(a,path,cookie=session,**{"wsgi.input":body},**changes)
            self.assertEqual(body.read_count,0)
        body=UnreadableInput()
        self.assertEqual(self.logout(a,session,csrf,CONTENT_TYPE="application/x-www-form-urlencoded",**{"wsgi.input":body})[0],403)
        self.assertEqual(body.read_count,0)

    def test_header_csrf_duplicates_and_failures_do_not_refresh_idle(self):
        a=self.make();session,_,_,_=self.login(a);csrf=self.csrf(a,session)
        self.mono+=5
        self.assertEqual(self.logout(a,session,csrf+","+csrf)[0],401)
        self.assertEqual(self.logout(a,session,"wrong")[0],401)
        self.mono+=5
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],401)

    def test_csp_hash_matches_exact_fixed_bodyless_logout_script(self):
        a=self.make();session,_,_,_=self.login(a)
        status,headers,body=self.call(a,"/",cookie=session);self.assertEqual(status,200)
        text=body.decode();script=re.search(r"<script>(.*?)</script>",text,re.S).group(1)
        digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        csp=dict(headers)["Content-Security-Policy"]
        self.assertIn("script-src 'sha256-"+digest+"'",csp)
        self.assertIn("connect-src 'self'",csp);self.assertIn("form-action 'none'",csp)
        self.assertNotIn("unsafe-inline",csp);self.assertNotIn("<form",text)
        self.assertIn("method:'POST'",script);self.assertIn("credentials:'same-origin'",script)
        self.assertIn("redirect:'error'",script);self.assertIn("'X-CSRF-Token'",script)
        self.assertNotIn("body:",script)
        token=re.search(r'id="logout-csrf"[^>]*value="([^"]+)"',text).group(1)
        self.assertNotIn(token,script);self.assertEqual(len(token),64)

    def test_image_pin_matches_verified_core_platform_lineage(self):
        source=(Path(__file__).resolve().parents[2]/"Dockerfile.ruby-staging-review").read_text()
        self.assertIn("FROM --platform=linux/amd64 python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8",source)
        self.assertNotIn("EXPOSE ",source);self.assertNotIn("VOLUME ",source)
        self.assertIn('ENTRYPOINT ["python3", "/srv/ruby_staging_http_app.py"]',source)

    def test_image_context_allowlist_names_only_runtime_source_and_recipe(self):
        root=Path(__file__).resolve().parents[2]
        lines=(root/"Dockerfile.ruby-staging-review.dockerignore").read_text().splitlines()
        rules=[line for line in lines if line and not line.startswith("#")]
        self.assertEqual(rules[:5],["**","!ops/","ops/**","!ops/mission-control-identity/","ops/mission-control-identity/**"])
        allowed={line[1:] for line in rules[5:]}
        copies={line.split()[1] for line in (root/"Dockerfile.ruby-staging-review").read_text().splitlines() if line.startswith("COPY ")}
        self.assertEqual(allowed,copies|{"Dockerfile.ruby-staging-review","Dockerfile.ruby-staging-review.dockerignore"})


for _name in ("setUp","send","make_auth","make","environ","call","start","token","response","queue","callback","login","assert_clear"):
    setattr(RuntimeBoundaryTests,_name,getattr(support.HTTPApplicationTests,_name))


if __name__=="__main__":unittest.main(verbosity=2)
