"""Handler tests for infra/handlers/product_api.py against moto (vps-52s)."""

import bz2
import json
import os
import sys
from pathlib import Path

import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")
requests = pytest.importorskip("requests")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infra" / "handlers"))

os.environ.update(
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_DEFAULT_REGION="ap-southeast-1",
    REGION="ap-southeast-1",
    TABLE_NAME="product-api-table-dev",
    INPUT_BUCKET="product-api-input-dev-test",
    PRODUCT_BUCKET="product-api-data-dev-test",
)

import product_api as api  # noqa: E402

REGION = "ap-southeast-1"


@pytest.fixture
def aws():
    with moto.mock_aws():
        api.reset_clients()
        ddb = boto3.client("dynamodb", region_name=REGION)
        ddb.create_table(
            TableName=api.TABLE_NAME,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "iprcode", "AttributeType": "N"},
                {"AttributeName": "cprcode", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "iprcode", "KeyType": "HASH"},
                {"AttributeName": "cprcode", "KeyType": "RANGE"},
            ],
        )
        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (api.INPUT_BUCKET, api.PRODUCT_BUCKET):
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION})
        yield s3
        api.reset_clients()


def put(iprcode, cprcode, **data):
    api.table().put_item(
        Item={"iprcode": iprcode, "cprcode": cprcode, "data": json.dumps({"iprcode": iprcode, "cprcode": cprcode, **data})}
    )


def body(resp):
    return json.loads(resp["body"])


# ------------------------------------------------------------ GET /product


def test_get_product_by_zero_padded_code(aws):
    put(171670, 171670, name="Test milk", sellingPrice=55)
    resp = api.get_product({"queryStringParameters": {"iprcode": "0171670"}})
    assert resp["statusCode"] == 200
    assert body(resp) == {"iprcode": 171670, "cprcode": 171670, "name": "Test milk", "sellingPrice": 55}


def test_get_product_missing_is_404(aws):
    resp = api.get_product({"queryStringParameters": {"iprcode": "999"}})
    assert resp["statusCode"] == 404


@pytest.mark.parametrize("params", [None, {}, {"iprcode": "abc"}, {"iprcode": "1; drop"}, {"iprcode": "1" * 19}])
def test_get_product_rejects_bad_input(aws, params):
    resp = api.get_product({"queryStringParameters": params})
    assert resp["statusCode"] == 400


# ------------------------------------------------------------ POST /products/list


def test_list_products_returns_found_and_missing(aws):
    put(1, 1, name="a")
    put(2, 2, name="b")
    resp = api.list_products({"body": json.dumps({"iprcodes": ["0000001", 2, "3"]})})
    assert resp["statusCode"] == 200
    out = body(resp)
    assert [p["name"] for p in out["products"]] == ["a", "b"]
    assert out["missing"] == ["3"]


@pytest.mark.parametrize(
    "raw", ["not json", json.dumps([1]), json.dumps({}), json.dumps({"iprcodes": []}), json.dumps({"iprcodes": ["1"] * 101})]
)
def test_list_products_rejects_bad_bodies(aws, raw):
    assert api.list_products({"body": raw})["statusCode"] == 400


# ------------------------------------------------------------ upload + ingest


def test_upload_request_returns_presigned_put_under_uploads(aws):
    out = body(api.upload_request({}))
    assert api.UPLOAD_KEY_RE.match(out["key"])
    assert out["method"] == "PUT"
    assert out["url"].startswith(f"https://{api.INPUT_BUCKET}.s3.")
    assert "X-Amz-Signature=" in out["url"] and "X-Amz-Expires=900" in out["url"]


def test_presigned_put_then_ingest_merges_and_deletes_upload(aws):
    put(5, 50, name="old name", keep="yes")
    grant = body(api.upload_request({}))
    products = [
        {"iprcode": "0000005", "cprcode": 50, "name": "new name"},
        {"iprcode": 6, "cprcode": 60, "name": "fresh"},
    ]
    # moto intercepts the presigned URL in-process
    r = requests.put(grant["url"], data=json.dumps(products), headers=grant["headers"])
    assert r.status_code == 200

    resp = api.ingest({"body": json.dumps({"key": grant["key"]})})
    assert resp["statusCode"] == 200, resp
    assert body(resp) == {"success": 2, "skipped": 0, "failure": 0, "errors": []}

    merged = body(api.get_product({"queryStringParameters": {"iprcode": "5"}}))
    assert merged == {"iprcode": 5, "cprcode": 50, "name": "new name", "keep": "yes"}
    assert aws.list_objects_v2(Bucket=api.INPUT_BUCKET).get("KeyCount") == 0


def test_ingest_skips_unchanged_and_counts_bad_rows(aws):
    put(7, 70, name="same")
    key = "uploads/" + "a" * 32 + ".json"
    rows = {"products": [{"iprcode": 7, "cprcode": 70, "name": "same"}, {"iprcode": "x", "cprcode": 1}, "nope"]}
    aws.put_object(Bucket=api.INPUT_BUCKET, Key=key, Body=json.dumps(rows))
    out = body(api.ingest({"body": json.dumps({"key": key})}))
    assert out["success"] == 0 and out["skipped"] == 1 and out["failure"] == 2
    assert [e["index"] for e in out["errors"]] == [1, 2]


@pytest.mark.parametrize("key", ["../etc/passwd", "uploads/x.json", "other/" + "a" * 32 + ".json", None, 5])
def test_ingest_only_accepts_keys_from_upload_request(aws, key):
    assert api.ingest({"body": json.dumps({"key": key})})["statusCode"] == 400


def test_ingest_missing_upload_is_404(aws):
    resp = api.ingest({"body": json.dumps({"key": "uploads/" + "b" * 32 + ".json"})})
    assert resp["statusCode"] == 404


def test_ingest_rejects_oversized_upload(aws, monkeypatch):
    monkeypatch.setattr(api, "MAX_INGEST_BYTES", 10)
    key = "uploads/" + "c" * 32 + ".json"
    aws.put_object(Bucket=api.INPUT_BUCKET, Key=key, Body=b"[" + b" " * 20 + b"]")
    assert api.ingest({"body": json.dumps({"key": key})})["statusCode"] == 400


def test_ingest_rejects_non_list_upload(aws):
    key = "uploads/" + "d" * 32 + ".json"
    aws.put_object(Bucket=api.INPUT_BUCKET, Key=key, Body=b'{"x": 1}')
    assert api.ingest({"body": json.dumps({"key": key})})["statusCode"] == 400


# ------------------------------------------------------------ dump + all-url


def test_all_url_is_404_before_first_dump(aws):
    assert api.all_products_url({})["statusCode"] == 404


def test_dump_then_all_url_serves_bz2_json(aws):
    for i in range(1, 4):
        put(i, i * 10, name=f"p{i}")
    assert api.dump_all() ["count"] == 3
    out = body(api.all_products_url({}))
    assert out["format"] == "bz2+json"
    r = requests.get(out["url"])
    assert r.status_code == 200
    # same decoding as s3bz Requests.getContentFromUrl (ProductSdk.allQuery)
    products = json.loads(bz2.decompress(r.content))
    assert sorted(p["name"] for p in products) == ["p1", "p2", "p3"]


def test_dump_paginates(aws, monkeypatch):
    calls = []
    real_table = api.table()

    class Paged:
        def scan(self, **kw):
            calls.append(kw)
            if "ExclusiveStartKey" not in kw:
                return {"Items": [{"iprcode": 1, "cprcode": 1, "data": "{}"}], "LastEvaluatedKey": {"iprcode": 1}}
            return {"Items": [{"iprcode": 2, "cprcode": 2, "data": "{}"}]}

    monkeypatch.setattr(api, "table", lambda: Paged())
    assert api.dump_all()["count"] == 2
    assert len(calls) == 2
    assert real_table is not None


def test_responses_are_json_with_content_type(aws):
    resp = api.get_product({"queryStringParameters": {"iprcode": "1"}})
    assert resp["headers"]["Content-Type"] == "application/json"
    json.loads(resp["body"])
