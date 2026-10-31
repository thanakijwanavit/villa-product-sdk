"""Product API handlers for the villaai2 dev stack (vps-52s).

HTTPS port of the old product-* Lambdas (thanakijwanavit/villaMaster,
villa-master-dev/product; logic in villaProductDatabase.database).  Same data
model: DynamoDB hash key ``iprcode`` (number), range key ``cprcode``
(number), product fields as a JSON string in ``data``.

What changed on purpose, because the villaai2 guardrails deny it or a public
API must not do it: no VPC, no DAX, no EFS cache, no pandas, no public-read
S3 objects (callers get presigned URLs), no LINE/Slack notifications.

Only boto3 is needed; it ships in the Lambda runtime.
"""

import bz2
import json
import os
import re
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = os.environ.get("REGION", "ap-southeast-1")
TABLE_NAME = os.environ.get("TABLE_NAME", "")
INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "")
PRODUCT_BUCKET = os.environ.get("PRODUCT_BUCKET", "")
ALL_PRODUCTS_KEY = os.environ.get("ALL_PRODUCTS_KEY", "all-products.json.bz2")
URL_EXPIRES = int(os.environ.get("URL_EXPIRES", "900"))
MAX_LIST = int(os.environ.get("MAX_LIST", "100"))
MAX_INGEST_BYTES = int(os.environ.get("MAX_INGEST_BYTES", str(10 * 1024 * 1024)))
MAX_INGEST_ITEMS = int(os.environ.get("MAX_INGEST_ITEMS", "10000"))

UPLOAD_PREFIX = "uploads/"
UPLOAD_KEY_RE = re.compile(r"^uploads/[0-9a-f]{32}\.json$")
CODE_RE = re.compile(r"^[0-9]{1,18}$")

_s3 = None
_table = None


def s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            region_name=REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
    return _s3


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    return _table


def reset_clients():
    """Drop cached clients (tests swap the AWS backend between cases)."""
    global _s3, _table
    _s3 = None
    _table = None


# ---------------------------------------------------------------- helpers


class BadRequest(Exception):
    pass


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def _body(event):
    raw = (event or {}).get("body")
    if raw in (None, ""):
        return {}
    if (event or {}).get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        raise BadRequest("body is not valid JSON")
    if not isinstance(parsed, dict):
        raise BadRequest("body must be a JSON object")
    return parsed


def parse_code(value, name="iprcode"):
    """'0171670' -> 171670, as the old handlers did with int()."""
    if isinstance(value, bool):
        raise BadRequest(f"{name} must be digits")
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not CODE_RE.match(value.strip()):
        raise BadRequest(f"{name} must be digits")
    return int(value.strip())


def item_to_product(item):
    data = item.get("data") or "{}"
    product = json.loads(data) if isinstance(data, str) else dict(data)
    product["iprcode"] = int(item["iprcode"])
    product["cprcode"] = int(item["cprcode"])
    return product


def _get_one(iprcode):
    result = table().query(KeyConditionExpression=Key("iprcode").eq(iprcode), Limit=1)
    items = result.get("Items") or []
    return item_to_product(items[0]) if items else None


def _handle(fn):
    def wrapper(event, context=None):
        try:
            return fn(event or {})
        except BadRequest as e:
            return respond(400, {"error": str(e)})

    wrapper.__name__ = fn.__name__
    return wrapper


# ---------------------------------------------------------------- handlers


@_handle
def get_product(event):
    """GET /product?iprcode=0171670"""
    params = event.get("queryStringParameters") or {}
    if "iprcode" not in params:
        raise BadRequest("iprcode is required")
    product = _get_one(parse_code(params["iprcode"]))
    if product is None:
        return respond(404, {"error": "product not found"})
    return respond(200, product)


@_handle
def list_products(event):
    """POST /products/list  {"iprcodes": ["0171670", ...]}"""
    codes = _body(event).get("iprcodes")
    if not isinstance(codes, list) or not codes:
        raise BadRequest("iprcodes must be a non-empty list")
    if len(codes) > MAX_LIST:
        raise BadRequest(f"at most {MAX_LIST} iprcodes per call")
    products, missing = [], []
    for raw in codes:
        product = _get_one(parse_code(raw))
        if product is None:
            missing.append(raw)
        else:
            products.append(product)
    return respond(200, {"products": products, "missing": missing})


@_handle
def all_products_url(event):
    """GET /products/all-url -> presigned GET of the bz2 JSON dump."""
    try:
        s3().head_object(Bucket=PRODUCT_BUCKET, Key=ALL_PRODUCTS_KEY)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return respond(404, {"error": "all-products file not generated yet"})
        raise
    url = s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": PRODUCT_BUCKET, "Key": ALL_PRODUCTS_KEY},
        ExpiresIn=URL_EXPIRES,
    )
    return respond(200, {"url": url, "expiresIn": URL_EXPIRES, "format": "bz2+json"})


@_handle
def upload_request(event):
    """POST /upload-request -> presigned PUT for a JSON list of products."""
    key = f"{UPLOAD_PREFIX}{uuid.uuid4().hex}.json"
    url = s3().generate_presigned_url(
        "put_object",
        Params={"Bucket": INPUT_BUCKET, "Key": key, "ContentType": "application/json"},
        ExpiresIn=URL_EXPIRES,
    )
    return respond(
        200,
        {
            "key": key,
            "url": url,
            "method": "PUT",
            "headers": {"Content-Type": "application/json"},
            "expiresIn": URL_EXPIRES,
        },
    )


def merge_products(products):
    """Old valueUpdate2 semantics: merge each product into the stored data,
    write only what changed."""
    result = {"success": 0, "skipped": 0, "failure": 0, "errors": []}
    tbl = table()
    with tbl.batch_writer(overwrite_by_pkeys=["iprcode", "cprcode"]) as batch:
        for index, product in enumerate(products):
            try:
                if not isinstance(product, dict):
                    raise BadRequest("product must be an object")
                iprcode = parse_code(product.get("iprcode"), "iprcode")
                cprcode = parse_code(product.get("cprcode"), "cprcode")
                existing = tbl.get_item(Key={"iprcode": iprcode, "cprcode": cprcode}).get("Item")
                data = json.loads(existing["data"]) if existing else {}
                updated = {**data, **product, "iprcode": iprcode, "cprcode": cprcode}
                if existing and updated == data:
                    result["skipped"] += 1
                    continue
                batch.put_item(
                    Item={
                        "iprcode": iprcode,
                        "cprcode": cprcode,
                        "data": json.dumps(updated, sort_keys=True, ensure_ascii=False),
                    }
                )
                result["success"] += 1
            except BadRequest as e:
                result["failure"] += 1
                if len(result["errors"]) < 20:
                    result["errors"].append({"index": index, "error": str(e)})
    return result


@_handle
def ingest(event):
    """POST /ingest {"key": "uploads/<32 hex>.json"} -> merge into the table."""
    key = _body(event).get("key")
    if not isinstance(key, str) or not UPLOAD_KEY_RE.match(key):
        raise BadRequest("key must be a key returned by /upload-request")
    try:
        head = s3().head_object(Bucket=INPUT_BUCKET, Key=key)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return respond(404, {"error": "upload not found (expired or never uploaded)"})
        raise
    if head["ContentLength"] > MAX_INGEST_BYTES:
        raise BadRequest(f"upload is larger than {MAX_INGEST_BYTES} bytes")
    raw = s3().get_object(Bucket=INPUT_BUCKET, Key=key)["Body"].read()
    try:
        payload = json.loads(raw)
    except ValueError:
        raise BadRequest("upload is not valid JSON")
    products = payload.get("products") if isinstance(payload, dict) else payload
    if not isinstance(products, list):
        raise BadRequest("upload must be a JSON list of products or {\"products\": [...]}")
    if len(products) > MAX_INGEST_ITEMS:
        raise BadRequest(f"at most {MAX_INGEST_ITEMS} products per upload")
    result = merge_products(products)
    s3().delete_object(Bucket=INPUT_BUCKET, Key=key)
    return respond(200, result)


def dump_all(event=None, context=None):
    """Scheduled: write every product as bz2-compressed JSON (the format
    s3bz Requests.getContentFromUrl, used by ProductSdk.allQuery, reads)."""
    products, kwargs = [], {}
    while True:
        page = table().scan(**kwargs)
        products.extend(item_to_product(i) for i in page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    body = bz2.compress(json.dumps(products, default=_json_default, ensure_ascii=False).encode("utf-8"))
    s3().put_object(
        Bucket=PRODUCT_BUCKET, Key=ALL_PRODUCTS_KEY, Body=body, ContentType="application/x-bzip2"
    )
    return {"count": len(products), "bytes": len(body)}
