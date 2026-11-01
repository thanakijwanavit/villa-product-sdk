# Villa product HTTPS API: the contract

Decided in vps-h5t (2026-11-01). This file is the contract between the SDK's HTTPS mode (vps-8hj), the dev product
API (vps-52s, `infra/` on branch `polecat/vps-52s`) and the e2e and parity suite (vps-hqj).
`tests/fixtures/https_contract.json` is its machine-readable copy. `tests/test_https_contract.py` fails when the two
disagree, and when the backend template has a route that is not listed here. The Lambda-invoke mode's contract
stays in `tests/fixtures/contract.json` (vps-3y4) and does not change.

## Decisions

### Q1. Contract source

**Decision:** backend-first, written down. What `polecat/vps-52s` (commit 4462400) already builds and tests is the
baseline: the routes, the `x-api-key` header, the request and response JSON and the presigned upload flow. This file
adds what it lacks: the delete and sync routes, `generatedAt`, and a smaller upload cap (see
[Backend changes](#backend-changes-for-vps-52s)). From now on both sides build against this file, not against each
other's code.

**Why:** vps-52s is built and tested (handler tests against moto, including a real presigned PUT and GET) and waits
only for deploy credentials. Client-first would reopen finished work. With the contract written down, vps-8hj can be
built and tested offline now, against mocked HTTP, instead of waiting for the deploy.

### Q2. All-products dump format

**Decision:** the wire format depends on the mode; the return type does not.

- HTTPS mode serves `format: "bz2+json"`: bz2-compressed UTF-8 JSON whose top level is one array of product objects,
  the same objects `GET /product` returns. The SDK refuses any other `format` value with `ProductSdkError`, so a
  later format change fails loudly instead of decoding wrongly.
- Lambda mode keeps the old `product-get-all-<branch>` file (zlib, pandas `orient="split"`), unchanged.
- `allQuery()` returns a pandas DataFrame in both modes. HTTPS mode decodes with
  `pandas.read_json(io.StringIO(text), orient="records")`. That is the reader Lambda mode's `retrieveJsonZl` already
  uses (with `orient="split"`), and its dtype inference is the same for both layouts, so both modes type columns the
  same way. Column order and index may differ. Checked with pandas 2.3.3 and 3.1.0: the same rows read through
  `split` and through `records` give equal frames with equal dtypes.

**Why:** vps-52s already writes and tests `bz2+json`. A JSON array of records can be read by any client without
pandas: `villaProductSdk.inventory.ProductSdk.allQuery` already decodes it through s3bz (`bz2.decompress`, then
`json.loads`). One return type lets a caller move to HTTPS mode by changing only the constructor.

Rejected:

- Returning a list in HTTPS mode, because code written against the DataFrame would break.
- Building the frame another way, for example `DataFrame.from_records`. `read_json` turns digit-only string columns
  into numbers (product-sdk.ipynb: `allQuery` shows `pr_cgcode` 6 for product 182223, which is stored as `"06"`).
  Another builder would not, and the two modes' frames would differ without any error.
- zlib plus `orient="split"` for HTTPS, because that is a pandas-specific layout for a public API.

### Q3. Product codes in responses

**Decision:** `iprcode` and `cprcode` are JSON integers in every response and in the dump, taken from the table key
(`171670`, not `"0171670"`). Every other field comes back exactly as stored, including `oprcode`, `pr_code` and the
barcodes. A request may give a code as a digit string (`"0171670"`, leading zeros allowed) or as a non-negative
integer; both name the same product. The `missing` and `deleted` lists echo codes exactly as the request sent them.
The SDK passes all of this through unchanged. For the 7-digit display form, use `f"{iprcode:07d}"`.

**Why:**

- The key is a DynamoDB number in both the old table (`product-table-dev-manual`) and the new one.
- SDK version 20 (commit d30074d) casts the six `INTCOLS` (`iprcode`, `cprcode`, `oprcode`, `pr_barcode`,
  `pr_barcode2`, `sellingPrice`) to int before every upload. So Lambda mode already returns ints for rows written
  since then (product-sdk.ipynb: the `syncS3` output after the version 20 upload).
- vps-52s does this today.
- JSON integers are exact for 7-digit codes and 13-digit barcodes, which are all below 2^53.

Rejected: 7-digit strings. The server would have to invent a width, since the API accepts codes of 1 to 18 digits,
and they would still differ from what Lambda mode returns for rows written since version 20.

**Writes:** HTTPS-mode `updateWithS3` sends rows through the same cast as Lambda mode, using one helper for both modes
(vps-t32 is hardening that cast). A row written through either mode is therefore stored the same way. The cast drops
a barcode's leading zero, in both modes (vps-xh2).

**Parity rule (vps-hqj):** Lambda mode returns the stored `data` as is. Its `iprcode` and `cprcode` are strings for
rows written before version 20 (product-sdk.ipynb: `querySingleProduct('0171670')` answered
`'iprcode': '0171670'`) and ints after. The parity check therefore compares those two fields by integer value, and
every other field exactly, type included.

### Q4. Delete route

**Decision:** yes, for test records only.

- `POST /products/delete` and `ProductSdk.deleteProducts(iprcodes)`, in HTTPS mode only.
- The server deletes only codes 9999000 to 9999999, the range the e2e suite writes (`tests/e2e/guard.py`,
  `TEST_PREFIX = "9999"`). A request naming any other code is refused whole: 400, and nothing is deleted.
- In Lambda mode `deleteProducts` raises `ProductSdkError` without calling anything, because no old function exists
  for it. The e2e write-then-clean-up test therefore runs in HTTPS mode only (`sdk.mode == "https"`).

**Why:** vps-hqj criterion 2 must remove what it writes. The API key is a shared bearer secret, so a delete that could
reach real products would let anyone holding a key erase the catalogue, and nothing in the product needs that. If
deleting real products is ever needed, it needs its own authorization, not this key.

### Q5. syncS3 in HTTPS mode

**Decision:** `syncS3()` keeps its meaning: when it returns, `allQuery()` includes every write acknowledged before the
call.

- The new `POST /products/sync` starts a rebuild of the all-products file and answers 202 at once, with
  `requestedAt`.
- The SDK then polls `GET /products/all-url` every 5 s until `generatedAt >= requestedAt`. The default timeout is
  300 s, after which it raises `ProductSdkError`.
- The hourly rebuild stays.

**Why:** Lambda-mode callers write, call `syncS3`, then read with `allQuery`. If `syncS3` did nothing, that read
would be up to an hour stale with no error. A synchronous route cannot work either: API Gateway ends an integration
at 29 s, and a full-table scan plus bz2 is not guaranteed to fit in that (the vps-52s dump function already has a
300 s timeout).

Rejected: dropping `syncS3`, and a synchronous sync route.

## Base URL and auth

- **Base URL:** the stack output `ApiUrl`, for example `https://<api-id>.execute-api.ap-southeast-1.amazonaws.com/dev`.
  The paths below are appended to it. Only `https://` is accepted, and the stage is part of the path.
- **Auth:** every route needs the header `x-api-key: <key>`. API Gateway checks it before any handler runs.
  - A missing or unknown key answers 403.
  - The key is a bearer secret. Never send it to a presigned S3 URL, and never put it in logs, `repr()` or
    exception text.
- **Bodies:** requests with a body send `Content-Type: application/json`. Every response body is JSON.
- **Timestamps:** ISO 8601 in UTC with milliseconds, for example `2026-11-01T12:00:00.000Z`. Clients parse them;
  they do not compare the strings.
- **Presigned URLs** carry a signature and a session token in their query string, so anyone holding one can use it
  until it expires. Treat them like the key: use them once, and never log them.

## Limits

| Limit | Value | Meaning |
|---|---|---|
| `listCodes` | 100 | codes in one `POST /products/list` or `POST /products/delete` call |
| `uploadProducts` | 1000 | products in one upload, and so in one `POST /ingest` |
| `uploadBytes` | 10485760 | bytes in one upload (10 MiB) |
| `presignedUrlSeconds` | 900 | lifetime of the presigned PUT and GET URLs |
| `apiTimeoutSeconds` | 29 | API Gateway's integration limit; every route must answer within it |
| `rateLimit` | 10 | requests per second per key (dev usage plan) |
| `burstLimit` | 20 | burst per key (dev usage plan) |
| `dailyQuota` | 10000 | requests per key per day (dev usage plan) |
| `uploadExpiryDays` | 1 | the input bucket deletes anything left under `uploads/` after this |
| `syncPollSeconds` | 5 | how often SDK `syncS3` polls `GET /products/all-url` |
| `syncTimeoutSeconds` | 300 | how long SDK `syncS3` waits by default |

## Routes

| Method | Path | SDK method | Request | Success |
|---|---|---|---|---|
| GET | `/product` | `querySingleProduct` | query `iprcode` | 200, a product |
| POST | `/products/list` | `queryList` | `{"iprcodes": [...]}`, 1 to 100 codes | 200, `{"products", "missing"}` |
| GET | `/products/all-url` | `allQuery`, `syncS3` | none | 200, `{"url", "expiresIn", "format", "generatedAt"}` |
| POST | `/upload-request` | `updateWithS3` | none | 200, `{"key", "url", "method", "headers", "expiresIn"}` |
| POST | `/ingest` | `updateWithS3` | `{"key": "uploads/<32 hex>.json"}` | 200, `{"success", "skipped", "failure", "errors"}` |
| POST | `/products/sync` | `syncS3` | none | 202, `{"status", "requestedAt"}` (new) |
| POST | `/products/delete` | `deleteProducts` | `{"iprcodes": [...]}`, 1 to 100 test codes | 200, `{"deleted", "missing"}` (new) |

"(new)" marks a route that `polecat/vps-52s` 4462400 does not have yet.

### GET /product

`GET /product?iprcode=0171670` returns the product object: every stored field, plus `iprcode` and `cprcode` as
integers from the key. When several rows share an `iprcode` (different `cprcode`), it returns the row with the
lowest `cprcode`. Excerpt:

```json
{"iprcode": 171670, "cprcode": 171670, "pr_code": "0171670", "pr_abb": "JIRAPAT YOUNG KALE 2", "pr_active": "Y"}
```

| Status | When |
|---|---|
| 400 | `{"error": "iprcode is required"}`, or `{"error": "iprcode must be digits"}` |
| 404 | `{"error": "product not found"}` |

### POST /products/list

`{"iprcodes": ["0171670", 217153, "9999999"]}` returns `{"products": [...], "missing": ["9999999"]}`.

- Products come back in request order. A code sent twice is looked up twice.
- `missing` lists the codes that have no row, exactly as they were sent.
- 400 is returned for an empty list, a non-list, more than 100 codes or any bad code, and then no products come
  back.

### GET /products/all-url

Returns:

```json
{"url": "<presigned GET>", "expiresIn": 900, "format": "bz2+json", "generatedAt": "2026-11-01T12:00:00.000Z"}
```

- `generatedAt` is when the scan that built the file started.
- `generatedAt` is `null` for a file written by a rebuild that did not record it. Treat `null` as older than any
  request.
- 404, `{"error": "all-products file not generated yet"}`, means there has been no rebuild yet.

### POST /upload-request and POST /ingest

1. `POST /upload-request` (no body) returns
   `{"key": "uploads/<32 hex>.json", "url": "<presigned PUT>", "method": "PUT", "headers": {"Content-Type": "application/json"}, "expiresIn": 900}`.
2. The client PUTs the upload to `url`, sending exactly `headers` (the content type is part of the signature) and
   no `x-api-key`. S3 answers 200.
3. The upload is a JSON array of products, or `{"products": [...]}`. Each product has `iprcode` and `cprcode`.
   An upload holds at most 1000 products and 10 MiB.
4. `POST /ingest` with `{"key": ...}` merges each product into its stored row, then deletes the upload:
   - Fields in the upload replace stored fields of the same name, and other stored fields stay.
   - A product whose merge changes nothing counts as `skipped`.
   - The answer is `{"success": n, "skipped": n, "failure": n, "errors": [{"index": i, "error": "..."}]}`. It keeps
     at most 20 errors, and `index` is the product's position in the upload.
   - 400 is returned for a key not shaped like the ones `/upload-request` issues (`uploads/<32 hex>.json`), an
     upload that is not JSON or not a list, or one over a limit.
   - 404 is returned when the upload is missing: never PUT, expired, or already ingested.

### POST /products/sync (new)

- Starts a rebuild of the all-products file without waiting for it, and answers 202 with
  `{"status": "started", "requestedAt": "..."}`.
- The rebuild starts its scan after `requestedAt` and uses consistent reads, so the file includes every write
  acknowledged before `requestedAt`. It records the scan's start as `generatedAt`.
- The file never goes back in time: a rebuild whose scan started before the stored file's `generatedAt` does not
  replace it.

### POST /products/delete (new)

`{"iprcodes": ["9999000", "9999001"]}` deletes every row (every `cprcode`) under each code, and answers
`{"deleted": [...], "missing": [...]}`. Both lists hold codes as they were sent: `deleted` the ones that had rows,
`missing` the ones that had none.

400 is returned when a code is outside 9999000 to 9999999, or for an empty list, a non-list, more than 100 codes or a
bad code. In every 400 case nothing is deleted.

## Errors

| Status | Body | From | SDK |
|---|---|---|---|
| 400 | `{"error": "..."}` | handler, bad input | `ProductSdkError`, not retried |
| 403 | `{"message": "Forbidden"}` | API Gateway, missing or unknown key; an unknown route answers `{"message": "Missing Authentication Token"}` | `ProductSdkError`, not retried |
| 404 | `{"error": "..."}` | handler, not found | `ProductSdkError` with `statusCode` 404, not retried |
| 429 | `{"message": "..."}` | API Gateway, throttled or daily quota used up | retried, then `ProductSdkError` |
| 502 | `{"message": "Internal server error"}` | API Gateway, the handler crashed | retried, then `ProductSdkError` |
| 503 | `{"message": "..."}` | API Gateway | retried, then `ProductSdkError` |
| 504 | `{"message": "Endpoint request timed out"}` | API Gateway, over 29 s | retried except `/ingest`, then `ProductSdkError` |

Handlers answer `{"error": ...}`, and API Gateway's own answers use `{"message": ...}`. Clients act on the status
code, never on the message text.

## The all-products file

- **Name:** `all-products.json.bz2` in the product bucket. It is served only through the presigned GET from
  `GET /products/all-url`.
- **Bytes:** bz2 over UTF-8 JSON. The top level is an array of product objects, exactly as `GET /product` returns
  them: `iprcode` and `cprcode` are integers, and every other field is as stored. `Content-Type` is
  `application/x-bzip2`, and there is no `Content-Encoding`, so the client decompresses the file itself.
- **Rebuilt:** hourly, and on `POST /products/sync`.

## SDK HTTPS mode (vps-8hj)

```python
ProductSdk(endpoint="https://<api-id>.execute-api.ap-southeast-1.amazonaws.com/dev", api_key=key)  # HTTPS mode
ProductSdk(mode="https")          # endpoint and key from VILLA_PRODUCT_API_URL and VILLA_PRODUCT_API_KEY
ProductSdk(branch="dev-manual")   # Lambda mode, unchanged, with a DeprecationWarning once
```

**Choosing the mode:**

- `mode=None` means `"https"` when `endpoint` is given, otherwise `"lambda"`. Environment variables never switch an
  existing call into HTTPS mode.
- In HTTPS mode, `endpoint` and `api_key` fall back to `VILLA_PRODUCT_API_URL` and `VILLA_PRODUCT_API_KEY`.
  - A missing value raises `ValueError` naming the variable, never its value.
  - An endpoint that is not `https://`, and `user` or `pw` given in HTTPS mode, raise `ValueError` too.
- `sdk.mode` is `"lambda"` or `"https"`.

**Timeouts and retries:**

- Timeouts are connect 10 s and read 30 s: the same `connect_timeout` and `read_timeout` arguments as Lambda mode.
- Status 429, 502, 503 and 504, and connection errors, are retried with at most 3 attempts in all and exponential
  backoff starting at 0.5 s.
- `POST /ingest` is never retried. After a lost answer its upload is already deleted, so a retry answers 404. A
  merge that changes nothing is skipped, so the caller can safely rerun `updateWithS3` instead.

**Errors:**

- Every non-2xx answer ends as `ProductSdkError(message, statusCode=<HTTP status>, functionName="<METHOD> <path>",
  body=<parsed JSON or the first 500 characters>)`.
- A failure talking to S3 keeps only S3's error `Code` (for example `SignatureDoesNotMatch`), because S3's error XML
  repeats parts of the request.
- Network errors and timeouts raise `ProductSdkError` with `statusCode=None`, chained from the `requests` exception.

| Method | HTTPS mode | Returns |
|---|---|---|
| `querySingleProduct(iprcode)` | `GET /product` | the product dict; 404 raises `ProductSdkError` |
| `queryList(iprcodes)` | `POST /products/list`, in calls of 100 | a list of products in request order; codes not found are left out |
| `allQuery()` | `GET /products/all-url`, then the presigned GET (no key), bz2, `read_json(orient="records")` | a pandas DataFrame |
| `updateWithS3(data, ...)` | per chunk of up to 1000 rows and 10 MiB: `POST /upload-request`, PUT, `POST /ingest` | `{"keys": [...], "result": {"success", "skipped", "failure", "errors"}}` |
| `syncS3(timeout=300)` | `POST /products/sync`, then poll `GET /products/all-url` (a 404 counts as not ready) | `{"status": "done", "requestedAt", "generatedAt"}` |
| `deleteProducts(iprcodes)` | `POST /products/delete`, in calls of 100 | `{"deleted": [...], "missing": [...]}`; Lambda mode raises `ProductSdkError` |

**`updateWithS3`:**

- Rows go through the Lambda-mode cast first (see Q3).
- `inputKeyName`, `invocationType`, `user` and `pw` are accepted and ignored: the server names uploads, and HTTPS
  mode always waits for the ingest.
- The result adds up all chunks. Error indexes count from the start of the caller's list, and at most 20 errors are
  kept.
- The first failed chunk stops the call. It raises `ProductSdkError`, whose `body` holds the result of the chunks
  already ingested.

**Logging:**

- Log the route, the status and the upload key.
- Never log the API key, a presigned URL or product rows.

## Backend changes for vps-52s

These are measured against `polecat/vps-52s` 4462400. Everything else there stays as built: the five routes,
`x-api-key` with the usage plan, the `{"error": ...}` bodies, the presigned upload flow, and the 1-day expiry under
`uploads/`.

1. **Delete route.** Add `POST /products/delete`, test codes only (Q4). It needs a handler, a route, and table
   `Query` and `DeleteItem` permission.
2. **Sync route.** Add `POST /products/sync`. It invokes the dump function asynchronously (Lambda `InvocationType`
   `Event`, needing `lambda:InvokeFunction` on it) and answers 202 with `requestedAt`.
3. **Rebuild changes.**
   - The rebuild scans with `ConsistentRead`.
   - It stores its scan start as S3 object metadata, and `GET /products/all-url` returns it as `generatedAt`.
   - It does not replace a file whose `generatedAt` is newer.
4. **Upload cap.** `MAX_INGEST_ITEMS` drops from 10000 to 1000.
   - `merge_products` makes one `GetItem` call per product. At a few milliseconds per call (an estimate, not a
     measurement), 10000 products cannot finish inside API Gateway's 29 s. On a timeout the Lambda is stopped part
     way, and the caller gets 504.
   - Raising the cap is a contract change, and needs a measured dev ingest time first (or batched reads).
5. **Wrong claim about which reader decodes the file.** The `dump_all` docstring and `docs/DEPLOYMENT.md` say
   `ProductSdk.allQuery` decodes this file. Of today's code, only `villaProductSdk.inventory.ProductSdk.allQuery`
   reads bz2 JSON. `villaProductSdk.products.ProductSdk.allQuery` reads zlib plus `orient="split"` in Lambda mode,
   and will read this file only in HTTPS mode, once vps-8hj adds it.

## Follow-ups filed by vps-h5t

- vps-bgw: the backend changes above, on top of `polecat/vps-52s`.
- vps-dlq: a contract test showing that `dump_all`'s output is readable by HTTPS-mode `allQuery`.
- vps-o4r: handler responses checked against `tests/fixtures/https_contract.json`.
- vps-xh2: the `INTCOLS` cast drops leading zeros from barcodes, in both modes.

## Changing this contract

A change edits this file, `tests/fixtures/https_contract.json`, the handlers and the SDK's HTTPS mode in the same
change. `tests/test_https_contract.py` keeps the first two in step. While `infra/template.yaml` is present, it also
checks that the template exposes no route missing from this contract.
