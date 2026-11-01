"""vps-3y4: the SDK's contract with the deployed product functions: their names for a branch and the payloads it
sends (tests/fixtures/contract.json). A recording fake Lambda client and a fake S3.save; s3bz is stubbed before the
SDK is imported, so no AWS call is made and the test does not depend on s3bz's pins."""
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

CONTRACT = json.loads((Path(__file__).parent / "fixtures" / "contract.json").read_text())


class RecordingLambda:
    """lambdasdk.Lambda's invoke, recorded: answers 200 with `body` (an Event invocation gets True, as lambdasdk returns)."""

    def __init__(self, body=None):
        self.body, self.calls = body if body is not None else {}, []

    def invoke(self, functionName, input, invocationType="RequestResponse"):
        self.calls.append({"functionName": functionName, "input": input, "invocationType": invocationType})
        if invocationType == "Event":
            return True
        return {"statusCode": 200, "body": json.dumps(self.body), "headers": {}}


@pytest.fixture
def products(monkeypatch):
    saved = []

    class S3:
        @staticmethod
        def save(key, objectToSave, bucket="", **kwargs):
            saved.append({"key": key, "bucket": bucket, "data": objectToSave})

    class Requests:
        @staticmethod
        def getContentFromUrl(url):
            return {"url": url}

    stub = types.ModuleType("s3bz.s3bz")
    stub.S3, stub.Requests = S3, Requests
    monkeypatch.setitem(sys.modules, "s3bz", types.ModuleType("s3bz"))
    monkeypatch.setitem(sys.modules, "s3bz.s3bz", stub)
    monkeypatch.delitem(sys.modules, "villaProductSdk.products", raising=False)
    module = importlib.import_module("villaProductSdk.products")
    module._saved = saved
    yield module
    sys.modules.pop("villaProductSdk.products", None)  # the next import gets the real s3bz, if installed


def sdk_for(products, body=None):
    sdk = products.ProductSdk(branch=CONTRACT["branch"])
    sdk.lambdaClient = RecordingLambda(body)
    return sdk


def body_of(call):
    """The JSON body of the API Gateway style event the SDK sent."""
    return json.loads(call["input"]["body"])


def test_function_names_for_branch(products):
    names = products.FunctionNames(branchName=CONTRACT["branch"])
    assert {name: getattr(names, name)() for name in CONTRACT["functionNames"]} == CONTRACT["functionNames"]
    assert products.ProductSdk(branch=CONTRACT["branch"]).functionNames.singleQuery() == CONTRACT["functionNames"]["singleQuery"]
    # every name the class offers is pinned: a new or renamed one must be added to the contract
    offered = {n for n in vars(products.FunctionNames) if not n.startswith("_")}
    assert offered == set(CONTRACT["functionNames"])


def test_query_single_product_payload(products):
    c = CONTRACT["querySingleProduct"]
    sdk = sdk_for(products, {"iprcode": c["iprcode"]})
    sdk.querySingleProduct(c["iprcode"])
    [call] = sdk.lambdaClient.calls
    assert call["functionName"] == c["functionName"] and call["invocationType"] == c["invocationType"]
    assert body_of(call) == c["body"]


def test_query_list_payload(products):
    c = CONTRACT["queryList"]
    sdk = sdk_for(products, [])
    sdk.queryList(c["iprcodes"])
    [call] = sdk.lambdaClient.calls
    assert call["functionName"] == c["functionName"] and call["invocationType"] == c["invocationType"]
    assert body_of(call) == c["body"]


@pytest.mark.parametrize("method", ["allQuery", "syncS3"])
def test_all_query_and_sync_send_an_empty_input(products, method):
    c = CONTRACT[method]
    sdk = sdk_for(products, {"url": "https://example.invalid/products"})
    try:
        getattr(sdk, method)()
    except Exception:
        pass  # what happens after the call (downloading the table) is not the contract
    call = sdk.lambdaClient.calls[0]
    assert call["functionName"] == c["functionName"] and call["input"] == c["input"]


def test_update_with_s3_payload_and_event_ack(products):
    c = CONTRACT["updateWithS3"]
    sdk = sdk_for(products)
    ack = sdk.updateWithS3([{"iprcode": "0171670", "cprcode": "0171670", "pr_abb": "KALE"}])
    [save] = products._saved
    [call] = sdk.lambdaClient.calls
    assert save["bucket"] == c["bucket"]
    assert call["functionName"] == c["functionName"] and call["invocationType"] == c["invocationType"]
    body = body_of(call)
    assert sorted(body) == c["bodyKeys"] and body["key"] == save["key"]  # the function loads exactly what was saved
    # the async call is acknowledged without waiting for the function: the legacy message, or (vps-jg2) a result
    # naming the uploaded key
    assert ack == "successfully sent event, please watch your slack" or (isinstance(ack, dict) and ack["key"] == save["key"])
