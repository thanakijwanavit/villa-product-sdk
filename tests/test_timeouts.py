"""vps-up7: no call can hang a caller forever. The Lambda client has connect/read timeouts and standard retries,
and allQuery's download has a timeout. Offline: s3bz is stubbed, keys are dummies, requests.get and the invoke are
fakes."""
import bz2
import importlib
import json
import sys
import types

import pytest


@pytest.fixture
def products(monkeypatch):
    stub = types.ModuleType("s3bz.s3bz")
    stub.S3, stub.Requests = type("S3", (), {}), type("Requests", (), {})
    monkeypatch.setitem(sys.modules, "s3bz", types.ModuleType("s3bz"))
    monkeypatch.setitem(sys.modules, "s3bz.s3bz", stub)
    monkeypatch.delitem(sys.modules, "villaProductSdk.products", raising=False)
    yield importlib.import_module("villaProductSdk.products")
    sys.modules.pop("villaProductSdk.products", None)


def test_lambda_client_has_timeouts_and_retries(products):
    sdk = products.ProductSdk(branch="dev-manual", user="AKIADUMMYDUMMYDUMMY0", pw="dummy-secret")
    config = sdk.lambdaClient.lambdaClient.meta.config
    assert (config.connect_timeout, config.read_timeout) == (10, 30)
    # products.py passes max_attempts=3 (botocore: retries after the first try), which botocore stores as
    # total_max_attempts=4
    assert config.retries == {"mode": "standard", "total_max_attempts": 4}
    assert sdk.lambdaClient.lambdaClient.meta.region_name == "ap-southeast-1"
    custom = products.ProductSdk(connect_timeout=2, read_timeout=5, region="ap-southeast-2").lambdaClient.lambdaClient
    assert (custom.meta.config.connect_timeout, custom.meta.config.read_timeout) == (2, 5)
    assert custom.meta.region_name == "ap-southeast-2"
    # lambdasdk's invoke still drives the replaced client
    assert hasattr(sdk.lambdaClient, "invoke") and sdk.lambdaClient.lambdaClient.meta.service_model.service_name == "lambda"


def test_all_query_download_uses_timeout(products, monkeypatch):
    table = {"columns": ["iprcode"], "data": [["0171670"]]}
    seen = []

    class Answer:
        ok, status_code = True, 200
        content = bz2.compress(json.dumps(table).encode())

    def get(url, **kwargs):
        seen.append({"url": url, **kwargs})
        return Answer()

    monkeypatch.setattr(products.requests, "get", get)
    sdk = products.ProductSdk(read_timeout=12)

    class Invoke:
        def invoke(self, functionName, input, invocationType="RequestResponse"):
            assert functionName == "product-get-all-dev-manual"
            return {"statusCode": 200, "body": json.dumps({"url": "https://dump.example.invalid/all"}), "headers": {}}

    sdk.lambdaClient = Invoke()
    assert sdk.allQuery() == table  # the same decode as before: bz2, then json
    assert seen == [{"url": "https://dump.example.invalid/all", "timeout": (10, 12)}]
