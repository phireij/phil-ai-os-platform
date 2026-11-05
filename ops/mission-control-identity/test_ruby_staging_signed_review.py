"""Offline signed-token/flow/session integration with ephemeral synthetic keys."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import inspect
import json
import socket
import threading
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

from ruby_staging_id_token import StagingIdTokenVerifier
from ruby_staging_lifecycle import SESSION_COOKIE
from ruby_staging_rehearsal import StagingRehearsalProfile
from ruby_staging_review_harness import StagingReviewHarness, INTEGRATION_OPT_IN, FixtureIntegrationError


NOW = 1700000000
PROFILE = StagingRehearsalProfile(enabled=True, origin="https://signed-review.example.test",
    callback="https://signed-review.example.test/auth/google/callback",
    client_id="signed-synthetic-staging.apps.googleusercontent.com", owner_subject="signed-synthetic-owner")
HOST = ("Host", "signed-review.example.test")
RECORDS = "/api/ruby-review-synthetic/records"


class NoSocket(socket.socket):
    def __init__(self,*args,**kwargs):
        raise AssertionError("network_forbidden")


class SignedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.other = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.public = cls.key.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        def signer(key):
            private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption())
            return crypt.RSASigner.from_string(private,key_id="synthetic-integration-key")
        cls.signer,cls.other_signer = signer(cls.key),signer(cls.other)

    def setUp(self):
        self.wall = NOW
        self.monotonic = 100
        self.harnesses=[]
        self.addCleanup(lambda:[h.close() for h in self.harnesses])
        for patcher in (patch.object(socket,"socket",NoSocket),
                        patch.object(socket,"create_connection",side_effect=AssertionError("network_forbidden")),
                        patch("google.auth._helpers.utcnow",side_effect=lambda:datetime.fromtimestamp(self.wall,timezone.utc).replace(tzinfo=None))):
            patcher.start();self.addCleanup(patcher.stop)

    def verifier(self,**kwargs):
        config=dict(audience=PROFILE.client_id,owner_subject=PROFILE.owner_subject,
                    trusted_pems={"synthetic-integration-key":self.public},keys_valid_until=NOW+600,
                    enabled=True,clock=lambda:self.wall)
        config.update(kwargs)
        return StagingIdTokenVerifier(**config)

    def make(self,verifier="default"):
        if verifier=="default":verifier=self.verifier()
        harness=StagingReviewHarness(PROFILE,opt_in=INTEGRATION_OPT_IN,enabled=True,
            flow_seconds=5,idle_seconds=10,absolute_seconds=30,capacity=8,
            clock=lambda:self.monotonic,token_verifier=verifier)
        self.harnesses.append(harness)
        return harness

    def token(self,start,signer=None,**claims):
        payload=dict(iss=PROFILE.issuer,aud=PROFILE.client_id,sub=PROFILE.owner_subject,
                     nonce=start.flow.nonce,iat=NOW-10,exp=NOW+300)
        payload.update(claims)
        return jwt.encode(signer or self.signer,payload).decode("ascii")

    def headers(self,start,extra=()):
        return (HOST,("Cookie",start.flow_cookie.split(";",1)[0]))+extra

    def complete(self,h,start,token=None,extra=()):
        return h.complete_signed_login_fixture(state=start.flow.state,
            id_token_fixture=self.token(start) if token is None else token,
            headers=self.headers(start,extra))

    def login(self,h,extra=()):
        start=h.start_login_fixture();result=self.complete(h,start,extra=extra)
        self.assertEqual(result.status,200)
        cookie=next(value.split(";",1)[0] for name,value in result.headers
                    if name=="Set-Cookie" and value.startswith(SESSION_COOKIE+"="))
        return cookie,json.loads(result.body)["csrf_token"],result

    def read(self,h,cookie):
        return h.dispatch(method="GET",path=RECORDS,headers=(HOST,("Cookie",cookie)))

    def assert_no_authority(self,result):
        data=json.loads(result.body)
        self.assertEqual(data["authority"],"none")
        self.assertIs(data["synthetic"],True)
        self.assertIs(data["real_identity_verified"],False)
        self.assertIs(data["execution_authorized"],False)
        self.assertIs(data["mutation_authorized"],False)

    def test_valid_signed_flow_issues_fixture_session_and_reads_records(self):
        h=self.make();cookie,_,result=self.login(h)
        self.assertTrue(json.loads(result.body)["synthetic_token_signature_verified"])
        read=self.read(h,cookie)
        self.assertEqual(read.status,200)
        self.assertEqual(len(json.loads(read.body)["records"]),3)
        self.assert_no_authority(result);self.assert_no_authority(read)

    def test_verifier_is_server_configured_and_no_expected_nonce_argument_exists(self):
        params=inspect.signature(StagingReviewHarness.complete_signed_login_fixture).parameters
        self.assertEqual(set(params),{"self","state","id_token_fixture","headers"})
        for bad in (object(),lambda *_:True,{"verified":True}):
            with self.assertRaisesRegex(FixtureIntegrationError,"token_verifier_invalid"):
                self.make(bad)

    def test_missing_verifier_consumes_flow_without_issuing_session(self):
        h=self.make(None);start=h.start_login_fixture()
        with patch.object(h._sessions,"issue") as issue:
            self.assertEqual(self.complete(h,start).status,503)
            self.assertEqual(self.complete(h,start).status,401)
            issue.assert_not_called()

    def test_invalid_signature_or_identity_never_issues_session_and_consumes_state(self):
        h=self.make()
        cases=[{"signer":self.other_signer},{"sub":"different-owner"},
               {"aud":"different.apps.googleusercontent.com"},{"iss":"https://evil.example"},
               {"nonce":"M"*64},{"exp":NOW}]
        for changes in cases:
            start=h.start_login_fixture();token=self.token(start,**changes)
            with patch.object(h._sessions,"issue") as issue:
                result=self.complete(h,start,token)
                self.assertEqual(result.status,401)
                self.assertEqual(self.complete(h,start).status,401)
                issue.assert_not_called()
            self.assert_no_authority(result)

    def test_verifier_policy_must_match_harness_policy(self):
        for overrides,claims in (({"owner_subject":"another-synthetic-owner"},{"sub":"another-synthetic-owner"}),
                                 ({"audience":"another-staging.apps.googleusercontent.com"},{"aud":"another-staging.apps.googleusercontent.com"})):
            h=self.make(self.verifier(**overrides));start=h.start_login_fixture()
            with patch.object(h._sessions,"issue") as issue:
                self.assertEqual(self.complete(h,start,self.token(start,**claims)).status,401)
                issue.assert_not_called()

    def test_replay_with_same_or_new_flow_is_rejected(self):
        h=self.make();first=h.start_login_fixture();token=self.token(first)
        self.assertEqual(self.complete(h,first,token).status,200)
        self.assertEqual(self.complete(h,first,token).status,401)
        second=h.start_login_fixture()
        self.assertEqual(self.complete(h,second,token).status,401)
        self.assertEqual(self.complete(h,second).status,401)

    def test_wrong_browser_or_malformed_host_rejects_before_crypto(self):
        h=self.make()
        for headers in ((HOST,("Cookie","__Host-ruby-staging-flow="+"X"*64)),
                        (("Host","evil.example"),)):
            start=h.start_login_fixture()
            with patch.object(h._token_verifier,"verify") as verify:
                result=h.complete_signed_login_fixture(state=start.flow.state,id_token_fixture=self.token(start),headers=headers)
                self.assertIn(result.status,(400,401));verify.assert_not_called()
            self.assertEqual(self.complete(h,start).status,401)

    def test_flow_expiry_rejects_before_crypto(self):
        h=self.make();start=h.start_login_fixture();self.monotonic+=5
        with patch.object(h._token_verifier,"verify") as verify:
            self.assertEqual(self.complete(h,start).status,401);verify.assert_not_called()

    def test_stale_key_snapshot_rejects_and_consumes_state(self):
        h=self.make(self.verifier(keys_valid_until=NOW+1));start=h.start_login_fixture();self.wall+=1
        with patch.object(h._sessions,"issue") as issue:
            self.assertEqual(self.complete(h,start).status,401);issue.assert_not_called()
        self.wall=NOW
        self.assertEqual(self.complete(h,start).status,401)

    def test_signature_is_checked_before_rotation_and_bad_attempt_keeps_old_session(self):
        h=self.make();old,_,_=self.login(h);start=h.start_login_fixture()
        bad=self.complete(h,start,self.token(start,signer=self.other_signer),extra=(("Cookie",old),))
        self.assertEqual(bad.status,401)
        self.assertEqual(self.read(h,old).status,200)
        new,_,_=self.login(h,extra=(("Cookie",old),))
        self.assertEqual(self.read(h,old).status,401)
        self.assertEqual(self.read(h,new).status,200)

    def test_duplicate_previous_session_cookie_denied_after_valid_signature(self):
        h=self.make();cookie,_,_=self.login(h);start=h.start_login_fixture()
        with patch.object(h._sessions,"issue") as issue:
            result=self.complete(h,start,extra=(("Cookie",cookie),("Cookie",cookie)))
            self.assertEqual(result.status,401);issue.assert_not_called()

    def test_concurrent_duplicate_callback_issues_exactly_one_fixture_session(self):
        h=self.make();start=h.start_login_fixture();token=self.token(start)
        barrier=threading.Barrier(8)
        def complete(_):
            barrier.wait();return self.complete(h,start,token)
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(complete,range(8)))
        self.assertEqual(sum(r.status==200 for r in results),1)
        for r in results:self.assert_no_authority(r)

    def test_signed_session_uses_existing_logout_and_expiry_controls(self):
        h=self.make();cookie,csrf,_=self.login(h)
        result=h.dispatch(method="POST",path="/auth/fixture/logout",
            headers=(HOST,("Origin",PROFILE.origin),("Cookie",cookie),("X-CSRF-Token",csrf)))
        self.assertEqual(result.status,200);self.assertEqual(self.read(h,cookie).status,401)
        cookie,_,_=self.login(h);self.monotonic+=10
        self.assertEqual(self.read(h,cookie).status,401)

    def test_signed_callback_has_no_request_route_or_real_authority(self):
        h=self.make();cookie,_,_=self.login(h)
        for path in ("/auth/google/callback","/auth/fixture/signed-login","/auth/google/start"):
            result=h.dispatch(method="GET",path=path,headers=(HOST,("Cookie",cookie)))
            self.assertEqual(result.status,404);self.assert_no_authority(result)

    def test_legacy_unsigned_simulation_is_explicitly_labelled(self):
        h=self.make();start=h.start_login_fixture()
        result=h.complete_login_fixture(state=start.flow.state,owner_fixture=PROFILE.owner_subject,
            nonce_fixture=start.flow.nonce,headers=self.headers(start))
        self.assertEqual(result.status,200)
        self.assertIs(json.loads(result.body)["synthetic_token_signature_verified"],False)
        self.assert_no_authority(result)

    def test_close_revokes_signed_session_and_removes_disposable_files(self):
        h=self.make();cookie,_,_=self.login(h);directory=h._fixture.fixture_directory
        h.close();self.assertFalse(directory.exists())
        with self.assertRaises(FixtureIntegrationError):self.read(h,cookie)


if __name__=="__main__":
    unittest.main()
