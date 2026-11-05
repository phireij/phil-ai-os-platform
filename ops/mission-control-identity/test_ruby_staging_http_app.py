"""In-process WSGI tests using the genuine backend with mocked HTTP sends.

No WSGI/HTTP listener is started. Backend fixture imports deny sockets and DNS
before implementation imports. Ephemeral keys and secret strings are synthetic.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import formatdate
import inspect
import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode

import requests
import test_ruby_staging_google_auth as fixtures
from google.auth import jwt

import ruby_staging_http_app as app_module
from ruby_staging_http_app import StagingHTTPApplication, StagingHTTPConfig, StagingHTTPConfigurationError, StagingRequestLimits
from ruby_staging_google_auth import StagingGoogleOwnerAuthenticator, TOKEN_URL, CERTIFICATE_URL
from ruby_staging_lifecycle import SESSION_COOKIE, FLOW_COOKIE, SessionStore, LifecycleError, pkce_challenge

NOW=fixtures.NOW
ORIGIN=fixtures.ORIGIN
CLIENT=fixtures.CLIENT
OWNER=fixtures.OWNER
CONFIG=StagingHTTPConfig(ORIGIN,CLIENT,OWNER,5,10,30,32)
LIMITS=StagingRequestLimits(16,128,128,60)


class HTTPApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StagingGoogleAuthenticatorTests.setUpClass()
        cls.key=fixtures.StagingGoogleAuthenticatorTests.key
        cls.signer=fixtures.StagingGoogleAuthenticatorTests.signer

    def setUp(self):
        self.wall=NOW;self.mono=100.0;self.replies=[];self.sent=[];self.apps=[];self.auths=[]
        self.addCleanup(lambda:[a.close() for a in self.apps])
        self.addCleanup(lambda:[a.close() for a in self.auths])
        for p in (patch.object(requests.Session,"send",autospec=True,side_effect=self.send),
                  patch("google.auth._helpers.utcnow",side_effect=lambda:datetime.fromtimestamp(self.wall,timezone.utc).replace(tzinfo=None))):
            p.start();self.addCleanup(p.stop)

    def send(self,session,request,**kwargs):
        self.sent.append((session,request,kwargs))
        if not self.replies:raise AssertionError("unexpected_http_request")
        r=self.replies.pop(0)
        if isinstance(r,Exception):raise r
        r.request=request;return r

    def make_auth(self,**changes):
        d=dict(origin=ORIGIN,client_id=CLIENT,owner_subject=OWNER,client_secret=fixtures.SECRET,
               max_cache_seconds=300,enabled=True,clock=lambda:self.wall)
        d.update(changes);a=StagingGoogleOwnerAuthenticator(**d);self.auths.append(a);return a

    def make(self,auth="default",**changes):
        if auth=="default":auth=self.make_auth()
        opts=dict(config=CONFIG,enabled=True,authenticator=auth,limits=LIMITS,clock=lambda:self.mono)
        opts.update(changes);app=StagingHTTPApplication(**opts);self.apps.append(app);return app

    def environ(self,path="/",method="GET",query="",cookie="",body=b"",**changes):
        env={"REQUEST_METHOD":method,"PATH_INFO":path,"QUERY_STRING":query,"SCRIPT_NAME":"",
             "wsgi.url_scheme":"https","wsgi.input":io.BytesIO(body),"wsgi.errors":io.StringIO(),
             "wsgi.version":(1,0),"wsgi.multithread":True,"wsgi.multiprocess":False,
             "wsgi.run_once":False,"HTTP_HOST":ORIGIN[8:]}
        if cookie:env["HTTP_COOKIE"]=cookie
        if method=="POST":env.update(CONTENT_LENGTH=str(len(body)),CONTENT_TYPE="")
        env.update(changes);return env

    def call(self,app,path="/",**kw):
        env=self.environ(path,**kw);got=[]
        body=b"".join(app(env,lambda status,headers:got.append((status,headers))))
        self.assertEqual(len(got),1);self.assertEqual(env["wsgi.errors"].getvalue(),"")
        status,headers=got[0]
        self.assertEqual(dict(headers)["Content-Length"],str(len(body)))
        self.assertEqual(dict(headers)["Cache-Control"],"no-store")
        self.assertEqual(dict(headers)["Referrer-Policy"],"no-referrer")
        self.assertNotIn("Access-Control-Allow-Origin",dict(headers))
        return int(status.split()[0]),headers,body

    def start(self,app):
        status,headers,_=self.call(app,"/auth/google/start")
        self.assertEqual(status,303)
        location=dict(headers)["Location"];p=urlsplit(location)
        self.assertEqual(p.scheme+"://"+p.netloc+p.path,app_module.AUTHORIZATION_URL)
        values={k:v[0] for k,v in parse_qs(p.query).items()}
        cookie=next(v.split(";",1)[0] for k,v in headers if k=="Set-Cookie")
        return values,cookie

    def token(self,nonce="N"*64,**changes):
        p=dict(iss="https://accounts.google.com",aud=CLIENT,sub=OWNER,nonce=nonce,iat=NOW-1,exp=NOW+3600)
        p.update(changes);return jwt.encode(self.signer,p).decode("ascii")

    def response(self,url,body,headers=None,status=200):
        r=requests.Response();r.status_code=status;r.url=url
        r.raw=fixtures.Raw(body,headers or [("Content-Type","application/json")]);return r

    def queue(self,flow,cert=True,**claims):
        token=self.token(claims.pop("nonce", flow["nonce"]),**claims)
        self.replies.append(self.response(TOKEN_URL,json.dumps({"id_token":token,"token_type":"Bearer"}).encode()))
        if cert:
            pem=fixtures.StagingGoogleAuthenticatorTests.cert(self)
            self.replies.append(self.response(CERTIFICATE_URL,json.dumps({"synthetic-cert":pem}).encode(),
                [("Content-Type","application/json"),("Cache-Control","public, max-age=300"),("Date",formatdate(self.wall,usegmt=True))]))

    def callback(self,app,flow,cookie,query=None,**kw):
        return self.call(app,"/auth/google/callback",query=query if query is not None else urlencode({"state":flow["state"],"code":"synthetic-code"}),cookie=cookie,**kw)

    def login(self,app,*,cert=True,previous=""):
        flow,cookie=self.start(app);self.queue(flow,cert=cert)
        if previous:cookie+="; "+previous
        status,headers,body=self.callback(app,flow,cookie);self.assertEqual(status,303)
        self.assertEqual(dict(headers)["Location"],"/")
        session=next(v.split(";",1)[0] for k,v in headers if k=="Set-Cookie" and v.startswith(SESSION_COOKIE+"="))
        return session,flow,cookie,headers

    def assert_clear(self,headers):
        self.assertTrue(any(k=="Set-Cookie" and v.startswith(FLOW_COOKIE+"=;") and "Max-Age=0" in v for k,v in headers))

    def test_default_off_is_inactive_without_session_construction(self):
        with patch.object(requests,"Session") as session:
            a=StagingHTTPApplication();self.apps.append(a)
            self.assertEqual(self.call(a)[0],503);self.assertEqual(self.call(app_module.application,"/healthz")[0],503)
            self.assertEqual(self.call(a,"/auth/google/callback")[0],503);session.assert_not_called()

    def test_explicit_policy_and_authenticator_type_are_required(self):
        for changes in ({"enabled":1},{"config":None},{"config":replace(CONFIG,origin=app_module.PRODUCTION_ORIGIN)},
                        {"config":replace(CONFIG,client_id=app_module.PRODUCTION_CLIENT_ID)},
                        {"config":replace(CONFIG,flow_seconds=True)},{"config":replace(CONFIG,idle_seconds=31)},
                        {"config":replace(CONFIG,origin="https://"+"a"*64+".test")}):
            with self.assertRaises(StagingHTTPConfigurationError):self.make(auth=None,**changes)
        for auth in (object(),lambda:True,self.make_auth(owner_subject="other")):
            with self.assertRaises(StagingHTTPConfigurationError):self.make(auth=auth)

    def test_enabled_without_backend_health_only_and_no_auth_start(self):
        a=self.make(auth=None)
        status,_,body=self.call(a,"/healthz");self.assertEqual(status,200)
        self.assertFalse(json.loads(body)["authentication_configured"])
        self.assertEqual(self.call(a,"/auth/google/start")[0],503)
        self.assertEqual(self.call(a,"/api/session")[0],401);self.assertEqual(self.sent,[])

    def test_real_backend_route_flow_signature_session_read_and_csrf(self):
        a=self.make();session,flow,_,headers=self.login(a)
        self.assert_clear(headers)
        self.assertEqual(flow["scope"],"openid");self.assertEqual(flow["response_type"],"code")
        self.assertEqual(flow["redirect_uri"],CONFIG.callback)
        self.assertEqual(flow["code_challenge_method"],"S256")
        post=self.sent[0][1];data=parse_qs(post.body)
        self.assertEqual(pkce_challenge(data["code_verifier"][0]),flow["code_challenge"])
        self.assertEqual(data["code"],["synthetic-code"])
        status,_,body=self.call(a,"/api/ruby-review-synthetic",cookie=session)
        self.assertEqual(status,200);payload=json.loads(body)
        self.assertEqual(len(payload["records"]),1);self.assertEqual(payload["authority"],"none")
        self.assertFalse(payload["execution_authorized"]);self.assertFalse(payload["mutation_authorized"])
        status,_,body=self.call(a,"/api/session",cookie=session)
        self.assertEqual(status,200);csrf=json.loads(body)["csrf_token"];self.assertEqual(len(csrf),64)
        status,headers,_=self.call(a,"/auth/logout",method="POST",cookie=session,
            HTTP_X_CSRF_TOKEN=csrf,HTTP_ORIGIN=ORIGIN)
        self.assertEqual(status,200);self.assertNotIn("Location",dict(headers))
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],401)

    def test_cookie_flags_response_security_and_no_identity_leak(self):
        a=self.make();session,flow,_,headers=self.login(a)
        for k,v in headers:
            if k=="Set-Cookie":
                for flag in ("Path=/","Secure","HttpOnly","SameSite=Lax"):self.assertIn(flag,v)
                self.assertNotIn("Domain=",v)
        _,hs,body=self.call(a,"/",cookie=session)
        self.assertIn("default-src 'none'",dict(hs)["Content-Security-Policy"])
        self.assertIn("form-action 'none'",dict(hs)["Content-Security-Policy"])
        for value in (OWNER,CLIENT,fixtures.SECRET,flow["nonce"],"synthetic-code"):
            self.assertNotIn(value,body.decode())
        self.assertIn("csrf_token",body.decode())

    def test_scheme_host_proxy_auth_multiprocess_headers_reject_before_transport(self):
        cases=[{"wsgi.url_scheme":"http"},{"HTTP_HOST":"evil.example"},{"HTTP_HOST":ORIGIN[8:]+",evil.example"},
               {"HTTP_HOST":ORIGIN[8:]+":443"},{"HTTP_FORWARDED":"proto=https"},
               {"HTTP_X_FORWARDED_PROTO":"https"},{"HTTP_X_FORWARDED_HOST":ORIGIN[8:]},
               {"HTTP_AUTHORIZATION":"Bearer SECRET"},{"HTTP_X_OWNER_SUBJECT":OWNER},
               {"wsgi.multiprocess":True},{"SCRIPT_NAME":"/mounted"},{"HTTP_ORIGIN":"null"},
               {"HTTP_ORIGIN":"https://foreign.test"},{"HTTP_USER_AGENT":"bad\n"},
               {"HTTP_USER_AGENT":"x"*17000}]
        a=self.make()
        for kw in cases:self.assertEqual(self.call(a,"/auth/google/start",**kw)[0],400)
        self.assertEqual(self.sent,[])

    def test_required_wsgi_lifecycle_metadata_must_be_explicit(self):
        a=self.make(auth=None)
        for missing in ("wsgi.version","wsgi.multithread","wsgi.multiprocess","wsgi.run_once"):
            env=self.environ("/healthz");env.pop(missing);received=[]
            body=b"".join(a(env,lambda status,headers:received.append(status)))
            self.assertEqual(received,["400 Bad Request"])
            self.assertEqual(json.loads(body)["error"],"request_invalid")
        # Empty CGI SCRIPT_NAME may legitimately be omitted; do not add an
        # unrelated deployment restriction while fixing required WSGI fields.
        env=self.environ("/healthz");env.pop("SCRIPT_NAME");received=[]
        list(a(env,lambda status,headers:received.append(status)))
        self.assertEqual(received,["200 OK"])
        self.assertEqual(self.sent,[])

    def test_standard_gpc_header_allows_normal_signed_owner_lifecycle(self):
        a=self.make();original=self.environ
        def with_gpc(*args,**kwargs):
            return original(*args,**{"HTTP_SEC_GPC":"1",**kwargs})
        with patch.object(self,"environ",side_effect=with_gpc):
            self.assertEqual(self.call(a)[0],200)
            self.assertEqual(self.call(a,"/api/session")[0],401)
            session,_,_,_=self.login(a)
            status,_,body=self.call(a,"/api/ruby-review-synthetic",cookie=session)
            self.assertEqual(status,200);payload=json.loads(body)
            self.assertEqual(payload["authority"],"none")
            self.assertFalse(payload["execution_authorized"])
            self.assertFalse(payload["mutation_authorized"])
            status,_,body=self.call(a,"/api/session",cookie=session)
            self.assertEqual(status,200);csrf=json.loads(body)["csrf_token"]
            self.assertEqual(self.call(a,"/auth/logout",method="POST",cookie=session,
                HTTP_X_CSRF_TOKEN=csrf,HTTP_ORIGIN=ORIGIN)[0],200)
            self.assertEqual(self.call(a,"/api/session",cookie=session)[0],401)

    def test_nonstandard_gpc_values_reject_before_transport(self):
        a=self.make()
        for value in ("","0","true","1,1"," 1","1 ",'"1"',1,True,None):
            with self.subTest(value=value):
                self.assertEqual(self.call(a,"/auth/google/start",HTTP_SEC_GPC=value)[0],400)
        self.assertEqual(self.sent,[])

    def test_invalid_gpc_callback_still_consumes_flow(self):
        a=self.make();flow,cookie=self.start(a)
        status,headers,_=self.callback(a,flow,cookie,HTTP_SEC_GPC="0")
        self.assertEqual(status,400);self.assert_clear(headers)
        self.assertEqual(self.callback(a,flow,cookie,HTTP_SEC_GPC="1")[0],401)
        self.assertEqual(self.sent,[])

    def test_gpc_does_not_grant_identity_or_relax_unknown_headers(self):
        a=self.make()
        for header in ("HTTP_X_FORWARDED_PROTO","HTTP_X_OWNER_SUBJECT","HTTP_UNKNOWN_HEADER"):
            self.assertEqual(self.call(a,"/auth/google/start",HTTP_SEC_GPC="1",
                **{header:"synthetic-value"})[0],400)
        self.assertEqual(self.sent,[])
        flow,cookie=self.start(a);self.queue(flow,sub="different-synthetic-owner")
        status,headers,_=self.callback(a,flow,cookie,HTTP_SEC_GPC="1")
        self.assertEqual(status,401);self.assert_clear(headers)
        self.assertFalse(any(k=="Set-Cookie" and v.startswith(SESSION_COOKIE+"=") for k,v in headers))

    def test_wsgi_version_and_flags_require_exact_supported_types(self):
        a=self.make(auth=None)
        cases={"wsgi.version":[None,[1,0],(1,), (True,False),(1,1),(2,0),("1","0")],
               "wsgi.multithread":[None,0,1,"true"],
               "wsgi.multiprocess":[None,0,1,True,"false"],
               "wsgi.run_once":[None,0,1,True,"false"]}
        for key,values in cases.items():
            for value in values:
                with self.subTest(field=key,value=repr(value)):
                    self.assertEqual(self.call(a,"/healthz",**{key:value})[0],400)
        for multithread in (False,True):
            self.assertEqual(self.call(a,"/healthz",**{"wsgi.multithread":multithread})[0],200)
        self.assertEqual(self.sent,[])

    def test_callback_with_unsupported_wsgi_lifecycle_consumes_without_authentication(self):
        a=self.make()
        for changes in ({"wsgi.multiprocess":None},{"wsgi.run_once":True},
                        {"wsgi.multithread":1},{"wsgi.version":(2,0)}):
            flow,cookie=self.start(a)
            with patch.object(a._authenticator,"authenticate") as authenticate:
                status,headers,_=self.callback(a,flow,cookie,**changes)
                self.assertEqual(status,400);self.assert_clear(headers)
                self.assertEqual(self.callback(a,flow,cookie)[0],401)
                authenticate.assert_not_called()

    def test_cross_site_session_reads_and_logout_refused(self):
        a=self.make();session,_,_,_=self.login(a)
        for path in ("/","/api/session","/api/ruby-review-synthetic"):
            for site in ("cross-site","same-site"):
                self.assertEqual(self.call(a,path,cookie=session,HTTP_SEC_FETCH_SITE=site)[0],400)
            self.assertEqual(self.call(a,path,cookie=session,HTTP_ORIGIN="https://other.test")[0],400)
        self.assertEqual(self.call(a,"/api/session",cookie=session,HTTP_SEC_FETCH_SITE="same-origin")[0],200)

    def test_google_redirect_chain_can_land_as_top_level_document_only(self):
        a=self.make();session,_,_,_=self.login(a)
        navigation={"HTTP_SEC_FETCH_SITE":"cross-site","HTTP_SEC_FETCH_MODE":"navigate",
                    "HTTP_SEC_FETCH_DEST":"document","HTTP_SEC_FETCH_USER":"?1"}
        status,_,body=self.call(a,"/",cookie=session,**navigation)
        self.assertEqual(status,200);self.assertIn("Signed-in",body.decode())
        self.assertEqual(self.call(a,"/api/session",cookie=session,**navigation)[0],400)
        navigation["HTTP_SEC_FETCH_DEST"]="iframe"
        self.assertEqual(self.call(a,"/",cookie=session,**navigation)[0],400)

    def test_callback_header_failure_consumes_flow_and_clears_cookie(self):
        a=self.make();flow,cookie=self.start(a);self.queue(flow)
        status,headers,_=self.callback(a,flow,cookie,HTTP_HOST="wrong.test")
        self.assertEqual(status,400);self.assert_clear(headers);self.assertEqual(self.sent,[])
        self.assertEqual(self.callback(a,flow,cookie)[0],401)

    def test_callback_query_duplicates_malformed_percent_and_override_fields(self):
        variants=[lambda s:f"state={s}&state={s}&code=x",lambda s:f"state={s}&code=x&code=y",
                  lambda s:f"state={s}&code=%GG",lambda s:f"state={s}&code=%FF",
                  lambda s:f"state={s}&code=x&nonce=override",lambda s:f"state={s}&code=x&verifier=v",
                  lambda s:f"state={s}&code=x&jku=https%3A%2F%2Fevil.test",
                  lambda s:f"state={s}&code=x&error=denied",lambda s:f"state={s}&error=denied",
                  lambda s:f"state={s}&code=x&iss=https%3A%2F%2Fevil.test",
                  lambda s:f"state={s}&code=x&error_description=SECRET"]
        a=self.make()
        for build in variants:
            flow,cookie=self.start(a)
            status,headers,body=self.callback(a,flow,cookie,query=build(flow["state"]))
            self.assertIn(status,(400,401));self.assert_clear(headers)
            self.assertEqual(self.callback(a,flow,cookie)[0],401);self.assertNotIn("SECRET",body.decode())
        self.assertEqual(self.sent,[])

    def test_google_optional_callback_metadata_is_bounded_and_accepted(self):
        a=self.make();flow,cookie=self.start(a);self.queue(flow)
        query=urlencode({"state":flow["state"],"code":"synthetic-code","scope":"openid","authuser":"0",
                         "prompt":"consent","iss":"https://accounts.google.com"})
        self.assertEqual(self.callback(a,flow,cookie,query=query,HTTP_SEC_FETCH_SITE="cross-site")[0],303)

    def test_wrong_browser_expired_flow_and_replay_never_exchange(self):
        a=self.make();flow,cookie=self.start(a)
        bad=FLOW_COOKIE+"="+"X"*64
        self.assertEqual(self.callback(a,flow,bad)[0],401)
        self.assertEqual(self.callback(a,flow,cookie)[0],401)
        flow,cookie=self.start(a);self.mono+=5
        self.assertEqual(self.callback(a,flow,cookie)[0],401);self.assertEqual(self.sent,[])
        session,flow,cookie,_=self.login(a);count=len(self.sent)
        self.assertEqual(self.callback(a,flow,cookie)[0],401);self.assertEqual(len(self.sent),count)

    def test_bad_identity_and_signature_leave_previous_session_valid(self):
        a=self.make();session,_,_,_=self.login(a)
        for claim in ({"sub":"wrong"},{"nonce":"X"*64},{"aud":"wrong.apps.googleusercontent.com"},{"exp":NOW}):
            flow,cookie=self.start(a);self.queue(flow,cert=False,**claim)
            with patch.object(a._sessions,"issue") as issue:
                status,headers,_=self.callback(a,flow,cookie+"; "+session)
                self.assertEqual(status,401);self.assert_clear(headers);issue.assert_not_called()
            self.assertEqual(self.call(a,"/api/session",cookie=session)[0],200)

    def test_fresh_login_recovers_stale_cookie_and_rotates_live_cookie(self):
        a=self.make();old,_,_,_=self.login(a)
        new,_,_,_=self.login(a,cert=False,previous=old)
        self.assertNotEqual(new,old);self.assertEqual(self.call(a,"/api/session",cookie=old)[0],401)
        self.mono+=10;newer,_,_,_=self.login(a,cert=False,previous=new)
        self.assertNotEqual(newer,new);self.assertEqual(self.call(a,"/api/session",cookie=newer)[0],200)
        unknown=SESSION_COOKIE+"="+"X"*64
        self.assertEqual(self.login(a,cert=False,previous=unknown)[0].split("=",1)[0],SESSION_COOKIE)

    def test_duplicate_or_malformed_session_cookie_never_authenticates(self):
        a=self.make()
        for previous in (SESSION_COOKIE+"=short",SESSION_COOKIE+"="+"X"*64+"; "+SESSION_COOKIE+"="+"X"*64):
            flow,cookie=self.start(a)
            status,headers,_=self.callback(a,flow,cookie+"; "+previous)
            self.assertEqual(status,401);self.assert_clear(headers)
        self.assertEqual(self.sent,[])

    def test_callback_method_body_and_generic_errors_clear_flow_cookie(self):
        a=self.make()
        for kw in ({"method":"POST","body":b"x=1"},{"method":"HEAD"},{"CONTENT_LENGTH":"1"}):
            flow,cookie=self.start(a);status,headers,_=self.callback(a,flow,cookie,**kw)
            self.assertIn(status,(400,405));self.assert_clear(headers)
            self.assertEqual(self.callback(a,flow,cookie)[0],401)
        flow,cookie=self.start(a)
        with patch.object(a._authenticator,"authenticate",side_effect=RuntimeError("SECRET_DETAILS")):
            status,headers,body=self.callback(a,flow,cookie)
        self.assertEqual(status,503);self.assert_clear(headers);self.assertNotIn("SECRET",body.decode())

    def test_no_fixture_claims_or_mutation_routes(self):
        a=self.make()
        for path in ("/auth/fixture/session","/auth/fixture/login","/api/ruby-review/records","/api/execute","/auth/google/claims"):
            self.assertEqual(self.call(a,path)[0],404)
            self.assertEqual(self.call(a,path,method="POST",body=b"{}")[0],405)
        self.assertEqual(self.call(a,"/auth/logout")[0],405)
        self.assertEqual(self.call(a,"/api/session",method="OPTIONS")[0],405)
        self.assertEqual(self.call(a,"/api/session",query="token=secret")[0],400)

    def test_logout_requires_exact_origin_valid_form_and_current_csrf(self):
        a=self.make();session,_,_,_=self.login(a)
        _,_,body=self.call(a,"/api/session",cookie=session);old=json.loads(body)["csrf_token"]
        _,_,body=self.call(a,"/api/session",cookie=session);new=json.loads(body)["csrf_token"]
        self.assertNotEqual(old,new)
        header=lambda csrf:{"HTTP_X_CSRF_TOKEN":csrf}
        for kw,expected in (({},403),({"HTTP_ORIGIN":"https://wrong.test"},400),
                            ({"HTTP_ORIGIN":ORIGIN,"CONTENT_TYPE":"application/json"},403)):
            self.assertEqual(self.call(a,"/auth/logout",method="POST",cookie=session,**header(new),**kw)[0],expected)
        self.assertEqual(self.call(a,"/auth/logout",method="POST",cookie=session,**header(old),HTTP_ORIGIN=ORIGIN)[0],401)
        self.assertEqual(self.call(a,"/auth/logout",method="POST",cookie=session,**header(new),HTTP_ORIGIN=ORIGIN)[0],200)

    def test_logout_body_bounds_duplicates_short_reads_and_transfer_encoding(self):
        a=self.make();session,_,_,_=self.login(a)
        _,_,body=self.call(a,"/api/session",cookie=session);csrf=json.loads(body)["csrf_token"]
        valid=urlencode({"csrf_token":csrf}).encode()
        cases=[(valid,{"CONTENT_LENGTH":"9999"}),(valid,{"CONTENT_LENGTH":"-1"}),(valid,{"CONTENT_LENGTH":"0001"}),
               (valid,{"CONTENT_LENGTH":"1000"}),(valid,{"HTTP_TRANSFER_ENCODING":"chunked"}),
               (valid+b"&csrf_token=other",{}),(b"csrf_token=%GG",{}),(b"csrf_token=abc&extra=1",{})]
        for b,kw in cases:self.assertEqual(self.call(a,"/auth/logout",method="POST",cookie=session,body=b,HTTP_ORIGIN=ORIGIN,**kw)[0],400)
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],200)

    def test_lifecycle_csrf_rotation_cannot_issue_revive_or_accept_old_token(self):
        s=SessionStore(enabled=True,idle_seconds=10,absolute_seconds=30,capacity=2,clock=lambda:self.mono)
        self.addCleanup(s.close)
        self.assertIsNone(s.rotate_csrf("X"*64));r=s.issue();n=s.rotate_csrf(r.token)
        self.assertIsNone(s.lookup(r.token,require_csrf=True,csrf_token=r.csrf_token))
        self.assertIsNotNone(s.lookup(r.token,require_csrf=True,csrf_token=n))
        self.mono+=10;self.assertIsNone(s.rotate_csrf(r.token));self.assertIsNone(s.lookup(r.token))
        self.mono-=1
        with self.assertRaises(LifecycleError):s.rotate_csrf(r.token)

    def test_parallel_same_callback_issues_at_most_one_session(self):
        a=self.make();flow,cookie=self.start(a);self.queue(flow)
        with ThreadPoolExecutor(max_workers=8) as pool:statuses=list(pool.map(lambda _:self.callback(a,flow,cookie)[0],range(8)))
        self.assertEqual(statuses.count(303),1);self.assertEqual(statuses.count(401),7);self.assertEqual(len(self.sent),2)

    def test_close_clears_state_backend_and_prevents_future_requests(self):
        a=self.make();session,_,_,_=self.login(a);backend=a._authenticator;a.close();count=len(self.sent)
        self.assertEqual(self.call(a,"/api/session",cookie=session)[0],503)
        self.assertEqual(self.call(a,"/auth/google/start")[0],503)
        self.assertFalse(backend.matches_policy(ORIGIN,CLIENT,OWNER));self.assertEqual(len(self.sent),count)

    def test_import_and_module_entrypoint_have_no_server_or_config_loader(self):
        source=inspect.getsource(app_module)
        self.assertNotIn("serve_forever",source);self.assertNotIn("make_server",source)
        self.assertNotIn("os.environ",source);self.assertNotIn("complete_login_fixture",source)
        self.assertEqual(set(inspect.signature(StagingHTTPApplication).parameters),{"config","enabled","authenticator","limits","clock"})

    def test_staging_image_has_only_real_application_dependencies_and_inactive_entrypoint(self):
        path=Path(__file__).resolve().parents[2]/"Dockerfile.ruby-staging-review"
        source=path.read_text();copies=[line.split()[1] for line in source.splitlines() if line.startswith("COPY ")]
        self.assertEqual(set(copies),{"ops/mission-control-identity/"+name for name in (
            "requirements.txt","ruby_staging_lifecycle.py","ruby_staging_id_token.py",
            "ruby_staging_google_auth.py","ruby_staging_app_factory.py","ruby_staging_http_app.py","ruby_review_synthetic.py")})
        self.assertIn('ENTRYPOINT ["python3", "/srv/ruby_staging_http_app.py"]',source)
        self.assertIn("USER app",source)
        self.assertNotIn("EXPOSE ",source);self.assertNotIn("VOLUME ",source)
        self.assertNotIn("COPY .",source);self.assertNotIn("rehearsal",source)
        self.assertNotIn("google_ceo_session.py",source);self.assertNotIn("google_exchange.py",source)

    def test_interleaved_store_clock_rollback_permanently_closes_application(self):
        script=[]
        def clock():return script.pop(0) if script else self.mono
        a=self.make(clock=clock);flow,cookie=self.start(a);self.queue(flow)
        script.extend([100.0,101.0,100.0])
        status,headers,_=self.callback(a,flow,cookie)
        self.assertEqual(status,503);self.assert_clear(headers);self.assertTrue(a._closed)
        self.assertFalse(a._authenticator.matches_policy(ORIGIN,CLIENT,OWNER))
        self.mono=102.0;self.assertEqual(self.call(a,"/auth/google/start")[0],503)

    def test_close_still_closes_backend_if_store_cleanup_raises(self):
        a=self.make()
        with patch.object(a._flows,"close",side_effect=RuntimeError("cleanup failure")):
            with self.assertRaises(RuntimeError):a.close()
        self.assertTrue(a._sessions._closed)
        self.assertFalse(a._authenticator.matches_policy(ORIGIN,CLIENT,OWNER))


if __name__=="__main__":unittest.main(verbosity=2)
