"""Synthetic tests: all socket creation forbidden, HTTP opener replaced."""
import io
from email.message import Message
import ssl
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request
import tools_staging_access_proof as proof

ENV = {'RUBY_STAGING_ACCESS_PROOF_APPROVED': 'true',
       'RUBY_WOO_PRODUCTION_BASE_URL': proof.APPROVED_ORIGIN,
       'RUBY_WOO_PRODUCTION_CONSUMER_KEY': 'ck_synthetic',
       'RUBY_WOO_PRODUCTION_CONSUMER_SECRET': 'cs_synthetic'}


class Response:
    def __init__(self, raw=b'[]', status=200, url=proof.URL, headers=None):
        self.raw, self.status, self.url = raw, status, url
        self.headers = {'Content-Type': 'application/json'} if headers is None else headers
        self.read_sizes = []
        self.closed = False
    def read(self, size):
        self.read_sizes.append(size)
        return self.raw[:size]
    def geturl(self): return self.url
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.net = patch('socket.socket', side_effect=AssertionError('network forbidden'))
        self.socket = self.net.start()
        self.addCleanup(self.net.stop)
    def invoke(self, response=None, env=None, error=None):
        opener = Mock()
        opener.open.return_value = response or Response()
        if error: opener.open.side_effect = error
        with patch.object(proof.request, 'build_opener', return_value=opener) as factory, patch('sys.stdout', new_callable=io.StringIO) as out, patch('sys.stderr', new_callable=io.StringIO) as err:
            code = proof.main(ENV if env is None else env)
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(out.getvalue(), (proof.SUCCESS if code == 0 else proof.FAILURE) + '\n')
        self.socket.assert_not_called()
        return code, opener, factory
    def test_valid_single_get_tls_proxy_and_copyless_status(self):
        response = Response(b'[{"id":42,"name":"PRIVATE-SYNTHETIC-NAME","price":"123"}]')
        code, opener, factory = self.invoke(response)
        self.assertEqual(code, 0)
        self.assertEqual(opener.open.call_count, 1)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, proof.URL)
        self.assertEqual(req.get_method(), 'GET')
        self.assertIsNone(req.data)
        self.assertEqual(opener.open.call_args.kwargs, {'timeout': 10})
        handlers = factory.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertTrue(handlers[1]._context.check_hostname)
        self.assertEqual(handlers[1]._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertIsInstance(handlers[2], proof.RefuseRedirect)
        self.assertEqual(response.read_sizes, [proof.MAX_BYTES + 1])
        self.assertTrue(response.closed)
        self.assertEqual(self.invoke()[0], 0)
    def test_origin_and_approval_precede_secret_lookup(self):
        class NoSecretReads(dict):
            def get(self, key, default=None):
                if key.endswith(('CONSUMER_KEY', 'CONSUMER_SECRET')): raise AssertionError('secret accessed')
                return super().get(key, default)
        for change in [{'RUBY_STAGING_ACCESS_PROOF_APPROVED': v} for v in [None, False, 'TRUE', 'false']] + [{'RUBY_WOO_PRODUCTION_BASE_URL':v} for v in [None, proof.APPROVED_ORIGIN+'/',proof.APPROVED_ORIGIN+'?x=1','https://other.invalid','http://other.invalid']]:
            env=NoSecretReads(ENV);env.update(change)
            with patch.object(proof.request, 'build_opener') as build:
                with self.assertRaises(proof.ProofRejected):proof.prove(env)
                build.assert_not_called()
    def test_bad_credentials_never_open(self):
        for key,value in [('RUBY_WOO_PRODUCTION_CONSUMER_KEY',None),('RUBY_WOO_PRODUCTION_CONSUMER_KEY','ck_x:bad'),('RUBY_WOO_PRODUCTION_CONSUMER_SECRET','cs_x\n')]:
            env=dict(ENV);env[key]=value
            code,opener,factory=self.invoke(env=env)
            self.assertEqual(code,2);factory.assert_not_called();opener.open.assert_not_called()
    def test_redirect_handler_never_follows(self):
        handler=proof.RefuseRedirect();handler.parent=Mock();headers=Message();headers['Location']='https://other.invalid/'
        for code in [301,302,303,307,308]:
            with self.assertRaises(proof.ProofRejected):getattr(handler,'http_error_'+str(code))(Request(proof.URL),io.BytesIO(),code,'redirect',headers)
        handler.parent.open.assert_not_called()
    def test_malformed_responses_and_json_fail_closed(self):
        responses=[Response(status=True),Response(status=302),Response(url='https://other.invalid'),Response(headers={'Content-Type':'text/html'}),Response(headers={'Content-Type':'application/json','Content-Encoding':'gzip'}),Response(headers={'Content-Type':'application/json','Content-Length':'1'}),Response(headers={'Content-Type':'application/json','Content-Length':str(proof.MAX_BYTES+1)}),Response(raw=b'x'*(proof.MAX_BYTES+1))]
        responses += [Response(raw=v) for v in [b'{}',b'[{},{}]',b'[null]',b'[{"id":1,"id":2}]',b'[NaN]',b'[{"x":1e999}]',b'[{"x":-1e999}]',b'\xff']]
        for response in responses:
            code,opener,_=self.invoke(response)
            self.assertEqual(code,2);self.assertEqual(opener.open.call_count,1);self.assertTrue(response.closed)
    def test_errors_do_not_echo_data_or_retry(self):
        code,opener,_=self.invoke(error=RuntimeError('PRIVATE-SYNTHETIC-SECRET https://private.invalid'))
        self.assertEqual(code,2);self.assertEqual(opener.open.call_count,1)
    def test_unverified_tls_never_open(self):
        bad=Mock();bad.check_hostname=False;bad.verify_mode=ssl.CERT_NONE
        with patch.object(proof.ssl,'create_default_context',return_value=bad):
            code,opener,factory=self.invoke()
        self.assertEqual(code,2);factory.assert_not_called();opener.open.assert_not_called()

if __name__ == '__main__': unittest.main()
