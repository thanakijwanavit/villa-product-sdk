# Dev product API on villaai2 (vps-52s)

An HTTPS product API so the SDK no longer needs caller AWS keys
(SDK side: vps-8hj). Account **villaai2 917866274866**, region
**ap-southeast-1**, stack **`villa-product-api-dev`**, **dev stage only**.

## Where the old backend lives

The SDK's `product-get-<branch>`, `product-get-all-`, `product-update-s3-`,
`product-dump-s3-` functions and bucket `input-product-bucket-<branch>` come
from **`thanakijwanavit/villaMaster`, `villa-master-dev/product/template.yml`**
(account 394922924679). Their code is a 5-line `products/app.py` that
re-exports handlers from the **`villaProductDatabase`** package
(`thanakijwanavit/villa-product-database`, `villaProductDatabase/database.py`).
`product-get-list-*` is named by the SDK but is not defined in that template.

`infra/handlers/product_api.py` ports those handlers. It keeps the same table
shape (hash `iprcode` N, range `cprcode` N, product fields as JSON in `data`)
and the old merge-on-update rule. It drops what villaai2 forbids or a public
API should not do: VPC + DAX, EFS cache, pandas, public-read S3 objects and
LINE/Slack calls (the old template holds those tokens in plain text; they are
not copied). Only boto3 is needed. The old functions and buckets are not
touched and no caller is repointed.

## Endpoints

All need header `x-api-key`. Without it API Gateway answers **403**.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/product` | `?iprcode=0171670` | product object, 404 if absent |
| POST | `/products/list` | `{"iprcodes": ["0171670", ...]}` (≤100) | `{"products": [...], "missing": [...]}` |
| GET | `/products/all-url` | | `{"url", "expiresIn", "format": "bz2+json"}`: presigned GET of every product (same encoding `ProductSdk.allQuery` decodes) |
| POST | `/upload-request` | | `{"key", "url", "method": "PUT", "headers"}`: presigned PUT, 15 min |
| POST | `/ingest` | `{"key": "<key from upload-request>"}` | `{"success", "skipped", "failure", "errors"}` |

Upload format: a JSON list of products (or `{"products": [...]}`), each with
`iprcode` and `cprcode`, at most 10 MB / 10 000 rows. Ingest deletes the
upload afterwards, and the bucket expires anything left under `uploads/` after
1 day. The all-products file is rebuilt hourly by `product-api-dump-dev`.

Usage plan: 10 req/s, burst 20, 10 000 calls a day. The API key is created
by SAM (`ProductApiApiKey`) and stays in API Gateway. Scripts read it by id
from the stack output `ApiKeyId` and never print it.

## Deploy

Run with the villaai2 profile. Every script refuses unless
`aws sts get-caller-identity` returns 917866274866.

```bash
export AWS_PROFILE=ai2
infra/deploy.sh                      # lint, build, package, create + print the change set; changes nothing
# paste the printed table into the bead; it must say "OK: no ECS/Fargate/EC2 ..."
infra/deploy.sh --execute vps-52s-<UTC stamp>   # re-checks the change set, executes, waits
```

Under nic's 16 Oct order (hm-ggytw) agent identities have no direct AWS write:
the execute step is run by villa-secret's deployer, or by a person.

## Seed product 0171670 and smoke-test

```bash
# read-only on the old account
AWS_PROFILE=default aws dynamodb query --region ap-southeast-1 \
  --table-name product-table-dev-manual \
  --key-condition-expression 'iprcode = :i' \
  --expression-attribute-values '{":i": {"N": "171670"}}' > /tmp/old.json
python3 infra/export_old_product.py /tmp/old.json > /tmp/products.json

AWS_PROFILE=ai2 infra/seed.sh /tmp/products.json   # upload-request -> PUT -> ingest -> refresh dump
AWS_PROFILE=ai2 infra/smoke.sh                     # no key 403; with key 0171670 200; upload-request 200
```

## Teardown

```bash
AWS_PROFILE=ai2 infra/teardown.sh --yes villa-product-api-dev
```

This empties the two stack buckets, deletes the stack and waits. Nothing
outside the stack is touched.

## Tests

```bash
pip install 'moto[s3,dynamodb]' boto3 pytest pyyaml requests
python -m pytest tests/test_product_api_handlers.py tests/test_product_api_infra.py
```

The handler tests run against moto, including a real presigned PUT and GET.
The infra tests check the template (dev only, no VPC/servers, the four Block
Public Access settings, encryption, TLS-only policy, upload expiry, API key +
throttled plan, the five routes), the change-set guard and the old-table export.
