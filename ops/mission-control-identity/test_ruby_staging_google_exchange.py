"""Socket-forbidden exchange/cache/fixture integration with ephemeral RSA certs."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import formatdate
import hashlib
import inspect
import json
import socket
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt

from ruby_staging_google_exchange import (
    TOKEN_URL, CERTIFICATE_URL, OFFLINE_EXCHANGE_OPT_IN,
    OfflineGoogleCodeExchange, OfflineGoogleFixtureTransport, OfflineExchangeRejected,
    FixtureHTTPRequest, FixtureHTTPResponse,
)
from ruby_staging_lifecycle import SESSION_COOKIE, CodeExchangeInputs, pkce_challenge
from ruby_staging_rehearsal import StagingRehearsalProfile
from ruby_staging_review_harness import StagingReviewHarness, INTEGRATION_OPT_IN, FixtureIntegrationError

NOW = 1700000000
PROFILE = StagingRehearsalProfile(enabled=True, origin="https://exchange.example.test",
    callback="https://exchange.example.test/auth/google/callback",
    client_id="synthetic-exchange.apps.googleusercontent.com", owner_subject="synthetic-exchange-owner")
HOST = ("Host", "exchange.example.test")


class OfflineExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = cls.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption())
        cls.signer = crypt.RSASigner.from_string(private, key_id="synthetic-cert")

    def setUp(self):
        self.wall, self.mono = NOW, 100
        self.harnesses, self.exchanges = [], []
        self.addCleanup(lambda: [h.close() for h in self.harnesses])
        self.addCleanup(lambda: [e.close() for e in self.exchanges])
        for p in (patch.object(socket, "socket", side_effect=AssertionError("network_forbidden")),
                  patch.object(socket, "create_connection", side_effect=AssertionError("network_forbidden")),
                  patch.object(requests.Session, "send", side_effect=AssertionError("network_forbidden")),
                  patch("google.auth._helpers.utcnow", side_effect=lambda: datetime.fromtimestamp(self.wall, timezone.utc).replace(tzinfo=None))):
            p.start(); self.addCleanup(p.stop)

    def cert(self, end=NOW+3600, begin=NOW-3600, key=None):
        key = key or self.key
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-offline-fixture")])
        return (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(1).not_valid_before(datetime.fromtimestamp(begin, timezone.utc))
                .not_valid_after(datetime.fromtimestamp(end, timezone.utc)).sign(key, hashes.SHA256())
                .public_bytes(serialization.Encoding.PEM).decode("ascii"))

    def make(self, **kw):
        transport = OfflineGoogleFixtureTransport()
        options = dict(transport=transport, max_cache_seconds=300, enabled=True,
                       opt_in=OFFLINE_EXCHANGE_OPT_IN, clock=lambda: self.wall)
        options.update(kw)
        exchange = OfflineGoogleCodeExchange(PROFILE, **options)
        self.exchanges.append(exchange)
        h = StagingReviewHarness(PROFILE, enabled=True, opt_in=INTEGRATION_OPT_IN,
            flow_seconds=5, idle_seconds=10, absolute_seconds=30, capacity=32,
            clock=lambda: self.mono, offline_exchange=exchange)
        self.harnesses.append(h)
        return h, exchange, transport

    def token(self, start, **claims):
        payload = dict(iss=PROFILE.issuer, aud=PROFILE.client_id, sub=PROFILE.owner_subject,
                       nonce=start.flow.nonce, iat=NOW-1, exp=NOW+3600)
        payload.update(claims)
        return jwt.encode(self.signer, payload).decode("ascii")

    def token_response(self, token, **changes):
        response = FixtureHTTPResponse(200, TOKEN_URL, (("Content-Type", "application/json"),),
            json.dumps({"id_token": token, "token_type": "Bearer", "access_token": "synthetic-access-not-used"}).encode())
        return replace(response, **changes)

    def cert_response(self, **changes):
        response = FixtureHTTPResponse(200, CERTIFICATE_URL,
            (("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "public, max-age=300"),
             ("Date", formatdate(self.wall, usegmt=True))), json.dumps({"synthetic-cert": self.cert()}).encode())
        return replace(response, **changes)

    def queue(self, transport, start, *, cert=True, **claims):
        transport.enqueue(self.token_response(self.token(start, **claims)))
        if cert: transport.enqueue(self.cert_response())

    def complete(self, h, start, *, code="synthetic-code+/&=", headers=None):
        return h.complete_code_login_fixture(state=start.flow.state, code_fixture=code,
            headers=headers or (HOST, ("Cookie", start.flow_cookie.split(";",1)[0])))

    def check_failed(self, h, start, transport, status=401):
        with patch.object(h._sessions, "issue") as issue:
            response = self.complete(h, start)
            self.assertEqual(response.status, status)
            self.assertEqual(self.complete(h, start).status, 401)
            issue.assert_not_called()
        self.assertFalse(json.loads(response.body)["real_identity_verified"])
        return response

    def test_default_off_exact_transport_and_ttl(self):
        for kw in ({"enabled": False}, {"enabled": 1}, {"opt_in": "wrong"}, {"transport": object()},
                   {"transport": requests.Session()}, {"max_cache_seconds": True}, {"max_cache_seconds": 0},
                   {"max_cache_seconds": 86401}, {"clock": lambda: float("nan")}):
            with self.subTest(kw=tuple(kw)):
                with self.assertRaisesRegex(OfflineExchangeRejected, "configuration_invalid"): self.make(**kw)
        class Other(OfflineGoogleFixtureTransport): pass
        with self.assertRaises(OfflineExchangeRejected): self.make(transport=Other())

    def test_no_request_overrides_and_no_credentials_input(self):
        self.assertEqual(set(inspect.signature(StagingReviewHarness.complete_code_login_fixture).parameters),
                         {"self", "state", "code_fixture", "headers"})
        self.assertNotIn("client_secret", inspect.signature(OfflineGoogleCodeExchange).parameters)
        self.assertNotIn("url", inspect.signature(OfflineGoogleCodeExchange.exchange_fixture).parameters)

    def test_end_to_end_code_pkce_signature_session_records(self):
        h, e, t = self.make(); s = h.start_login_fixture(); self.queue(t,s)
        r = self.complete(h,s); self.assertEqual(r.status,200)
        self.assertEqual([q.url for q in t.requests], [TOKEN_URL,CERTIFICATE_URL])
        post, get = t.requests
        data = parse_qs(post.body.decode("ascii"), strict_parsing=True)
        self.assertEqual(set(data), {"code","code_verifier","client_id","client_secret","grant_type","redirect_uri"})
        self.assertEqual(data["code"],["synthetic-code+/&="])
        self.assertEqual(data["client_id"],[PROFILE.client_id]); self.assertEqual(data["redirect_uri"],[PROFILE.callback])
        self.assertEqual(data["grant_type"],["authorization_code"])
        self.assertEqual(pkce_challenge(data["code_verifier"][0]),s.flow.code_challenge)
        self.assertEqual(data["client_secret"],["synthetic-fixture-only-not-a-google-credential"])
        for q in t.requests:
            self.assertFalse(q.allow_redirects); self.assertFalse(q.trust_environment)
            self.assertEqual(q.timeout,(3,5)); self.assertNotIn("synthetic-code",repr(q))
        self.assertEqual(get.body,b"")
        body=json.loads(r.body)
        self.assertTrue(body["synthetic_token_signature_verified"])
        self.assertEqual(body["authority"],"none")
        self.assertFalse(body["real_identity_verified"]); self.assertFalse(body["execution_authorized"])
        cookie=next(v.split(";",1)[0] for n,v in r.headers if n=="Set-Cookie" and v.startswith(SESSION_COOKIE+"="))
        read=h.dispatch(method="GET",path="/api/ruby-review-synthetic/records",headers=(HOST,("Cookie",cookie)))
        self.assertEqual(read.status,200); self.assertEqual(len(json.loads(read.body)["records"]),3)
        self.assertNotIn("synthetic-access",repr(r)); self.assertNotIn("synthetic-code",r.body.decode())

    def test_browser_host_duplicate_and_expired_flow_before_exchange(self):
        for variant in ("browser","host","duplicate","expired"):
            h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s)
            headers=(HOST,("Cookie",s.flow_cookie.split(";",1)[0]))
            if variant=="browser":headers=(HOST,("Cookie","__Host-ruby-staging-flow="+"X"*64))
            if variant=="host":headers=(("Host","evil.example"),)+headers[1:]
            if variant=="duplicate":headers=headers+(headers[1],)
            if variant=="expired":self.mono+=5
            self.assertIn(self.complete(h,s,headers=headers).status,(400,401));self.assertEqual(t.requests,())
            self.assertEqual(self.complete(h,s).status,401)

    def test_malformed_code_consumes_flow_without_request(self):
        for code in (None,True,[],"","code with space","code\n","é","X"*4097):
            h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s)
            self.assertEqual(self.complete(h,s,code=code).status,401)
            self.assertEqual(self.complete(h,s).status,401);self.assertEqual(t.requests,())

    def test_missing_exchange_consumes_flow(self):
        h,e,t=self.make();h._offline_exchange=None;s=h.start_login_fixture()
        self.check_failed(h,s,t,503)

    def test_wrong_policy_or_exchange_type_rejected_at_construction(self):
        h,e,t=self.make()
        for value in (object(),lambda:True):
            with self.assertRaises(FixtureIntegrationError):
                StagingReviewHarness(PROFILE,enabled=True,opt_in=INTEGRATION_OPT_IN,flow_seconds=5,
                    idle_seconds=10,absolute_seconds=30,capacity=2,offline_exchange=value)
        with self.assertRaises(FixtureIntegrationError):
            StagingReviewHarness(replace(PROFILE,owner_subject="other-owner"),enabled=True,opt_in=INTEGRATION_OPT_IN,
                flow_seconds=5,idle_seconds=10,absolute_seconds=30,capacity=2,offline_exchange=e)
        self.assertEqual(t.requests,())

    def test_replay_and_concurrent_callbacks_exchange_once(self):
        h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s)
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses=list(pool.map(lambda _:self.complete(h,s).status,range(8)))
        self.assertEqual(statuses.count(200),1);self.assertEqual(statuses.count(401),7)
        self.assertEqual(len(t.requests),2)

    def test_token_response_status_redirect_and_endpoint_failure(self):
        for changes in ({"status":302},{"status":True},{"status":500},{"final_url":TOKEN_URL+"?redirect=1"},
                        {"final_url":"https://evil.example"},{"headers":(("Content-Type","application/json"),("Location",TOKEN_URL))}):
            h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s),**changes))
            self.check_failed(h,s,t);self.assertEqual(len(t.requests),1)

    def test_token_response_bounds_encoding_headers_and_json(self):
        base=(("Content-Type","application/json"),)
        invalid=[{"body":b"x"*65537},{"body":b""},{"body":b"\xff"},{"body":b"[]"},
                 {"body":b'{"id_token":"x","id_token":"y"}'},{"body":b'{"extra":{"a":1,"a":2},"id_token":"x"}'},
                 {"body":b'{"id_token":"x","n":NaN}'},{"body":b'{"error":"SECRET_UPSTREAM"}'},
                 {"body":b'{"id_token":null}'},{"body":json.dumps({"id_token":"x"*16385}).encode()},
                 {"headers":(("Content-Type","text/html"),)},
                 {"headers":base+(("Content-Encoding","gzip"),)},
                 {"headers":base+(("Content-Length","1"),)},
                 {"headers":base+(("content-type","application/json"),)},
                 {"headers":base+(("X-Test","\r\n"),)},
                 {"headers":base+(("X-Test","x"*8192),)},
                 {"body":b'{"id_token":"x","token_type":"Basic"}'}]
        for changes in invalid:
            h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s),**changes))
            r=self.check_failed(h,s,t);self.assertEqual(len(t.requests),1)
            self.assertNotIn("SECRET",r.body.decode())

    def test_invalid_signature_claims_and_nonce_never_issue_session(self):
        for claims in ({"sub":"other"},{"aud":"other.apps.googleusercontent.com"},{"iss":"https://evil.example"},
                       {"nonce":"X"*64},{"exp":NOW}):
            h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s,**claims);self.check_failed(h,s,t)
        h,e,t=self.make();s=h.start_login_fixture()
        token=self.token(s);head,pay,sig=token.split(".");sig=("A" if sig[0]!="A" else "B")+sig[1:]
        t.enqueue(self.token_response(".".join((head,pay,sig))));t.enqueue(self.cert_response());self.check_failed(h,s,t)

    def test_certificate_http_failures_do_not_create_cache(self):
        for changes in ({"status":302},{"status":500},{"final_url":"https://evil.example"},
                        {"body":b"x"*131073},{"body":b"[]"},{"headers":(("Content-Type","text/plain"),)}):
            h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)))
            t.enqueue(self.cert_response(**changes));self.check_failed(h,s,t)
            self.assertIsNone(e._verifier);self.assertEqual(e._valid_until,0)

    def test_certificate_content_rejects_missing_duplicate_oversize_noncertificate_and_many_keys(self):
        invalid=[b"{}",b'{"k":"x","k":"y"}',json.dumps({"k":None}).encode(),
                 json.dumps({"k":"x"*16385}).encode(),json.dumps({"k":"-----BEGIN PUBLIC KEY-----"}).encode(),
                 json.dumps({str(i):self.cert() for i in range(9)}).encode(),
                 json.dumps({"bad key":self.cert()}).encode(),json.dumps({"k":self.cert(end=NOW)}).encode(),
                 json.dumps({"k":self.cert(begin=NOW+1)}).encode()]
        for body in invalid:
            h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)))
            t.enqueue(self.cert_response(body=body));self.check_failed(h,s,t);self.assertIsNone(e._verifier)

    def test_certificate_rsa_size_and_algorithm_rejected(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=1024)
        h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)))
        t.enqueue(self.cert_response(body=json.dumps({"synthetic-cert":self.cert(key=key)}).encode()))
        self.check_failed(h,s,t)

    def test_cache_directives_age_and_date_fail_closed(self):
        cases=[("public","0",formatdate(NOW,usegmt=True)),("max-age=0","0",formatdate(NOW,usegmt=True)),
               ("max-age=300, no-store","0",formatdate(NOW,usegmt=True)),
               ("max-age=300, no-cache","0",formatdate(NOW,usegmt=True)),
               ("max-age=300, private","0",formatdate(NOW,usegmt=True)),
               ("max-age=300, max-age=999","0",formatdate(NOW,usegmt=True)),
               ("max-age=-1","0",formatdate(NOW,usegmt=True)),
               ("max-age=300","300",formatdate(NOW,usegmt=True)),
               ("max-age=300","-1",formatdate(NOW,usegmt=True)),
               ("max-age=300","0",formatdate(NOW+1,usegmt=True)),
               ("max-age=300","0",formatdate(NOW-300,usegmt=True)),
               ("max-age=300","0","bad-date")]
        for cache,age,date in cases:
            h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)))
            t.enqueue(self.cert_response(headers=(("Content-Type","application/json"),("Cache-Control",cache),
                                                  ("Date",date),("Age",age))))
            self.check_failed(h,s,t);self.assertIsNone(e._verifier)

    def test_fresh_cache_reused_and_no_token_provided_refresh(self):
        h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s);self.assertEqual(self.complete(h,s).status,200)
        s=h.start_login_fixture();self.queue(t,s,cert=False);self.assertEqual(self.complete(h,s).status,200)
        self.assertEqual([q.method for q in t.requests],["POST","GET","POST"])
        private=self.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        other=crypt.RSASigner.from_string(private,key_id="unknown-key")
        s=h.start_login_fixture();token=jwt.encode(other,dict(iss=PROFILE.issuer,aud=PROFILE.client_id,
            sub=PROFILE.owner_subject,nonce=s.flow.nonce,iat=NOW,exp=NOW+300)).decode()
        t.enqueue(self.token_response(token));self.check_failed(h,s,t)
        self.assertEqual(len(t.requests),4)

    def test_cache_expiry_refetches_and_failed_refresh_does_not_reuse_stale(self):
        h,e,t=self.make(max_cache_seconds=1);s=h.start_login_fixture();self.queue(t,s)
        self.assertEqual(self.complete(h,s).status,200);self.wall+=1
        s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)));t.enqueue(self.cert_response(status=500))
        self.check_failed(h,s,t);self.assertIsNone(e._verifier)
        s=h.start_login_fixture();self.queue(t,s);self.assertEqual(self.complete(h,s).status,200)
        self.assertEqual([q.method for q in t.requests],["POST","GET","POST","GET","POST","GET"])

    def test_cache_age_date_and_ttl_cap_are_conservative(self):
        h,e,t=self.make(max_cache_seconds=250);s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)))
        t.enqueue(self.cert_response(headers=(("Content-Type","application/json"),("Cache-Control","public, max-age=300"),
            ("Date",formatdate(NOW-60,usegmt=True)),("Age","120"))))
        self.assertEqual(self.complete(h,s).status,200);self.assertEqual(e._valid_until,NOW+180)
        h,e,t=self.make(max_cache_seconds=30);s=h.start_login_fixture();self.queue(t,s)
        self.assertEqual(self.complete(h,s).status,200);self.assertEqual(e._valid_until,NOW+30)

    def test_cache_certificate_expiry_caps_refresh(self):
        h,e,t=self.make();s=h.start_login_fixture();t.enqueue(self.token_response(self.token(s)))
        t.enqueue(self.cert_response(body=json.dumps({"synthetic-cert":self.cert(end=NOW+1)}).encode()))
        self.assertEqual(self.complete(h,s).status,200);self.assertEqual(e._valid_until,NOW+1)
        self.wall+=1;s=h.start_login_fixture();self.queue(t,s)
        self.assertEqual(self.complete(h,s).status,200);self.assertEqual(len(t.requests),4)

    def test_response_delay_subtracted_from_age(self):
        h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s)
        original=OfflineGoogleFixtureTransport.send
        def delayed(transport,request):
            result=original(transport,request)
            if request.url==CERTIFICATE_URL:self.wall+=10
            return result
        with patch.object(OfflineGoogleFixtureTransport,"send",delayed):
            self.assertEqual(self.complete(h,s).status,200)
        self.assertEqual(e._valid_until,NOW+300)

    def test_clock_rollback_nan_and_close_permanently_reject(self):
        for bad in (NOW-1,float("nan"),True):
            h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s);self.wall=bad
            self.check_failed(h,s,t);self.wall=NOW
            s=h.start_login_fixture();self.assertEqual(self.complete(h,s).status,401);self.assertEqual(t.requests,())
        h,e,t=self.make();e.close();s=h.start_login_fixture();self.assertEqual(self.complete(h,s).status,401)

    def test_empty_transport_is_redacted_and_state_consumed(self):
        h,e,t=self.make();s=h.start_login_fixture();r=self.check_failed(h,s,t)
        self.assertEqual(json.loads(r.body)["error"],"fixture_login_invalid")
        with self.assertRaises(OfflineExchangeRejected) as caught:
            e.exchange_fixture(code_fixture="SECRET_CODE",flow=CodeExchangeInputs("N"*64,"V"*64))
        self.assertEqual(str(caught.exception),"offline_exchange_rejected")
        self.assertTrue(caught.exception.__suppress_context__)

    def test_verifier_and_exchange_share_clock_high_water_mark(self):
        script=[]
        def clock():return script.pop(0) if script else self.wall
        h,e,t=self.make(clock=clock);s=h.start_login_fixture();self.queue(t,s)
        self.assertEqual(self.complete(h,s).status,200)
        s=h.start_login_fixture();self.wall=NOW+1;self.queue(t,s,cert=False,iat=NOW+1)
        script.extend([NOW,NOW,NOW,NOW+1,NOW+1,NOW])
        self.check_failed(h,s,t)
        self.assertTrue(e._closed);self.assertIsNone(e._verifier)
        count=len(t.requests);script.clear();s=h.start_login_fixture()
        self.assertEqual(self.complete(h,s).status,401);self.assertEqual(len(t.requests),count)

    def test_internal_flow_type_and_format_validation(self):
        h,e,t=self.make()
        for flow in (object(),None,CodeExchangeInputs("bad","V"*64),CodeExchangeInputs("N"*64,"bad")):
            with self.assertRaises(OfflineExchangeRejected):e.exchange_fixture(code_fixture="synthetic",flow=flow)
        self.assertEqual(t.requests,())

    def test_rotation_requires_success_and_previous_session_remains_on_failure(self):
        h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s);r=self.complete(h,s)
        cookie=next(v.split(";",1)[0] for n,v in r.headers if n=="Set-Cookie" and v.startswith(SESSION_COOKIE+"="))
        s=h.start_login_fixture();self.queue(t,s,cert=False,sub="wrong")
        headers=(HOST,("Cookie",s.flow_cookie.split(";",1)[0]+"; "+cookie))
        self.assertEqual(self.complete(h,s,headers=headers).status,401)
        read=lambda:h.dispatch(method="GET",path="/auth/fixture/session",headers=(HOST,("Cookie",cookie)))
        self.assertEqual(read().status,200)
        s=h.start_login_fixture();self.queue(t,s,cert=False)
        headers=(HOST,("Cookie",s.flow_cookie.split(";",1)[0]+"; "+cookie))
        self.assertEqual(self.complete(h,s,headers=headers).status,200);self.assertEqual(read().status,401)

    def test_no_login_route_and_cleanup_discards_cassette(self):
        h,e,t=self.make();s=h.start_login_fixture();self.queue(t,s);self.assertEqual(self.complete(h,s).status,200)
        self.assertEqual(h.dispatch(method="GET",path="/auth/google/callback",headers=(HOST,)).status,404)
        self.assertEqual(h.dispatch(method="POST",path="/auth/google/callback",headers=(HOST,)).status,405)
        h.close();self.assertEqual(t.requests,())
        with self.assertRaises(OfflineExchangeRejected):t.enqueue(self.cert_response())
        with self.assertRaises(FixtureIntegrationError):h.start_login_fixture()

    def test_cassette_capacity_and_repr(self):
        transport=OfflineGoogleFixtureTransport();r=self.token_response("SYNTHETIC_TOKEN_SECRET")
        self.assertNotIn("SYNTHETIC_TOKEN_SECRET",repr(r))
        for _ in range(64):transport.enqueue(r)
        with self.assertRaises(OfflineExchangeRejected):transport.enqueue(r)
        with self.assertRaises(OfflineExchangeRejected):transport.send(object())
        transport.close()


if __name__=="__main__":unittest.main(verbosity=2)
