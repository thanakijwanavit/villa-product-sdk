"""Offline behaviour tests for villaProductSdk.products (vps-l7s).

No AWS: lambdasdk and s3bz are replaced by the recording fakes in conftest.py, and the
autouse offline_guard fails any test that tries a real boto3, requests or socket call.

Error paths are asserted only where vps-jg2 (typed ProductSdkError, unique upload keys)
keeps today's behaviour: a failure raises, and the raised error carries the original
one. Not asserted here, because vps-jg2 changes them: the error body that generalInvoke
returns for a non-200 response, the None that querySingleProduct and
returnLambdaResponse return on failure, updateWithS3's fixed default key and its return
values.
"""
import json

import pytest
from botocore.exceptions import ClientError

BRANCH = "feature-x"
NAMES = {
    "dumpToS3": "product-dump-s3-feature-x",
    "updateProduct": "product-update-feature-x",
    "updateS3": "product-update-s3-feature-x",
    "singleQuery": "product-get-feature-x",
    "allQuery": "product-get-all-feature-x",
    "inputBucket": "input-product-bucket-feature-x",
    "inventoryBucket": "product-bucket-feature-x",
    "listQuery": "product-get-list-feature-x",
}
KALE = {"cprcode": "0171670", "iprcode": "0171670", "oprcode": "0171670",
        "ordertype": "Y", "pr_abb": "JIRAPAT YOUNG KALE 2"}
PUZZLE = {"cprcode": "0235141", "iprcode": "0235141", "oprcode": "0235141",
          "ordertype": "Y", "pr_abb": "EEBOO-PZCT3-PUZZLE"}


@pytest.fixture
def products(load_sdk):
    return load_sdk("villaProductSdk.products")


@pytest.fixture
def sdk(products):
    return products.ProductSdk(branch=BRANCH, user="test-user", pw="test-pw")


def sent_body(invocation):
    """The JSON body of the API Gateway-style event the SDK sent."""
    return json.loads(invocation["input"]["body"])


def lambda_error(operation):
    return ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                       operation)


def carries(excinfo, original):
    """True if the raised exception is ``original`` or was raised from or during it."""
    error = excinfo.value
    while error is not None:
        if error is original:
            return True
        error = error.__cause__ or error.__context__
    return False


# --- FunctionNames and the constructor ---------------------------------------------

@pytest.mark.parametrize("method, expected", sorted(NAMES.items()))
def test_function_names_for_a_branch(products, method, expected):
    assert getattr(products.FunctionNames(branchName=BRANCH), method)() == expected


def test_every_function_name_is_tested(products):
    names = {n for n in vars(products.FunctionNames) if not n.startswith("_")}
    assert names == set(NAMES)


def test_function_names_default_to_dev_manual(products):
    names = products.FunctionNames()
    assert {m: getattr(names, m)() for m in NAMES} == {
        m: n.replace(BRANCH, "dev-manual") for m, n in NAMES.items()}


def test_constructor_builds_the_lambda_client_and_calls_nothing(products, fake_aws):
    sdk = products.ProductSdk(branch=BRANCH, user="u", pw="p", region="us-east-1")
    assert fake_aws.clients == [{"user": "u", "pw": "p", "sessionToken": None,
                                 "region": "us-east-1"}]
    assert sdk.functionNames.singleQuery() == "product-get-feature-x"
    assert fake_aws.calls == []


def test_constructor_defaults(products, fake_aws):
    sdk = products.ProductSdk()
    assert sdk.branchName == "dev-manual"
    assert fake_aws.clients == [{"user": None, "pw": None, "sessionToken": None,
                                 "region": "ap-southeast-1"}]


# --- the SDK methods ----------------------------------------------------------------

def test_general_invoke_returns_the_body_of_a_200_response(sdk, fake_aws):
    fake_aws.respond("some-function", body={"ok": True, "items": [1, 2]})
    payload = {"body": json.dumps({"q": 1})}
    assert sdk.generalInvoke(functionName="some-function", payload=payload) == {
        "ok": True, "items": [1, 2]}
    assert fake_aws.invocations == [{"functionName": "some-function", "input": payload,
                                     "invocationType": "RequestResponse"}]


def test_query_single_product_sends_the_iprcode_to_product_get(sdk, fake_aws):
    fake_aws.respond("product-get-feature-x", body=KALE)
    assert sdk.querySingleProduct("0171670") == KALE
    [call] = fake_aws.invocations
    assert call["functionName"] == "product-get-feature-x"
    assert sent_body(call) == {"iprcode": "0171670"}
    assert call["invocationType"] == "RequestResponse"


def test_query_list_sends_the_iprcodes_to_product_get_list(sdk, fake_aws):
    fake_aws.respond("product-get-list-feature-x", body=[KALE, PUZZLE])
    assert sdk.queryList(["0171670", "0235141"]) == [KALE, PUZZLE]
    [call] = fake_aws.invocations
    assert call["functionName"] == "product-get-list-feature-x"
    assert sent_body(call) == {"iprcodes": ["0171670", "0235141"]}
    assert call["invocationType"] == "RequestResponse"


def test_all_query_downloads_the_url_that_product_get_all_returns(sdk, fake_aws):
    url = "https://example.invalid/product-dump.bz2"  # only the fake Requests sees it
    fake_aws.respond("product-get-all-feature-x", body={"url": url})
    fake_aws.serve(url, {"0171670": KALE, "0235141": PUZZLE})
    assert sdk.allQuery() == {"0171670": KALE, "0235141": PUZZLE}
    assert fake_aws.invocations == [{"functionName": "product-get-all-feature-x", "input": {},
                                     "invocationType": "RequestResponse"}]
    assert fake_aws.downloads == [url]


def test_update_with_s3_saves_the_data_then_invokes_ingestion_with_its_key(sdk, fake_aws):
    data = [KALE, PUZZLE]
    fake_aws.respond("product-update-s3-feature-x", body={"success": 2, "failure": 0})
    sdk.updateWithS3(data, inputKeyName="upload-1", invocationType="RequestResponse")
    [save] = fake_aws.saves
    assert save["bucket"] == "input-product-bucket-feature-x"
    assert save["key"] == "upload-1"
    assert save["objectToSave"] is data
    [call] = fake_aws.invocations
    assert call["functionName"] == "product-update-s3-feature-x"
    assert sent_body(call)["key"] == "upload-1"
    assert call["invocationType"] == "RequestResponse"
    assert [kind for kind, _ in fake_aws.calls] == ["s3.save", "invoke"]


def test_update_with_s3_tells_ingestion_the_key_it_saved_under_by_default(sdk, fake_aws):
    """Holds for today's fixed default key and for vps-jg2's unique key per call."""
    sdk.updateWithS3([KALE])
    [save] = fake_aws.saves
    [call] = fake_aws.invocations
    assert save["bucket"] == "input-product-bucket-feature-x"
    assert call["functionName"] == "product-update-s3-feature-x"
    assert sent_body(call)["key"] == save["key"]


def test_update_with_s3_writes_with_the_sdk_credentials_unless_given_others(sdk, fake_aws):
    sdk.updateWithS3([KALE], inputKeyName="k1")
    sdk.updateWithS3([KALE], inputKeyName="k2", user="other-user", pw="other-pw")
    assert [(s["user"], s["pw"]) for s in fake_aws.saves] == [
        ("test-user", "test-pw"), ("other-user", "other-pw")]


def test_sync_s3_invokes_the_dump_function_and_returns_its_body(sdk, fake_aws):
    fake_aws.respond("product-dump-s3-feature-x", body={"result": "saved 10929 products"})
    assert sdk.syncS3() == {"result": "saved 10929 products"}
    assert fake_aws.invocations == [{"functionName": "product-dump-s3-feature-x", "input": {},
                                     "invocationType": "RequestResponse"}]


def test_return_lambda_response_returns_the_parsed_body(products):
    response = {"statusCode": 200, "body": json.dumps(KALE)}
    assert products.ProductSdk.returnLambdaResponse(response) == KALE


def test_print_first_returns_the_first_item(products):
    assert products.ProductSdk.printFirst({"0235141": PUZZLE, "0171670": KALE}) == (
        "0235141", PUZZLE)


def test_products_from_list_round_trips(products):
    assert products.ProductsFromList.from_dict({"iprcodes": ["0171670"]}).to_dict() == {
        "iprcodes": ["0171670"]}


# --- error paths that vps-jg2 keeps ---------------------------------------------------

FAILING_CALLS = {
    "generalInvoke": ("some-function", lambda sdk: sdk.generalInvoke("some-function", {})),
    "queryList": ("product-get-list-feature-x", lambda sdk: sdk.queryList(["0171670"])),
    "allQuery": ("product-get-all-feature-x", lambda sdk: sdk.allQuery()),
    "syncS3": ("product-dump-s3-feature-x", lambda sdk: sdk.syncS3()),
    "updateWithS3": ("product-update-s3-feature-x",
                     lambda sdk: sdk.updateWithS3([KALE], inputKeyName="k")),
}


@pytest.mark.parametrize("method", sorted(FAILING_CALLS))
def test_a_failed_invoke_raises(sdk, fake_aws, method):
    function_name, call = FAILING_CALLS[method]
    original = lambda_error("Invoke")
    fake_aws.respond(function_name, error=original)
    with pytest.raises(Exception) as excinfo:
        call(sdk)
    assert carries(excinfo, original)


@pytest.mark.parametrize("raw", [{"statusCode": 200}, {"statusCode": 200, "body": "not json"}],
                         ids=["no body", "body is not JSON"])
def test_general_invoke_raises_on_an_unparseable_response(sdk, fake_aws, raw):
    fake_aws.respond("some-function", raw=raw)
    with pytest.raises(Exception) as excinfo:
        sdk.generalInvoke("some-function", {})
    assert not isinstance(excinfo.value, AssertionError)  # not the fakes complaining
    assert [c["functionName"] for c in fake_aws.invocations] == ["some-function"]


def test_all_query_raises_and_downloads_nothing_without_a_url(sdk, fake_aws):
    fake_aws.respond("product-get-all-feature-x", body={"error": "no dump yet"})
    with pytest.raises(Exception) as excinfo:
        sdk.allQuery()
    assert not isinstance(excinfo.value, AssertionError)
    assert fake_aws.downloads == []


def test_update_with_s3_raises_and_does_not_invoke_when_the_save_fails(sdk, fake_aws):
    original = lambda_error("PutObject")
    fake_aws.fail_saves_with = original
    with pytest.raises(Exception) as excinfo:
        sdk.updateWithS3([KALE], inputKeyName="k", invocationType="RequestResponse")
    assert carries(excinfo, original)
    assert fake_aws.invocations == []
