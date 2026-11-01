"""vps-8z7: parseLambdaResponse takes the answer the deployed product Lambdas send.

The deployed product-* functions answer {'body', 'statusCode', 'header': {}} (README.md logs that lambdaResponse
for product-update-s3-dev-manual); API Gateway proxy responses, and awsSchema.apigateway.Response, say 'headers'.
Response.fromDict hands every key but 'body' to the constructor, which has no 'header' field, nor one for
multiValueHeaders or isBase64Encoded, in any awsSchema release settings.ini allows (0.0.13 to 0.0.27). So every
real answer was a 'could not be parsed' ProductSdkError, and nothing caught it: the other offline tests fake
'headers'.

awsSchema is the real, installed package here: never faked or patched. lambdasdk and s3bz are conftest.py's
recording fakes.
"""
import copy
import json

import awsSchema.apigateway
import pytest

GET = "product-get-dev-manual"
KALE = {"cprcode": "0171670", "iprcode": "0171670", "oprcode": "0171670", "ordertype": "Y",
        "pr_abb": "JIRAPAT YOUNG KALE 2"}


def deployed(body, statusCode=200):
    """an answer as the deployed product Lambdas send it: 'header', not 'headers' (README.md)"""
    return {"body": json.dumps(body), "statusCode": statusCode, "header": {}}


def api_gateway(body, statusCode=200):
    """an API Gateway proxy response: 'headers' and the proxy keys awsSchema's Response has no field for"""
    return {"body": json.dumps(body), "statusCode": statusCode, "headers": {"Content-Type": "application/json"},
            "multiValueHeaders": {"Content-Type": ["application/json"]}, "isBase64Encoded": False}


@pytest.fixture
def products(load_sdk):
    """villaProductSdk.products imported afresh: fake lambdasdk and s3bz, the real awsSchema"""
    return load_sdk("villaProductSdk.products")


def test_the_parser_runs_on_the_real_awsschema(products):
    assert products.Response is awsSchema.apigateway.Response
    assert awsSchema.apigateway.__file__.endswith("apigateway.py")  # the installed module, not a stand-in


def test_parse_lambda_response_accepts_deployed_header_key(products):
    assert products.parseLambdaResponse({"body": '{"a": 1}', "statusCode": 200, "header": {}}) == {"a": 1}


def test_parse_lambda_response_accepts_api_gateway_headers_key(products):
    assert products.parseLambdaResponse({"body": '{"a": 1}', "statusCode": 200, "headers": {}}) == {"a": 1}
    assert products.parseLambdaResponse(api_gateway({"a": 1})) == {"a": 1}


@pytest.mark.parametrize("statusCode, body", [(500, {"error": "internal error"}), (404, {"error": "product not found"})])
def test_parse_lambda_response_non_200_with_header_key_is_typed_error(products, statusCode, body):
    with pytest.raises(products.ProductSdkError) as caught:
        products.parseLambdaResponse(deployed(body, statusCode), GET)
    e = caught.value
    assert e.statusCode == statusCode and e.functionName == GET
    # the function's own error, parsed; a parse error carries the raw body string and chains the TypeError
    assert e.body == body and "could not be parsed" not in str(e) and e.__cause__ is None


def test_parse_lambda_response_does_not_mutate_input(products):
    answers = [deployed({"a": 1}), api_gateway({"a": 1}), deployed({"error": "internal error"}, 500)]
    before = copy.deepcopy(answers)
    assert products.parseLambdaResponse(answers[0]) == products.parseLambdaResponse(answers[1]) == {"a": 1}
    with pytest.raises(products.ProductSdkError):
        products.parseLambdaResponse(answers[2])
    assert answers == before


def test_query_single_product_parses_deployed_response(products, fake_aws):
    fake_aws.respond(GET, raw=deployed(KALE))
    assert products.ProductSdk(branch="dev-manual").querySingleProduct("0171670") == KALE
    assert [i["functionName"] for i in fake_aws.invocations] == [GET]
    assert json.loads(fake_aws.invocations[0]["input"]["body"]) == {"iprcode": "0171670"}


CALLS = [  # (name, call, function, body it answers, what the call returns)
    ("queryList", lambda sdk: sdk.queryList(["0171670"]), "product-get-list-dev-manual", [KALE], [KALE]),
    ("syncS3", lambda sdk: sdk.syncS3(), "product-dump-s3-dev-manual", {"ok": True}, {"ok": True}),
    ("updateWithS3-RequestResponse",
     lambda sdk: sdk.updateWithS3([KALE], invocationType="RequestResponse")["result"],
     "product-update-s3-dev-manual", {"success": 1, "failure": 0}, {"success": 1, "failure": 0}),
    ("allQuery", lambda sdk: sdk.allQuery(), "product-get-all-dev-manual",
     {"url": "https://example.invalid/all"}, ("downloaded", "https://example.invalid/all")),
]


@pytest.mark.parametrize("call, function, body, expected", [c[1:] for c in CALLS], ids=[c[0] for c in CALLS])
def test_every_other_synchronous_call_parses_deployed_response(products, fake_aws, monkeypatch,
                                                               call, function, body, expected):
    fake_aws.respond(function, raw=deployed(body))
    monkeypatch.setattr(products, "retrieveJsonZl", lambda url, timeout: ("downloaded", url))  # allQuery's download
    assert call(products.ProductSdk(branch="dev-manual")) == expected
    assert [i["functionName"] for i in fake_aws.invocations] == [function]


@pytest.mark.usefixtures("products")  # loaded first, so the fake-bound products module inventory imports is undone too
def test_inventory_query_single_product_parses_deployed_response(load_sdk, fake_aws):
    # villaProductSdk.inventory parses with products.parseLambdaResponse since vps-9he
    inventory = load_sdk("villaProductSdk.inventory")
    fake_aws.respond(GET, raw=deployed(KALE))
    assert inventory.ProductSdk(branch="dev-manual").querySingleProduct("0171670") == KALE
