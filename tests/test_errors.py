'''ProductSdk raises ProductSdkError on Lambda failures (vps-b4r).

s3bz is stubbed in sys.modules, so these tests need no AWS access; the
Lambda client is replaced by a fake after the SDK is constructed.
'''
import importlib
import json
import sys
import types

import pytest


@pytest.fixture
def products(monkeypatch):
  s3bz = types.ModuleType('s3bz')
  s3bzInner = types.ModuleType('s3bz.s3bz')
  s3bzInner.S3 = type('S3', (), {})
  s3bzInner.Requests = type('Requests', (), {})
  s3bz.s3bz = s3bzInner
  monkeypatch.setitem(sys.modules, 's3bz', s3bz)
  monkeypatch.setitem(sys.modules, 's3bz.s3bz', s3bzInner)
  monkeypatch.delitem(sys.modules, 'villaProductSdk.products', raising=False)
  return importlib.import_module('villaProductSdk.products')


class FakeLambda:
  '''records calls; returns `response` or raises `error`'''
  def __init__(self, response=None, error=None):
    self.response = response
    self.error = error
    self.calls = []

  def invoke(self, functionName, input, **kwargs):
    self.calls.append((functionName, input))
    if self.error is not None:
      raise self.error
    return self.response


def apiResponse(statusCode, body):
  return {'statusCode': statusCode, 'body': json.dumps(body), 'headers': {}}


def makeSdk(products, fake):
  sdk = products.ProductSdk(branch='dev-test')
  sdk.lambdaClient = fake
  return sdk


def test_query_single_product_raises_on_invoke_error(products):
  sdk = makeSdk(products, FakeLambda(error=RuntimeError('AWS down')))
  with pytest.raises(products.ProductSdkError) as info:
    sdk.querySingleProduct('0171670')
  assert info.value.statusCode is None
  assert isinstance(info.value.__cause__, RuntimeError)
  assert sdk.lambdaClient.calls[0][0] == 'product-get-dev-test'


def test_query_single_product_raises_on_not_found(products):
  body = {'error': 'product not found'}
  sdk = makeSdk(products, FakeLambda(response=apiResponse(404, body)))
  with pytest.raises(products.ProductSdkError) as info:
    sdk.querySingleProduct('3203290')
  assert info.value.statusCode == 404
  assert info.value.body == body


def test_query_single_product_returns_body_on_200(products):
  body = {'iprcode': '0171670'}
  sdk = makeSdk(products, FakeLambda(response=apiResponse(200, body)))
  assert sdk.querySingleProduct('0171670') == body
  sentBody = json.loads(sdk.lambdaClient.calls[0][1]['body'])
  assert sentBody == {'iprcode': '0171670'}


def test_general_invoke_raises_on_non_200(products):
  body = {'error': 'internal'}
  sdk = makeSdk(products, FakeLambda(response=apiResponse(500, body)))
  with pytest.raises(products.ProductSdkError) as info:
    sdk.generalInvoke('product-get-list-dev-test', {})
  assert info.value.statusCode == 500
  assert info.value.body == body


def test_general_invoke_raises_on_unparseable_response(products):
  raw = {'errorMessage': 'Task timed out', 'errorType': 'TimeoutError'}
  sdk = makeSdk(products, FakeLambda(response=raw))
  with pytest.raises(products.ProductSdkError) as info:
    sdk.generalInvoke('product-get-list-dev-test', {})
  assert info.value.statusCode is None
  assert info.value.body == raw  # the raw response is kept intact


def test_return_lambda_response_raises_on_unparseable(products):
  with pytest.raises(products.ProductSdkError):
    products.ProductSdk.returnLambdaResponse({'errorMessage': 'boom'})


def test_query_list_returns_body_on_200(products):
  body = [{'iprcode': '0217153'}, {'iprcode': '203915'}]
  sdk = makeSdk(products, FakeLambda(response=apiResponse(200, body)))
  assert sdk.queryList(['0217153', '203915']) == body
  functionName, payload = sdk.lambdaClient.calls[0]
  assert functionName == 'product-get-list-dev-test'
  assert json.loads(payload['body']) == {'iprcodes': ['0217153', '203915']}


def test_query_list_raises_on_non_200(products):
  sdk = makeSdk(products, FakeLambda(response=apiResponse(400, {'error': 'bad'})))
  with pytest.raises(products.ProductSdkError) as info:
    sdk.queryList(['x'])
  assert info.value.statusCode == 400
