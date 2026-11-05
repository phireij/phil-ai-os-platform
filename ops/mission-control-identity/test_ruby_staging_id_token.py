"""Real signature verification of ephemeral SYNTHETIC tokens. No network."""

import base64
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import socket
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt as google_jwt

from ruby_staging_id_token import (
    ISSUER, PRODUCTION_CLIENT_ID, StagingIdTokenVerifier,
    TokenRejected, VerifierConfigurationError,
)


NOW = 1700000000
AUDIENCE = "synthetic-staging.apps.googleusercontent.com"
OWNER = "synthetic-owner-001"
NONCE = "N" * 64


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class NoSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        raise AssertionError("network_forbidden")


class TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public = cls.key.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.other_public = cls.other_key.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        private = cls.key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.signer = crypt.RSASigner.from_string(private, key_id="synthetic-key-1")

    def setUp(self):
        self.now = NOW
        for patcher in (
            patch.object(socket, "socket", NoSocket),
            patch.object(socket, "create_connection", side_effect=AssertionError("network_forbidden")),
            patch("google.auth._helpers.utcnow", side_effect=lambda: datetime.fromtimestamp(self.now, timezone.utc).replace(tzinfo=None)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def verifier(self, **kwargs):
        config = dict(audience=AUDIENCE, owner_subject=OWNER,
                      trusted_pems={"synthetic-key-1": self.public},
                      keys_valid_until=NOW + 600, enabled=True, clock=lambda: self.now)
        config.update(kwargs)
        return StagingIdTokenVerifier(**config)

    def claims(self, **kwargs):
        value = dict(iss=ISSUER, aud=AUDIENCE, sub=OWNER, nonce=NONCE,
                     iat=NOW-10, exp=NOW+300)
        value.update(kwargs)
        return value

    def token(self, claims=None, header=None):
        return google_jwt.encode(self.signer, self.claims() if claims is None else claims,
                                 header=header).decode("ascii")

    def raw_token(self, header, payload, key=None):
        encoded = b64(header) + "." + b64(payload)
        signature = (key or self.key).sign(encoded.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
        return encoded + "." + b64(signature)

    def rejects(self, token, verifier=None, nonce=NONCE):
        with self.assertRaisesRegex(TokenRejected, "^id_token_rejected$") as caught:
            (verifier or self.verifier()).verify(token, expected_nonce=nonce)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_exact_approved_versions_loaded(self):
        for name, version in {"google-auth":"2.62.0", "requests":"2.34.2", "cryptography":"50.0.2"}.items():
            self.assertEqual(importlib.metadata.version(name), version)

    def test_valid_signature_owner_and_nonce_return_no_authority(self):
        result = self.verifier().verify(self.token(), expected_nonce=NONCE)
        self.assertEqual((result.issuer,result.audience,result.subject), (ISSUER,AUDIENCE,OWNER))
        self.assertTrue(result.signature_verified)
        self.assertTrue(result.owner_matches)
        self.assertEqual(result.authority,"none")
        self.assertEqual(result.trust_provenance,"external_server_responsibility")
        self.assertFalse(hasattr(result,"token"))
        self.assertNotIn(OWNER,repr(result))

    def test_google_library_signature_verification_cannot_be_disabled(self):
        with patch("ruby_staging_id_token.google_jwt.decode", wraps=google_jwt.decode) as decode:
            self.verifier().verify(self.token(), expected_nonce=NONCE)
        self.assertIs(decode.call_args.kwargs["verify"],True)
        self.assertEqual(decode.call_args.kwargs["audience"],AUDIENCE)
        self.assertEqual(decode.call_args.kwargs["clock_skew_in_seconds"],0)
        self.assertEqual(set(decode.call_args.kwargs["certs"]),{"synthetic-key-1"})

    def test_default_disabled_and_truthy_values_rejected(self):
        for enabled in (False, None, 1, "true"):
            with self.subTest(enabled=enabled), self.assertRaises(VerifierConfigurationError):
                self.verifier(enabled=enabled)
        with self.assertRaises(VerifierConfigurationError):
            StagingIdTokenVerifier(audience=AUDIENCE,owner_subject=OWNER,
                trusted_pems={"synthetic-key-1":self.public},keys_valid_until=NOW+600)

    def test_production_client_and_bad_policy_rejected(self):
        for field, value in (("audience",PRODUCTION_CLIENT_ID),("audience",None),
                             ("audience","https://evil.example"),("owner_subject",""),
                             ("owner_subject","owner@example.test"),("owner_subject",[])):
            with self.subTest(field=field,value=value), self.assertRaises(VerifierConfigurationError):
                self.verifier(**{field:value})

    def test_wrong_signature_and_wrong_key_rejected(self):
        token = self.raw_token(json.dumps({"alg":"RS256","kid":"synthetic-key-1"}).encode(),
                               json.dumps(self.claims()).encode(),key=self.other_key)
        self.rejects(token)
        self.rejects(self.token(), self.verifier(trusted_pems={"synthetic-key-1":self.other_public}))

    def test_tampered_payload_rejected(self):
        header, _, signature = self.token().split(".")
        self.rejects(header+"."+b64(json.dumps(self.claims(exp=NOW+999)).encode())+"."+signature)

    def test_truncated_or_modified_signature_rejected(self):
        header,payload,signature=self.token().split(".")
        for bad in (signature[:-4],"A"*len(signature),signature+"="):
            self.rejects(header+"."+payload+"."+bad)

    def test_non_rs256_algorithms_are_rejected_before_library(self):
        for alg in ("none","HS256","RS512","ES256",None,True):
            token=self.raw_token(json.dumps({"alg":alg,"kid":"synthetic-key-1"}).encode(),json.dumps(self.claims()).encode())
            with self.subTest(alg=alg), patch("ruby_staging_id_token.google_jwt.decode") as decode:
                self.rejects(token)
                decode.assert_not_called()

    def test_missing_or_unknown_kid_never_falls_back(self):
        for header in ({"alg":"RS256"},{"alg":"RS256","kid":"unknown"},
                       {"alg":"RS256","kid":"https://evil.example/key"},{"alg":"RS256","kid":[]}):
            token=self.raw_token(json.dumps(header).encode(),json.dumps(self.claims()).encode())
            with patch("ruby_staging_id_token.google_jwt.decode") as decode:
                self.rejects(token)
                decode.assert_not_called()

    def test_embedded_key_url_critical_and_compression_headers_rejected(self):
        for name, value in (("jku","https://evil.example/keys"),("x5u","https://evil.example/cert"),
                            ("jwk",{}),("x5c",[]),("crit",[]),("b64",False),("zip","DEF")):
            header={"alg":"RS256","kid":"synthetic-key-1",name:value}
            self.rejects(self.raw_token(json.dumps(header).encode(),json.dumps(self.claims()).encode()))

    def test_typ_if_present_must_be_jwt(self):
        for typ in (None,"at+jwt","jwt",[],True):
            header={"alg":"RS256","kid":"synthetic-key-1","typ":typ}
            self.rejects(self.raw_token(json.dumps(header).encode(),json.dumps(self.claims()).encode()))
        self.verifier().verify(self.token(header={"typ":"JWT"}),expected_nonce=NONCE)

    def test_duplicate_header_fields_rejected_even_when_signed(self):
        for header in (b'{"alg":"RS256","alg":"RS256","kid":"synthetic-key-1"}',
                       b'{"alg":"RS256","kid":"synthetic-key-1","kid":"synthetic-key-1"}'):
            self.rejects(self.raw_token(header,json.dumps(self.claims()).encode()))

    def test_duplicate_claims_and_nested_duplicates_rejected(self):
        for field in ("iss","aud","sub","nonce","iat","exp","azp","nbf"):
            claims=self.claims(azp=AUDIENCE,nbf=NOW-1)
            raw=json.dumps(claims)[:-1]+',"'+field+'":'+json.dumps(claims[field])+'}'
            self.rejects(self.raw_token(b'{"alg":"RS256","kid":"synthetic-key-1"}',raw.encode()))
        raw=json.dumps(self.claims())[:-1]+',"extra":{"a":1,"a":1}}'
        self.rejects(self.raw_token(b'{"alg":"RS256","kid":"synthetic-key-1"}',raw.encode()))

    def test_wrong_issuer_including_alternate_google_spelling_rejected(self):
        for issuer in ("accounts.google.com","https://accounts.google.com/","https://evil.example",[],None):
            self.rejects(self.token(self.claims(iss=issuer)))

    def test_audience_is_required_scalar_and_exact(self):
        for audience in ("other.apps.googleusercontent.com",[AUDIENCE],[],None,True):
            self.rejects(self.token(self.claims(aud=audience)))

    def test_azp_if_present_must_be_exact_client(self):
        self.verifier().verify(self.token(self.claims(azp=AUDIENCE)),expected_nonce=NONCE)
        for azp in ("other.apps.googleusercontent.com",[],None,True):
            self.rejects(self.token(self.claims(azp=azp)))

    def test_wrong_owner_cannot_be_replaced_by_email_or_domain(self):
        for owner in ("synthetic-owner-002",OWNER.upper(),None,123,[]):
            self.rejects(self.token(self.claims(sub=owner,email="owner@example.test",email_verified=True,hd="example.test")))

    def test_nonce_required_and_bound_to_server_value(self):
        for nonce in ("Q"*64,None,"",NONCE.lower(),[],True):
            self.rejects(self.token(self.claims(nonce=nonce)))
        for expected in (None,"",NONCE.lower(),[],True,"N"*63):
            self.rejects(self.token(),nonce=expected)

    def test_all_required_claims_must_be_present(self):
        for name in ("iss","aud","sub","nonce","iat","exp"):
            claims=self.claims();del claims[name]
            self.rejects(self.token(claims))

    def test_timestamp_claims_are_strict_finite_nonnegative_integers(self):
        for field in ("iat","exp","nbf"):
            for value in (True,False,1.0,"1700000000",None,[],float("nan"),float("inf"),-1,2**53+1):
                with self.subTest(field=field,value=value):
                    self.rejects(self.token(self.claims(**{field:value})))

    def test_expired_future_and_inverted_lifetimes_rejected(self):
        for changes in ({"exp":NOW-1},{"exp":NOW},{"iat":NOW+1},
                        {"iat":NOW,"exp":NOW},{"iat":NOW-5,"exp":NOW-10},{"nbf":NOW+1}):
            self.rejects(self.token(self.claims(**changes)))

    def test_not_before_equal_now_is_accepted(self):
        self.verifier().verify(self.token(self.claims(nbf=NOW)),expected_nonce=NONCE)

    def test_expiry_rechecked_after_signature_verification(self):
        verifier=self.verifier()
        token=self.token(self.claims(exp=NOW+1))
        original=google_jwt.decode
        def slow(*args,**kwargs):
            value=original(*args,**kwargs);self.now=NOW+1;return value
        with patch("ruby_staging_id_token.google_jwt.decode",side_effect=slow):
            self.rejects(token,verifier)

    def test_stale_keys_rejected_and_never_refreshed(self):
        verifier=self.verifier(keys_valid_until=NOW+1)
        self.now=NOW+1
        with patch("ruby_staging_id_token.google_jwt.decode") as decode:
            self.rejects(self.token(),verifier)
            decode.assert_not_called()
        self.now=NOW
        self.rejects(self.token(),verifier)

    def test_clock_rollback_and_invalid_clock_permanently_close(self):
        for bad in (NOW-1,float("nan"),float("inf"),None,True,"1700000000"):
            self.now=NOW
            verifier=self.verifier()
            token=self.token()
            self.now=bad
            self.rejects(token,verifier)
            self.now=NOW
            self.rejects(token,verifier)

    def test_expiry_cannot_be_extended_by_input_dict_mutation(self):
        keys={"synthetic-key-1":self.public}
        verifier=self.verifier(trusted_pems=keys)
        keys["synthetic-key-1"]=self.other_public
        verifier.verify(self.token(),expected_nonce=NONCE)
        token=self.raw_token(b'{"alg":"RS256","kid":"synthetic-key-1"}',json.dumps(self.claims()).encode(),self.other_key)
        self.rejects(token,verifier)

    def test_key_rotation_requires_an_explicit_new_trusted_snapshot(self):
        token=self.raw_token(b'{"alg":"RS256","kid":"synthetic-key-2"}',json.dumps(self.claims()).encode(),self.other_key)
        self.rejects(token)
        keys={"synthetic-key-1":self.public,"synthetic-key-2":self.other_public}
        self.verifier(trusted_pems=keys).verify(token,expected_nonce=NONCE)

    def test_bad_keyset_configuration_rejected(self):
        for keys in ({},None,{"x":self.public.decode()},{"x":b"bad"},
                     {"https://evil.example/key":self.public},{str(i):self.public for i in range(9)}):
            with self.subTest(keys_type=type(keys)),self.assertRaises(VerifierConfigurationError):
                self.verifier(trusted_pems=keys)
        for expiry in (NOW,NOW-1,None,True,float("inf"),"1800000000"):
            with self.assertRaises(VerifierConfigurationError):
                self.verifier(keys_valid_until=expiry)

    def test_private_weak_and_non_rsa_keys_rejected(self):
        weak=rsa.generate_private_key(public_exponent=65537,key_size=1024)
        elliptic=ec.generate_private_key(ec.SECP256R1())
        pems=[weak.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo),
              elliptic.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo),
              self.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())]
        for pem in pems:
            with self.assertRaises(VerifierConfigurationError):
                self.verifier(trusted_pems={"synthetic-key-1":pem})

    def certificate(self, start=NOW-60, end=NOW+10):
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"synthetic-only.example.test")])
        cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.key.public_key()).serial_number(1)
        cert=cert.not_valid_before(datetime.fromtimestamp(start,timezone.utc)).not_valid_after(datetime.fromtimestamp(end,timezone.utc)).sign(self.key,hashes.SHA256())
        return cert.public_bytes(serialization.Encoding.PEM)

    def test_certificate_expiry_caps_trusted_snapshot_expiry(self):
        verifier=self.verifier(trusted_pems={"synthetic-key-1":self.certificate()})
        verifier.verify(self.token(),expected_nonce=NONCE)
        self.now=NOW+10
        self.rejects(self.token(),verifier)

    def test_future_or_expired_certificates_rejected(self):
        for start,end in ((NOW+1,NOW+100),(NOW-100,NOW)):
            with self.assertRaises(VerifierConfigurationError):
                self.verifier(trusted_pems={"synthetic-key-1":self.certificate(start,end)})

    def test_constructor_clock_rollback_cannot_precede_certificate_validity(self):
        values=iter((NOW+10,NOW))
        with self.assertRaises(VerifierConfigurationError):
            self.verifier(trusted_pems={"synthetic-key-1":self.certificate(NOW+5,NOW+100)},
                          clock=lambda:next(values))

    def test_input_type_size_and_segment_bounds(self):
        for token in (None,{},b"token","","a"*16385,"a.b","a.b.c.d","é.b.c","a..c"):
            self.rejects(token)
        self.rejects("a"*2049+".e30."+"a"*30)

    def test_invalid_json_and_non_object_claims_rejected(self):
        header=b'{"alg":"RS256","kid":"synthetic-key-1"}'
        for payload in (b'[]',b'null',b'"text"',b'{invalid',b'{"x":NaN}',b'\xff'):
            self.rejects(self.raw_token(header,payload))
        self.rejects(self.raw_token(b'[]',json.dumps(self.claims()).encode()))

    def test_noncanonical_base64_padding_or_characters_rejected(self):
        parts=self.token().split(".")
        for index in range(3):
            for suffix in ("="," ","\n","+"):
                changed=parts.copy();changed[index]+=suffix
                self.rejects(".".join(changed))

    def test_library_errors_are_redacted(self):
        with patch("ruby_staging_id_token.google_jwt.decode",side_effect=ValueError("private-token-and-owner-details")):
            self.rejects(self.token())

    def test_success_result_contains_no_unneeded_claims(self):
        result=self.verifier().verify(self.token(self.claims(email="person@example.test",picture="https://example.test/photo",custom="private")),expected_nonce=NONCE)
        self.assertFalse(hasattr(result,"email"))
        self.assertFalse(hasattr(result,"picture"))
        self.assertFalse(hasattr(result,"custom"))


if __name__ == "__main__":
    unittest.main()
