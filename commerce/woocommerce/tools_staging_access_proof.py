"""One explicitly enabled catalog GET. No catalog output or write capability."""
from __future__ import annotations

import base64
import json
import math
import os
import re
import ssl
import sys
from urllib import request

APPROVED_ORIGIN = 'https://darkgreen-wallaby-680439.hostingersite.com'
URL = APPROVED_ORIGIN + '/wp-json/wc/v3/products?page=1&per_page=1'
MAX_BYTES = 256 * 1024
TIMEOUT_SECONDS = 10
SUCCESS = 'RUBY_STAGING_ACCESS_PROOF_OK products_read=true variations_checked=false mutations=false'
FAILURE = 'RUBY_STAGING_ACCESS_PROOF_BLOCKED no_retry_authorized=true'


class ProofRejected(Exception):
    pass


def reject(*args):
    raise ProofRejected()


class RefuseRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        reject()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            reject()
        result[key] = value
    return result


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        reject()
    return result


def prove(environment):
    # Validate exact approved origin BEFORE retrieving any credential values.
    if environment.get('RUBY_STAGING_ACCESS_PROOF_APPROVED') != 'true':
        reject()
    if environment.get('RUBY_WOO_PRODUCTION_BASE_URL') != APPROVED_ORIGIN:
        reject()
    key = environment.get('RUBY_WOO_PRODUCTION_CONSUMER_KEY')
    secret = environment.get('RUBY_WOO_PRODUCTION_CONSUMER_SECRET')
    for value, prefix in ((key, 'ck_'), (secret, 'cs_')):
        if not isinstance(value, str) or not re.fullmatch(prefix + r'[A-Za-z0-9_-]{1,256}', value):
            reject()
    authorization = base64.b64encode((key + ':' + secret).encode('ascii')).decode('ascii')
    # Platform-default verified TLS; OS trust configuration remains trusted.
    context = ssl.create_default_context()
    if context.check_hostname is not True or context.verify_mode != ssl.CERT_REQUIRED:
        reject()
    opener = request.build_opener(request.ProxyHandler({}), request.HTTPSHandler(context=context), RefuseRedirect())
    req = request.Request(URL, method='GET', headers={
        'Authorization': 'Basic ' + authorization,
        'Accept': 'application/json', 'Accept-Encoding': 'identity',
        'User-Agent': 'ruby-staging-access-proof/1',
    })
    with opener.open(req, timeout=TIMEOUT_SECONDS) as response:
        if type(response.status) is not int or response.status != 200 or response.geturl() != URL:
            reject()
        content_type = response.headers.get('Content-Type', '')
        if not isinstance(content_type, str) or not re.fullmatch(r'application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?', content_type, re.IGNORECASE):
            reject()
        if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
            reject()
        length = response.headers.get('Content-Length')
        if length is not None and (not isinstance(length, str) or not re.fullmatch(r'[0-9]{1,10}', length) or int(length) > MAX_BYTES):
            reject()
        raw = response.read(MAX_BYTES + 1)
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or (length is not None and int(length) != len(raw)):
            reject()
    payload = json.loads(raw.decode('utf-8'), object_pairs_hook=strict_object,
                         parse_constant=reject, parse_float=finite_float)
    if not isinstance(payload, list) or len(payload) > 1 or not all(isinstance(item, dict) for item in payload):
        reject()
    # Empty catalogs are valid access responses; no product identity is asserted.


def main(environment=None):
    try:
        prove(os.environ if environment is None else environment)
    except Exception:
        # Do not export exception text, traceback, response, URL or credentials.
        print(FAILURE)
        return 2
    print(SUCCESS)
    return 0


if __name__ == '__main__':
    sys.exit(main())
