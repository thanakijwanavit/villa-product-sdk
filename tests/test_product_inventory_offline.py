"""Offline behaviour tests for villaProductSdk.inventory (vps-l7s).

This is the older copy of the SDK class that products.py replaced. It is still shipped,
and vps-jg2 does not change it, so these tests pin today's behaviour, error paths
included. No AWS: lambdasdk and s3bz are the recording fakes in conftest.py.
"""
import json
import logging

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
}
KALE = {"cprcode": "0171670", "iprcode": "0171670", "oprcode": "0171670",
        "ordertype": "Y", "pr_abb": "JIRAPAT YOUNG KALE 2"}


@pytest.fixture
def inventory(load_sdk):
    return load_sdk("villaProductSdk.inventory")


@pytest.fixture
def sdk(inventory):
    return inventory.ProductSdk(branch=BRANCH, user="test-user", pw="test-pw")


def sent_body(invocation):
    return json.loads(invocation["input"]["body"])


def lambda_error(operation):
    return ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                       operation)


@pytest.mark.parametrize("method, expected", sorted(NAMES.items()))
def test_function_names_for_a_branch(inventory, method, expected):
    assert getattr(inventory.FunctionNames(branchName=BRANCH), method)() == expected


def test_every_function_name_is_tested(inventory):
    names = {n for n in vars(inventory.FunctionNames) if not n.startswith("_")}
    assert names == set(NAMES)


def test_constructor_builds_the_lambda_client_and_calls_nothing(inventory, fake_aws):
    sdk = inventory.ProductSdk(branch=BRANCH, user="u", pw="p", region="us-east-1")
    assert fake_aws.clients == [{"user": "u", "pw": "p", "sessionToken": None,
                                 "region": "us-east-1"}]
    assert sdk.functionNames.branchName == BRANCH
    assert fake_aws.calls == []


def test_constructor_defaults(inventory, fake_aws):
    assert inventory.ProductSdk().branchName == "dev-manual"
    assert fake_aws.clients == [{"user": None, "pw": None, "sessionToken": None,
                                 "region": "ap-southeast-1"}]


def test_update_with_s3_saves_the_data_then_invokes_ingestion_with_its_key(sdk, fake_aws):
    data = [KALE]
    fake_aws.respond("product-update-s3-feature-x", body={"success": 1, "failure": 0})
    assert sdk.updateWithS3(data, inputKeyName="upload-1") == {"success": 1, "failure": 0}
    assert fake_aws.saves == [{"key": "upload-1", "objectToSave": data,
                               "bucket": "input-product-bucket-feature-x",
                               "user": "test-user", "pw": "test-pw"}]
    assert fake_aws.saves[0]["objectToSave"] is data
    [call] = fake_aws.invocations
    assert call["functionName"] == "product-update-s3-feature-x"
    assert sent_body(call) == {"key": "upload-1"}
    assert call["invocationType"] == "RequestResponse"
    assert [kind for kind, _ in fake_aws.calls] == ["s3.save", "invoke"]


def test_update_with_s3_tells_ingestion_the_key_it_saved_under_by_default(sdk, fake_aws):
    fake_aws.respond("product-update-s3-feature-x", body={"success": 1})
    sdk.updateWithS3([KALE])
    [save] = fake_aws.saves
    [call] = fake_aws.invocations
    assert sent_body(call) == {"key": save["key"]}


def test_update_with_s3_writes_with_other_credentials_when_given(sdk, fake_aws):
    sdk.updateWithS3([KALE], inputKeyName="k", invocationType="Event",
                     user="other-user", pw="other-pw")
    [save] = fake_aws.saves
    assert (save["user"], save["pw"]) == ("other-user", "other-pw")
    assert fake_aws.invocations[0]["invocationType"] == "Event"


def test_query_single_product_sends_the_iprcode_to_product_get(sdk, fake_aws):
    fake_aws.respond("product-get-feature-x", body=KALE)
    assert sdk.querySingleProduct("0171670") == KALE
    [call] = fake_aws.invocations
    assert call["functionName"] == "product-get-feature-x"
    assert sent_body(call) == {"iprcode": "0171670"}
    assert call["invocationType"] == "RequestResponse"


def test_all_query_downloads_the_url_that_product_get_all_returns(sdk, fake_aws):
    url = "https://example.invalid/product-dump.bz2"
    fake_aws.respond("product-get-all-feature-x", body={"url": url})
    fake_aws.serve(url, {"0171670": KALE})
    assert sdk.allQuery() == {"0171670": KALE}
    assert fake_aws.invocations == [{"functionName": "product-get-all-feature-x", "input": {},
                                     "invocationType": "RequestResponse"}]
    assert fake_aws.downloads == [url]


def test_sync_s3_invokes_the_dump_function_and_returns_the_raw_response(sdk, fake_aws):
    raw = {"statusCode": 200, "body": json.dumps({"result": "saved 10929 products"})}
    fake_aws.respond("product-dump-s3-feature-x", raw=raw)
    assert sdk.syncS3() == raw  # unlike products.py, the body is not parsed
    assert fake_aws.invocations == [{"functionName": "product-dump-s3-feature-x", "input": {},
                                     "invocationType": "RequestResponse"}]


def test_return_lambda_response_returns_the_parsed_body(inventory):
    response = {"statusCode": 200, "body": json.dumps(KALE)}
    assert inventory.ProductSdk.returnLambdaResponse(response) == KALE


def test_return_lambda_response_logs_and_returns_none_when_it_cannot_parse(inventory, caplog):
    with caplog.at_level(logging.ERROR):
        assert inventory.ProductSdk.returnLambdaResponse({"statusCode": 502}) is None
    assert "error parsing body" in caplog.text


def test_print_first_returns_the_first_item(inventory):
    assert inventory.ProductSdk.printFirst({"b": 2, "a": 1}) == ("b", 2)


FAILING_CALLS = {
    "updateWithS3": ("product-update-s3-feature-x",
                     lambda sdk: sdk.updateWithS3([KALE], inputKeyName="k")),
    "querySingleProduct": ("product-get-feature-x", lambda sdk: sdk.querySingleProduct("1")),
    "allQuery": ("product-get-all-feature-x", lambda sdk: sdk.allQuery()),
    "syncS3": ("product-dump-s3-feature-x", lambda sdk: sdk.syncS3()),
}


@pytest.mark.parametrize("method", sorted(FAILING_CALLS))
def test_a_failed_invoke_propagates_unchanged(sdk, fake_aws, method):
    function_name, call = FAILING_CALLS[method]
    original = lambda_error("Invoke")
    fake_aws.respond(function_name, error=original)
    with pytest.raises(ClientError) as excinfo:
        call(sdk)
    assert excinfo.value is original


def test_update_with_s3_raises_and_does_not_invoke_when_the_save_fails(sdk, fake_aws):
    original = lambda_error("PutObject")
    fake_aws.fail_saves_with = original
    with pytest.raises(ClientError) as excinfo:
        sdk.updateWithS3([KALE], inputKeyName="k")
    assert excinfo.value is original
    assert fake_aws.invocations == []
