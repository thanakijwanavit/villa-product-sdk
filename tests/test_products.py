"""Offline tests for villaProductSdk.products (vps-d1o).

No AWS calls: the Lambda client, S3 and HTTP downloads are replaced with fakes.
Run: python -m pytest tests
"""
import configparser
import json
import re
import zlib
from pathlib import Path

import pandas as pd
import pytest

import villaProductSdk.products as products
from villaProductSdk.products import INTCOLS, ProductSdk, retrieveJsonZl

ROOT = Path(__file__).resolve().parents[1]


# --- notebook <-> library parity -------------------------------------------

def _notebook_export_cells():
    nb = json.loads((ROOT / 'product-sdk.ipynb').read_text())
    cells = []
    for cell in nb['cells']:
        src = ''.join(cell['source'])
        if cell['cell_type'] == 'code' and re.match(r'#\s*export\s*\n', src):
            body = src.split('\n', 1)[1]
            # nbdev rewrites absolute imports of the package to relative ones
            body = body.replace('from villaProductSdk.', 'from .')
            cells.append(body.strip())
    return cells


def _library_cells():
    text = (ROOT / 'villaProductSdk' / 'products.py').read_text()
    return [c.strip() for c in text.split('# Cell\n')[1:]]


def _norm(code):
    return [line.rstrip() for line in code.strip().splitlines() if line.strip()]


def test_products_py_matches_notebook_exports():
    nb_cells, lib_cells = _notebook_export_cells(), _library_cells()
    assert len(nb_cells) == len(lib_cells)
    for nb_cell, lib_cell in zip(nb_cells, lib_cells):
        assert _norm(nb_cell) == _norm(lib_cell)


def test_all_exported_names_are_defined():
    for name in products.__all__:
        assert hasattr(products, name), name


def test_pandas_is_a_declared_requirement():
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / 'settings.ini')
    reqs = cfg['DEFAULT']['requirements'].split()
    assert 'pandas' in reqs


# --- fakes -------------------------------------------------------------------

def _apigw(body, status=200):
    return {'body': json.dumps(body), 'statusCode': status, 'headers': {}}


class FakeLambda:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def invoke(self, functionName, input, invocationType=None):
        self.calls.append({'functionName': functionName, 'input': input,
                           'invocationType': invocationType})
        return self.responses[functionName]


class FakeHttpResponse:
    def __init__(self, status_code, content=b'', payload=None):
        self.status_code = status_code
        self.content = content
        self._payload = payload
        self.text = repr(payload) if payload is not None else content.decode('latin-1')
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


@pytest.fixture
def sdk():
    return ProductSdk(branch='dev-manual')


def _zl_frame(df):
    return zlib.compress(df.to_json(orient='split').encode())


# --- behaviour ---------------------------------------------------------------

def test_function_names_follow_branch(sdk):
    fn = sdk.functionNames
    assert fn.allQuery() == 'product-get-all-dev-manual'
    assert fn.listQuery() == 'product-get-list-dev-manual'
    assert fn.dumpToS3() == 'product-dump-s3-dev-manual'


def test_query_list_returns_body_instead_of_printing(sdk, capsys):
    body = [{'iprcode': '0171670'}]
    sdk.lambdaClient = FakeLambda({'product-get-list-dev-manual': _apigw(body)})
    assert sdk.queryList(['0171670']) == body
    call = sdk.lambdaClient.calls[0]
    assert json.loads(call['input']['body']) == {'iprcodes': ['0171670']}
    assert capsys.readouterr().out == ''


def test_retrieve_json_zl_decodes_dataframe(monkeypatch):
    df = pd.DataFrame({'iprcode': [171670, 9], 'pr_abb': ['KALE', 'WALKER']})
    monkeypatch.setattr(products.requests, 'get',
                        lambda url, **kw: FakeHttpResponse(200, _zl_frame(df)))
    out = retrieveJsonZl('https://example.invalid/all')
    pd.testing.assert_frame_equal(out, df)


def test_retrieve_json_zl_non_200_raises(monkeypatch):
    # vps-jg2 (merged in vps-896): a failed download raises ProductSdkError instead of printing and returning None
    monkeypatch.setattr(products.requests, 'get',
                        lambda url, **kw: FakeHttpResponse(403, payload={'error': 'denied'}))
    with pytest.raises(products.ProductSdkError) as caught:
        retrieveJsonZl('https://example.invalid/all')
    assert caught.value.statusCode == 403


def test_all_query_downloads_presigned_url(sdk, monkeypatch):
    df = pd.DataFrame({'iprcode': [1, 2], 'pr_abb': ['A', 'B']})
    sdk.lambdaClient = FakeLambda(
        {'product-get-all-dev-manual': _apigw({'url': 'https://example.invalid/x'})})
    seen = []

    def fake_get(url, **kw):  # up7 adds a timeout keyword
        seen.append(url)
        return FakeHttpResponse(200, _zl_frame(df))

    monkeypatch.setattr(products.requests, 'get', fake_get)
    pd.testing.assert_frame_equal(sdk.allQuery(), df)
    assert seen == ['https://example.invalid/x']


def test_update_with_s3_casts_intcols(sdk, monkeypatch):
    saved = {}

    def fake_save(key, objectToSave, bucket, user=None, pw=None):
        saved.update(key=key, data=objectToSave, bucket=bucket)

    monkeypatch.setattr(products.S3, 'save', fake_save)
    sdk.lambdaClient = FakeLambda({'product-update-s3-dev-manual': None})
    result = sdk.updateWithS3([{'iprcode': '0171670', 'pr_abb': 'KALE', 'pr_puqty': 1}],
                              inputKeyName='k1')
    # vps-jg2 (merged in vps-896): a structured result naming the key instead of the Slack string
    assert result['key'] == 'k1' and result['invocationType'] == 'Event' and result['result'] is None
    assert saved['bucket'] == 'input-product-bucket-dev-manual'
    assert saved['data'] == [{'iprcode': 171670, 'pr_abb': 'KALE', 'pr_puqty': '1'}]
    assert set(INTCOLS) >= {'iprcode', 'cprcode', 'oprcode'}


def test_sync_s3_returns_body(sdk):
    sdk.lambdaClient = FakeLambda({'product-dump-s3-dev-manual': _apigw({'ok': True})})
    assert sdk.syncS3() == {'ok': True}
