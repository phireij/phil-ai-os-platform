"""Actual in-process WSGI owner transport; no server or external request."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import threading
import unittest
from unittest.mock import patch

import test_ruby_staging_http_app as fixtures
from ruby_staging_http_app import (StagingHTTPApplication, StagingHTTPConfigurationError,
    StagingOwnerQuoteBinding, StagingOwnerQuoteError, ISSUER)

LIST='/api/ruby-owner-inquiries'
PREPARE='/api/ruby-owner-quotes/prepare'
IID='synthetic-inquiry-0001'; RID='synthetic-revision-0001'
SENTINEL='PRIVATE_TRANSPORT_SENTINEL'


def request():
    return {'inquiry_id':IID,'expected_revision_id':RID,'idempotency_key':'synthetic-prepare-key',
            'authored_quote':{'synthetic':'input'}}


class OwnerQuoteHTTPTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.HTTPApplicationTests.setUpClass.__func__)
    setUp=fixtures.HTTPApplicationTests.setUp
    send=fixtures.HTTPApplicationTests.send
    make_auth=fixtures.HTTPApplicationTests.make_auth
    make=fixtures.HTTPApplicationTests.make
    environ=fixtures.HTTPApplicationTests.environ
    call=fixtures.HTTPApplicationTests.call
    start=fixtures.HTTPApplicationTests.start
    token=fixtures.HTTPApplicationTests.token
    response=fixtures.HTTPApplicationTests.response
    queue=fixtures.HTTPApplicationTests.queue
    callback=fixtures.HTTPApplicationTests.callback
    login=fixtures.HTTPApplicationTests.login

    def binding(self, **kwargs):
        events=[]
        options=dict(issuer=ISSUER,owner_subject=fixtures.OWNER,
            list_inquiries=lambda:events.append('list') or {'inquiries':[]},
            get_inquiry=lambda iid:events.append(('detail',iid)) or {'inquiry_id':iid},
            prepare_quote=lambda value:events.append(('prepare',value)) or {'state':'prepared_not_recorded'},
            close=lambda:events.append('close'))
        options.update(kwargs)
        return StagingOwnerQuoteBinding(**options), events

    def ready(self, **kwargs):
        binding,events=self.binding(**kwargs);app=self.make(owner_quote_binding=binding)
        cookie,*_=self.login(app)
        status,_,body=self.call(app,'/api/session',cookie=cookie)
        self.assertEqual(status,200)
        return app,cookie,json.loads(body)['csrf_token'],events

    def prepare(self, app, cookie, csrf, *, data=None, body=None, **kwargs):
        body=json.dumps(request() if data is None else data).encode() if body is None else body
        options=dict(method='POST',cookie=cookie,body=body,HTTP_ORIGIN=fixtures.ORIGIN,
                     HTTP_X_CSRF_TOKEN=csrf,CONTENT_TYPE='application/json')
        options.update(kwargs)
        return self.call(app,PREPARE,**options)

    def test_default_absent_and_disabled_never_enable_or_touch_binding(self):
        app=self.make(auth=None)
        self.assertEqual(self.call(app,LIST)[0],404)
        self.assertEqual(self.call(app,PREPARE,method='POST')[0],405)
        app=StagingHTTPApplication(owner_quote_binding=object());self.apps.append(app)
        self.assertEqual(self.call(app,LIST)[0],503)

    def test_exact_owner_type_and_exclusive_ownership(self):
        binding,events=self.binding(owner_subject='other')
        with self.assertRaises(StagingHTTPConfigurationError):self.make(owner_quote_binding=binding)
        self.assertEqual(events,[]);binding.close();self.assertEqual(events,['close'])
        binding,events=self.binding();app=self.make(owner_quote_binding=binding)
        with self.assertRaises(StagingHTTPConfigurationError):self.make(owner_quote_binding=binding)
        self.assertEqual(events,[]);app.close();app.close();self.assertEqual(events,['close'])
        with self.assertRaises(StagingHTTPConfigurationError):self.make(owner_quote_binding=object())

    def test_authentication_required_before_callback_or_body_read(self):
        binding,events=self.binding();app=self.make(owner_quote_binding=binding)
        class Unread:
            def read(self,n):raise AssertionError('body must not be read')
        self.assertEqual(self.call(app,LIST)[0],401)
        self.assertEqual(self.call(app,LIST+'/'+IID)[0],401)
        self.assertEqual(self.prepare(app,'','',**{'wsgi.input':Unread()})[0],401)
        self.assertEqual(events,[])

    def test_real_signed_owner_session_lists_reads_and_prepares_without_authority(self):
        app,cookie,csrf,events=self.ready()
        self.assertEqual(self.call(app,LIST,cookie=cookie)[0],200)
        self.assertEqual(self.call(app,LIST+'/'+IID,cookie=cookie)[0],200)
        status,headers,body=self.prepare(app,cookie,csrf)
        self.assertEqual(status,200);data=json.loads(body)
        self.assertEqual(data['state'],'prepared_not_recorded');self.assertEqual(data['authority'],'none')
        self.assertFalse(data['execution_authorized']);self.assertFalse(data['mutation_authorized'])
        self.assertEqual(events,['list',('detail',IID),('prepare',request())])
        self.assertNotIn(SENTINEL,body.decode())

    def test_origin_csrf_framing_and_methods_fail_before_body(self):
        app,cookie,csrf,events=self.ready()
        class Unread:
            def read(self,n):raise AssertionError('body must not be read')
        variants=[{'HTTP_ORIGIN':'https://other.invalid'},{'HTTP_ORIGIN':''},{'HTTP_X_CSRF_TOKEN':'wrong'},
            {'CONTENT_TYPE':'application/json; charset=utf-8'},{'CONTENT_LENGTH':''},{'CONTENT_LENGTH':'01'},
            {'CONTENT_LENGTH':'-1'},{'CONTENT_LENGTH':'1,1'},{'CONTENT_LENGTH':'65537'},
            {'HTTP_TRANSFER_ENCODING':'chunked'},{'HTTP_CONTENT_LENGTH':'10'},{'HTTP_CONNECTION':'keep-alive'}]
        for values in variants:
            with self.subTest(values=values):
                self.assertIn(self.prepare(app,cookie,csrf,**{**values,'wsgi.input':Unread()})[0],(400,401,403,413))
        self.assertEqual(self.call(app,PREPARE,cookie=cookie)[0],405)
        self.assertEqual(self.call(app,LIST,method='POST',cookie=cookie)[0],405)
        self.assertEqual(self.call(app,LIST,cookie=cookie,query='limit=10')[0],400)
        self.assertEqual(self.call(app,LIST+'/../other',cookie=cookie)[0],400)
        self.assertEqual(events,[])

    def test_strict_json_bounds_unknown_authority_fields_and_short_reads(self):
        app,cookie,csrf,events=self.ready()
        invalid=[b'{}',b'[]',b'null',b'\xff',b'{"x":1,"x":2}',b'{"x":NaN}',
            json.dumps({**request(),'owner_subject':'forged'}).encode(),
            json.dumps({**request(),'authored_quote':{'x':1.5}}).encode(),
            json.dumps({**request(),'authored_quote':{'x':2**53}}).encode(),
            json.dumps({**request(),'authored_quote':{'x':'\ud800'}}).encode(),
            json.dumps({**request(),'inquiry_id':True}).encode()]
        for body in invalid:
            with self.subTest(body=body[:40]):self.assertEqual(self.prepare(app,cookie,csrf,body=body)[0],400)
        self.assertEqual(self.prepare(app,cookie,csrf,**{'wsgi.input':io.BytesIO(b'{}')})[0],400)
        nested={}
        for _ in range(17):nested={'x':nested}
        self.assertEqual(self.prepare(app,cookie,csrf,data={**request(),'authored_quote':nested})[0],400)
        self.assertEqual(events,[])

    def test_body_read_is_bounded_and_never_drains_beyond_declared_length(self):
        app,cookie,csrf,events=self.ready();raw=json.dumps(request()).encode()
        class Chunked:
            def __init__(self):self.offset=0;self.sizes=[]
            def read(self,n):
                self.sizes.append(n)
                if self.offset==len(raw):raise AssertionError('read past declared body')
                chunk=raw[self.offset:self.offset+min(n,7)];self.offset+=len(chunk);return chunk
        stream=Chunked()
        self.assertEqual(self.prepare(app,cookie,csrf,body=raw,**{'wsgi.input':stream})[0],200)
        self.assertEqual(stream.offset,len(raw));self.assertEqual(stream.sizes[0],len(raw))
        class Oversized:
            def read(self,n):return b'x'*(n+1)
        self.assertEqual(self.prepare(app,cookie,csrf,**{'wsgi.input':Oversized()})[0],400)

    def test_private_result_fields_and_exceptions_never_exposed(self):
        for key in ('source_handoff','catalog_snapshot','scope_fingerprint','request_body','idempotency_key','original_source'):
            app,cookie,csrf,events=self.ready(prepare_quote=lambda value,k=key:{'nested':{k:SENTINEL}})
            status,_,body=self.prepare(app,cookie,csrf);self.assertEqual(status,503);self.assertNotIn(SENTINEL.encode(),body)
        def fail(_):raise RuntimeError(SENTINEL)
        app,cookie,csrf,events=self.ready(prepare_quote=fail)
        status,_,body=self.prepare(app,cookie,csrf);self.assertEqual(status,503);self.assertNotIn(SENTINEL.encode(),body)

    def test_prepare_key_matches_existing_private_contract(self):
        app,cookie,csrf,events=self.ready()
        self.assertEqual(self.prepare(app,cookie,csrf,data={**request(),'idempotency_key':'synthetic.key~valid-01'})[0],200)
        self.assertEqual(self.prepare(app,cookie,csrf,data={**request(),'idempotency_key':'x'*129})[0],400)

    def test_serialized_response_limit_includes_escaping_and_metadata(self):
        app,cookie,csrf,events=self.ready(prepare_quote=lambda value:{'review':'あ'*25000})
        status,_,body=self.prepare(app,cookie,csrf)
        self.assertEqual(status,503);self.assertLess(len(body),1024)

    def test_closed_error_mapping(self):
        for code,status in [('inquiry_source_unavailable',404),('inquiry_not_found',404),
                            ('inquiry_stale',409),('quote_input_invalid',400),('quote_unavailable',503),
                            (SENTINEL,503)]:
            def fail(_,code=code):raise StagingOwnerQuoteError(code)
            app,cookie,csrf,events=self.ready(prepare_quote=fail)
            actual,_,body=self.prepare(app,cookie,csrf);self.assertEqual(actual,status);self.assertNotIn(SENTINEL.encode(),body)

    def test_logout_during_body_read_prevents_service_call(self):
        app,cookie,csrf,events=self.ready();entered=threading.Event();release=threading.Event()
        raw=json.dumps(request()).encode()
        class Blocked:
            def read(self,n):entered.set();self_wait=release.wait(5);assert self_wait;return raw
        with ThreadPoolExecutor(max_workers=1) as pool:
            result=pool.submit(self.prepare,app,cookie,csrf,body=raw,**{'wsgi.input':Blocked()})
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.call(app,'/auth/logout',method='POST',cookie=cookie,
                HTTP_ORIGIN=fixtures.ORIGIN,HTTP_X_CSRF_TOKEN=csrf)[0],200)
            release.set();self.assertEqual(result.result(5)[0],401)
        self.assertEqual(events,[])

    def test_late_service_result_rejected_after_all_session_invalidations(self):
        for change in ('logout','close','expire','csrf','login','clock'):
            with self.subTest(change=change):
                entered=threading.Event();release=threading.Event()
                def prepare(value):
                    entered.set();assert release.wait(5);return {'private_review':SENTINEL}
                app,cookie,csrf,events=self.ready(prepare_quote=prepare)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    result=pool.submit(self.prepare,app,cookie,csrf);self.assertTrue(entered.wait(5))
                    self.assertEqual(self.call(app,LIST,cookie=cookie)[0],503)
                    if change=='logout':self.assertEqual(self.call(app,'/auth/logout',method='POST',cookie=cookie,HTTP_ORIGIN=fixtures.ORIGIN,HTTP_X_CSRF_TOKEN=csrf)[0],200)
                    elif change=='close':app.close();self.assertNotIn('close',events)
                    elif change=='expire':self.mono+=11
                    elif change=='csrf':self.call(app,'/api/session',cookie=cookie)
                    elif change=='login':self.login(app,cert=False,previous=cookie)
                    else:self.mono-=1
                    release.set();status,_,body=result.result(5)
                    self.assertIn(status,(401,503));self.assertNotIn(SENTINEL.encode(),body)
                if change in ('close','clock'):self.assertEqual(events.count('close'),1)
                app.close();self.assertEqual(events.count('close'),1)
                self.mono+=100

    def test_close_releases_owned_binding_once_and_sanitizes_cleanup_error(self):
        calls=[]
        def close():calls.append('close');raise RuntimeError(SENTINEL)
        app,cookie,csrf,events=self.ready(close=close)
        app.close();app.close();self.assertEqual(calls,['close'])
        self.assertEqual(self.call(app,LIST,cookie=cookie)[0],503)

    def test_control_cleanup_failure_still_closes_auth_backend(self):
        for later_failure in (None, RuntimeError('synthetic-later-failure')):
            with self.subTest(later_failure=later_failure):
                failure=KeyboardInterrupt('synthetic-control')
                def close():raise failure
                app,cookie,csrf,events=self.ready(close=close)
                options={'side_effect':later_failure} if later_failure else {'wraps':app._authenticator.close}
                with patch.object(app._authenticator,'close',**options) as auth_close:
                    with self.assertRaises(KeyboardInterrupt) as caught:app.close()
                    self.assertIs(caught.exception,failure);auth_close.assert_called_once()
                app._authenticator.close()
                self.assertIsNone(app._owner_quote_binding)
                self.assertEqual(self.call(app,LIST,cookie=cookie)[0],503)

if __name__=='__main__':unittest.main()
