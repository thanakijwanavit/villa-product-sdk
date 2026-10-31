"""Offline behaviour tests for villaInventorySdk.inventory (vps-l7s).

The single-product query's Lambda name (FunctionNames.singleQuery) is left to vps-6fo,
which fixes it: these tests check that querySingleProduct invokes whatever singleQuery()
names, and do not pin today's name. No AWS: lambdasdk and s3bz are the recording fakes
in conftest.py.
"""
import pytest
from botocore.exceptions import ClientError

BRANCH = "feature-x"
NAMES = {  # every FunctionNames method except singleQuery (vps-6fo)
    "dumpToS3": "product-dump-s3-feature-x",
    "updateProduct": "product-update-feature-x",
    "updateS3": "product-update-s3-feature-x",
    "allQuery": "product-get-all-feature-x",
    "inputBucket": "input-product-bucket-feature-x",
    "inventoryBucket": "product-bucket-feature-x",
}
KALE = {"cprcode": "0171670", "iprcode": "0171670", "oprcode": "0171670",
        "ordertype": "Y", "pr_abb": "JIRAPAT YOUNG KALE 2"}


@pytest.fixture
def inventory(load_sdk):
    return load_sdk("villaInventorySdk.inventory")


@pytest.fixture
def sdk(inventory):
    return inventory.ProductSdk(branch=BRANCH, user="test-user", pw="test-pw")


def lambda_error(operation):
    return ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                       operation)


@pytest.mark.parametrize("method, expected", sorted(NAMES.items()))
def test_function_names_for_a_branch(inventory, method, expected):
    assert getattr(inventory.FunctionNames(branchName=BRANCH), method)() == expected


def test_every_function_name_is_tested(inventory):
    names = {n for n in vars(inventory.FunctionNames) if not n.startswith("_")}
    assert names == set(NAMES) | {"singleQuery"}


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
    raw = {"statusCode": 200, "body": '{"success": 1}'}
    fake_aws.respond("product-update-s3-feature-x", raw=raw)
    assert sdk.updateWithS3(data, inputKeyName="upload-1") == raw  # returned as is
    assert fake_aws.saves == [{"key": "upload-1", "objectToSave": data,
                               "bucket": "input-product-bucket-feature-x",
                               "user": "test-user", "pw": "test-pw"}]
    assert fake_aws.saves[0]["objectToSave"] is data
    # the key goes as a plain dict, not inside an API Gateway-style event
    assert fake_aws.invocations == [{"functionName": "product-update-s3-feature-x",
                                     "input": {"key": "upload-1"},
                                     "invocationType": "RequestResponse"}]
    assert [kind for kind, _ in fake_aws.calls] == ["s3.save", "invoke"]


def test_update_with_s3_tells_ingestion_the_key_it_saved_under_by_default(sdk, fake_aws):
    fake_aws.respond("product-update-s3-feature-x", raw={"statusCode": 200, "body": "{}"})
    sdk.updateWithS3([KALE])
    [save] = fake_aws.saves
    [call] = fake_aws.invocations
    assert call["input"] == {"key": save["key"]}


def test_update_with_s3_writes_with_other_credentials_when_given(sdk, fake_aws):
    sdk.updateWithS3([KALE], inputKeyName="k", invocationType="Event",
                     user="other-user", pw="other-pw")
    [save] = fake_aws.saves
    assert (save["user"], save["pw"]) == ("other-user", "other-pw")
    assert fake_aws.invocations[0]["invocationType"] == "Event"


def test_query_single_product_sends_the_iprcode_to_the_single_query_function(sdk, fake_aws):
    target = sdk.functionNames.singleQuery()  # its value is vps-6fo's to fix and pin
    raw = {"statusCode": 200, "body": '{"iprcode": "0171670"}'}
    fake_aws.respond(target, raw=raw)
    assert sdk.querySingleProduct("0171670") == raw  # returned as is
    assert fake_aws.invocations == [{"functionName": target, "input": {"iprcode": "0171670"},
                                     "invocationType": "RequestResponse"}]


FAILING_CALLS = {  # method: (the Lambda it invokes, the call)
    "updateWithS3": (lambda sdk: sdk.functionNames.updateS3(),
                     lambda sdk: sdk.updateWithS3([KALE], inputKeyName="k")),
    "querySingleProduct": (lambda sdk: sdk.functionNames.singleQuery(),
                           lambda sdk: sdk.querySingleProduct("0171670")),
}


@pytest.mark.parametrize("method", sorted(FAILING_CALLS))
def test_a_failed_invoke_propagates_unchanged(sdk, fake_aws, method):
    function_name, call = FAILING_CALLS[method]
    original = lambda_error("Invoke")
    fake_aws.respond(function_name(sdk), error=original)
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
