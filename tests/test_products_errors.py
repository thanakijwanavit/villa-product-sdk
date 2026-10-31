"""vps-jg2: products.py raises a typed ProductSdkError instead of printing and returning None or the error body,
and updateWithS3 uploads each call under its own key. Offline: the Lambda client and S3 are stubbed."""
import ast
import json
import threading
from pathlib import Path

import pytest

from villaProductSdk import products
from villaProductSdk.products import InvocationType, ProductSdk, ProductSdkError

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "villaProductSdk" / "products.py"


def ok(body, status=200):
    return {"statusCode": status, "body": json.dumps(body), "headers": {}}


class FakeLambda:
    """Stands in for lambdasdk.Lambda: answers from a script (an exception is raised) and keeps the calls."""

    def __init__(self, *answers):
        self.answers, self.calls, self.lock = list(answers), [], threading.Lock()

    def invoke(self, functionName, input, invocationType="RequestResponse"):
        with self.lock:
            self.calls.append({"functionName": functionName, "input": input, "invocationType": invocationType})
            answer = self.answers.pop(0) if self.answers else ok({"ok": True})
        if isinstance(answer, BaseException):
            raise answer
        return True if invocationType == "Event" else answer


@pytest.fixture
def sdk():
    s = ProductSdk(branch="dev-manual")
    s.lambdaClient = FakeLambda()
    return s


@pytest.fixture
def saved(monkeypatch):
    store, lock = [], threading.Lock()

    def save(key, objectToSave, bucket="", **kwargs):
        with lock:
            store.append({"key": key, "bucket": bucket, "data": objectToSave})

    monkeypatch.setattr(products.S3, "save", staticmethod(save))
    return store


# ------------------------------------------------------------------ errors are raised, typed
def test_a_non_200_answer_raises_with_status_function_and_body(sdk):
    sdk.lambdaClient = FakeLambda(ok({"error": "product not found"}, status=404))
    with pytest.raises(ProductSdkError) as caught:
        sdk.querySingleProduct("3203290")
    e = caught.value
    assert e.statusCode == 404 and e.functionName == "product-get-dev-manual" and e.body == {"error": "product not found"}
    assert "product-get-dev-manual" in str(e) and "404" in str(e)


@pytest.mark.parametrize("answer", [
    {"errorMessage": "Task timed out after 30.00 seconds", "errorType": "TimeoutError"},  # a function error has no body
    {"statusCode": 200, "body": "not json {"},
    None,
    "a plain string",
])
def test_an_unparseable_answer_raises(sdk, answer):
    sdk.lambdaClient = FakeLambda(answer)
    with pytest.raises(ProductSdkError) as caught:
        sdk.queryList(["0217153"])
    assert caught.value.functionName == "product-get-list-dev-manual"


def test_a_failed_invoke_raises_and_keeps_the_cause(sdk):
    boom = ConnectionError("endpoint unreachable")
    sdk.lambdaClient = FakeLambda(boom)
    with pytest.raises(ProductSdkError) as caught:
        sdk.querySingleProduct("0171670")  # used to print 'calling lambda failed' and return None
    assert caught.value.functionName == "product-get-dev-manual" and caught.value.__cause__ is boom


def test_general_invoke_no_longer_returns_the_error_body_as_data(sdk):
    sdk.lambdaClient = FakeLambda(ok({"error": "bad input"}, status=400))
    with pytest.raises(ProductSdkError) as caught:
        sdk.generalInvoke("product-get-list-dev-manual", {})
    assert caught.value.statusCode == 400


def test_return_lambda_response_raises_instead_of_returning_none():
    with pytest.raises(ProductSdkError):
        ProductSdk.returnLambdaResponse({"no": "body"})
    assert ProductSdk.returnLambdaResponse(ok({"a": 1})) == {"a": 1}


def test_success_paths_return_the_body_and_do_not_mutate_the_response(sdk):
    answer = ok({"iprcode": "0171670"})
    sdk.lambdaClient = FakeLambda(answer, ok([{"iprcode": "1"}]), ok({"synced": True}))
    assert sdk.querySingleProduct("0171670") == {"iprcode": "0171670"}
    assert "body" in answer  # awsSchema's fromDict pops 'body': the sdk parses a copy
    assert sdk.queryList(["1"]) == [{"iprcode": "1"}]
    assert sdk.syncS3() == {"synced": True}
    assert [c["functionName"] for c in sdk.lambdaClient.calls] == ["product-get-dev-manual", "product-get-list-dev-manual",
                                                                    "product-dump-s3-dev-manual"]


def test_all_query_raises_when_the_url_call_fails(sdk):
    sdk.lambdaClient = FakeLambda(ok({"error": "x"}, status=500))
    with pytest.raises(ProductSdkError):
        sdk.allQuery()


# ------------------------------------------------------------------ updateWithS3
PRODUCTS = [{"iprcode": "0171670", "cprcode": "0171670", "pr_abb": "KALE"}]


def test_two_concurrent_uploads_use_different_keys_and_each_invokes_with_its_own(sdk, saved):
    results, barrier = [], threading.Barrier(2)

    def upload():
        barrier.wait()
        results.append(sdk.updateWithS3(PRODUCTS))

    threads = [threading.Thread(target=upload) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    keys = {r["key"] for r in results}
    assert len(keys) == 2 and all(k.startswith("input-data-name-") for k in keys)
    assert {s["key"] for s in saved} == keys
    assert {json.loads(c["input"]["body"])["key"] for c in sdk.lambdaClient.calls} == keys


def test_the_async_path_returns_a_structured_result_not_the_slack_string(sdk, saved):
    result = sdk.updateWithS3(PRODUCTS)
    assert result == {"key": saved[0]["key"], "bucket": "input-product-bucket-dev-manual",
                      "functionName": "product-update-s3-dev-manual", "invocationType": "Event", "result": None}
    assert sdk.lambdaClient.calls[0]["invocationType"] == "Event"
    assert saved[0]["data"] == [{"iprcode": 171670, "cprcode": 171670, "pr_abb": "KALE"}]


def test_an_explicit_key_is_honoured_and_the_sync_path_returns_the_body(sdk, saved):
    sdk.lambdaClient = FakeLambda(ok({"updated": 1}))
    result = sdk.updateWithS3(PRODUCTS, inputKeyName="my-key", invocationType=InvocationType.requestResponse)
    assert result["key"] == "my-key" and saved[0]["key"] == "my-key" and result["result"] == {"updated": 1}


def test_a_failed_ingestion_or_upload_raises(sdk, saved, monkeypatch):
    sdk.lambdaClient = FakeLambda(ok({"error": "bad rows"}, status=400))
    with pytest.raises(ProductSdkError) as caught:
        sdk.updateWithS3(PRODUCTS, invocationType=InvocationType.requestResponse)
    assert caught.value.statusCode == 400 and caught.value.body == {"error": "bad rows"}

    def broken(**kwargs):
        raise PermissionError("AccessDenied")

    monkeypatch.setattr(products.S3, "save", staticmethod(broken))
    with pytest.raises(ProductSdkError):
        sdk.updateWithS3(PRODUCTS)


# ------------------------------------------------------------------ the source itself
def test_no_bare_except_and_no_print_in_products_py():
    tree = ast.parse(LIB.read_text())
    bare = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and n.type is None]
    prints = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
    assert bare == [] and prints == []


def test_event_and_response_come_from_one_module():
    tree = ast.parse(LIB.read_text())
    sources = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in ("Event", "Response"):
                    sources.setdefault(alias.name, []).append(node.module)
    assert sources == {"Event": ["awsSchema.apigateway"], "Response": ["awsSchema.apigateway"]}


def test_the_library_matches_the_notebook():
    """Every #export cell of product-sdk.ipynb is in products.py, and products.py has nothing else (nbdev_build_lib)."""
    nb = json.loads((ROOT / "product-sdk.ipynb").read_text())
    exported = ["".join(c["source"]).split("\n", 1)[1] for c in nb["cells"]
                if c["cell_type"] == "code" and "".join(c["source"]).startswith("#export")]
    cells = LIB.read_text().split("# Cell\n")[1:]
    norm = lambda text: "\n".join(line.rstrip() for line in text.strip().splitlines())  # nbdev drops trailing spaces
    assert [norm(c) for c in cells] == [norm(e) for e in exported]


def test_the_version_is_bumped_with_a_changelog_line():
    import villaProductSdk

    version = next(l.split("=")[1].strip() for l in (ROOT / "settings.ini").read_text().splitlines() if l.startswith("version"))
    assert villaProductSdk.__version__ == version == "0.1.0"
    assert "## 0.1.0" in (ROOT / "CHANGELOG.md").read_text()
