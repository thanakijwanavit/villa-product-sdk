"""vps-9he: villaProductSdk.inventory no longer hides errors behind a bare except.

returnLambdaResponse used to catch everything (KeyboardInterrupt and SystemExit too), log the whole lambda
response and return None. It now raises the SDK's typed ProductSdkError, as villaProductSdk.products does.
Offline: the Lambda client and S3 are stubbed.
"""
import json
import logging

import pytest

from villaProductSdk import inventory
from villaProductSdk.inventory import ProductSdk
from villaProductSdk.products import ProductSdkError


def ok(body, status=200):
    return {"statusCode": status, "body": json.dumps(body), "headers": {}}


class FakeLambda:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def invoke(self, functionName, input, invocationType="RequestResponse"):
        self.calls.append(functionName)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


@pytest.fixture
def sdk():
    return ProductSdk(branch="dev-manual")


def test_a_200_answer_returns_the_body(sdk):
    sdk.lambdaClient = FakeLambda(ok({"iprcode": "0171670", "name": "Kale"}))
    assert sdk.querySingleProduct("0171670") == {"iprcode": "0171670", "name": "Kale"}
    assert sdk.lambdaClient.calls == ["product-get-dev-manual"]


@pytest.mark.parametrize("answer, message", [
    ({"statusCode": 200, "headers": {}}, "has no body"),
    (None, "has no body"),
    ({"statusCode": 200, "body": "{not json", "headers": {}}, "could not be parsed"),
    (ok({"error": "product not found"}, status=404), "answered with an error"),
], ids=["no-body", "none", "bad-json", "404"])
def test_bad_answers_raise_product_sdk_error_naming_the_function(sdk, answer, message):
    sdk.lambdaClient = FakeLambda(answer)
    with pytest.raises(ProductSdkError) as caught:
        sdk.querySingleProduct("0171670")
    assert message in str(caught.value)
    assert caught.value.functionName == "product-get-dev-manual"


def test_the_404_keeps_status_and_body(sdk):
    sdk.lambdaClient = FakeLambda(ok({"error": "product not found"}, status=404))
    with pytest.raises(ProductSdkError) as caught:
        sdk.querySingleProduct("3203290")
    assert caught.value.statusCode == 404 and caught.value.body == {"error": "product not found"}


def test_update_with_s3_raises_too(sdk, monkeypatch):
    monkeypatch.setattr(inventory.S3, "save", staticmethod(lambda **kwargs: None))
    sdk.lambdaClient = FakeLambda({"statusCode": 200, "headers": {}})
    with pytest.raises(ProductSdkError) as caught:
        sdk.updateWithS3([{"iprcode": "1"}])
    assert caught.value.functionName == "product-update-s3-dev-manual"


def test_the_whole_response_is_no_longer_logged(sdk, caplog):
    sdk.lambdaClient = FakeLambda({"statusCode": 500, "body": "{bad", "headers": {"x-secret-ish": "do-not-log"}})
    with caplog.at_level(logging.DEBUG), pytest.raises(ProductSdkError):
        sdk.querySingleProduct("0171670")
    assert "do-not-log" not in caplog.text


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_an_interrupt_while_parsing_is_not_swallowed(sdk, monkeypatch, interrupt):
    def stop(_):
        raise interrupt()

    monkeypatch.setattr("villaProductSdk.products.Response.fromDict", staticmethod(stop))
    with pytest.raises(interrupt):
        ProductSdk.returnLambdaResponse(ok({"a": 1}))


def test_real_api_gateway_answers_with_headers_parse(sdk, monkeypatch):
    """The old parser was villaProductSdk.schema.Response, which knows 'header' but not API Gateway's 'headers': a
    real 200 raised TypeError inside the bare except and came back as None (querySingleProduct, updateWithS3) or
    as a raw TypeError (allQuery)."""
    sdk.lambdaClient = FakeLambda({"statusCode": 200, "headers": {"content-type": "application/json"},
                                   "body": json.dumps({"url": "https://example.invalid/all"})})
    monkeypatch.setattr(inventory.Requests, "getContentFromUrl", staticmethod(lambda url: {"from": url}))
    assert sdk.allQuery() == {"from": "https://example.invalid/all"}
    assert sdk.lambdaClient.calls == ["product-get-all-dev-manual"]


def test_all_query_error_is_typed(sdk):
    sdk.lambdaClient = FakeLambda(ok({"error": "boom"}, status=500))
    with pytest.raises(ProductSdkError) as caught:
        sdk.allQuery()
    assert caught.value.functionName == "product-get-all-dev-manual" and caught.value.statusCode == 500
