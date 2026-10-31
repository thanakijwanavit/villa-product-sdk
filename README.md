# villaProductSdk
> Read and write Villa product master data through the product Lambda functions on AWS.


Documentation site: https://thanakijwanavit.github.io/villa-product-sdk/ (to be confirmed before a public release).

**Status: pre-alpha.** The API below is what this repository's source does today. Known gaps, and the beads that track them, are listed under [Known issues](#known-issues). See `CHANGELOG.md` for version history.

## Install

```bash
pip install villaProductSdk
```

### Supported Python

`setup.py` declares Python >= 3.6, but the dependency pin `urllib3==1.25.10` breaks the import on newer interpreters. Checked on 2026-10-31 by importing `villaProductSdk.products` with that pin:

| Python | Import |
|---|---|
| 3.8, 3.9 | works |
| 3.10, 3.11, 3.12 | fails inside urllib3 1.25.10 |

Use Python 3.8 or 3.9 until the pin is removed (vps-9kk).

### Versions on PyPI and in this repository

The newest release on PyPI is **0.0.20** (27 Jan 2021). It was built from a state that is not in this repository: it has no `syncS3`, and its `allQuery` downloads a feather file through pandas, which is not a declared dependency. This repository's `settings.ini` says 0.0.19. Everything below describes this repository's source, which is what the next release will ship.

## Authentication

The SDK calls AWS Lambda directly (the **Lambda mode**), so the caller needs AWS credentials that may invoke the product functions and, for uploads, write to the input bucket.

- `ProductSdk(user=..., pw=...)`: `user` is an **AWS access key ID** and `pw` is the matching **AWS secret access key**. They are passed straight to `boto3`.
- Leave both as `None` (recommended) and boto3 uses its normal credential chain: environment variables, `~/.aws` profiles, or an instance or container role.

Lambda mode is **deprecated** for callers outside Villa's own AWS accounts: it needs IAM credentials on the caller's machine. An HTTPS mode, `ProductSdk(endpoint=..., api_key=...)`, is being built (vps-8hj) so that callers only hold an API key. It is not in this release.

## Stages (`branch`)

Every AWS resource name ends with the stage name, chosen with `branch` (default `dev-manual`):

| Resource | Name |
|---|---|
| single product query | `product-get-<branch>` |
| list query | `product-get-list-<branch>` |
| full dump query | `product-get-all-<branch>` |
| S3 upload ingestion | `product-update-s3-<branch>` |
| dump to S3 | `product-dump-s3-<branch>` |
| upload bucket | `input-product-bucket-<branch>` |

Use the dev stage (`dev-manual`) for development and testing. Use the production stage only from production systems, with credentials scoped to that stage. The region defaults to `ap-southeast-1` (`region=`).

## Example (dev stage)

```python
from villaProductSdk.products import ProductSdk

# credentials come from the environment or an AWS profile; never write keys in code
sdk = ProductSdk(branch="dev-manual")

product = sdk.querySingleProduct("0171670")   # dict, or None on failure
if product is None:
    raise SystemExit("query failed; see the printed message")
print(product)
```

Run it with credentials from the environment, for example `AWS_PROFILE=<your-dev-profile> python example.py`.

## API reference: `villaProductSdk.products`

All methods are on `ProductSdk`. "Lambda error" means a `botocore.exceptions.ClientError` raised by boto3 (for example `AccessDeniedException` or `ResourceNotFoundException`) or a `botocore.exceptions.NoCredentialsError`.

### `ProductSdk(branch='dev-manual', user=None, pw=None, region='ap-southeast-1')`

Creates the Lambda client. Makes no network call.

### `querySingleProduct(iprcode='0171670')`

- **Input:** `iprcode`, the product code as a string.
- **Output:** the product as a `dict` of product fields (`iprcode`, `cprcode`, `pr_name`, ...), as returned by `product-get-<branch>`.
- **Errors:** none raised. Any exception, including a Lambda error, prints `calling lambda failed` and returns `None`. An unparseable response is logged and returns `None`. A product that is not found comes back as whatever body the function returns, not as an exception. (vps-jg2, vps-b4r)

### `queryList(iprcodes)`

- **Input:** `iprcodes`, a list of product codes (strings).
- **Output:** the response body of `product-get-list-<branch>`, a list of product dicts.
- **Errors:** a Lambda error is raised. An unparseable response raises a plain `Exception` whose message is the traceback. A non-200 status prints `error` and **returns the error body as data**. (vps-jg2, vps-b4r)

### `allQuery()`

- **Input:** none.
- **Output:** every product, as decoded from the bz2-compressed JSON file at the URL returned by `product-get-all-<branch>`.
- **Errors:** a Lambda error is raised, and so is a `KeyError` if the response has no `url`. If the download fails, it prints `error downloading` and **returns the raw response bytes** instead of the data.

### `updateWithS3(data, inputKeyName='input-data-name', invocationType=InvocationType.event, user=None, pw=None)`

Uploads many products: it saves `data` to the bucket `input-product-bucket-<branch>` under the key `inputKeyName`, then invokes `product-update-s3-<branch>` with that key.

- **Input:** `data`, a list of product dicts; `invocationType`, either `InvocationType.event` (`'Event'`, asynchronous, the default) or `InvocationType.requestResponse` (`'RequestResponse'`, waits for the result). Import `InvocationType` from `lambdasdk.lambdasdk`. `user`/`pw` override the credentials for the S3 write.
- **Output:** with `'Event'`, the string `successfully sent event, please watch your slack`; with `'RequestResponse'`, the ingestion function's response body, or `None` if it cannot be parsed.
- **Errors:** S3 and Lambda errors are raised.
- **Warning:** the default key is fixed, so two uploads running at the same time to the same stage overwrite each other's file. Pass a unique `inputKeyName` per upload. (vps-jg2)

### `syncS3()`

- **Input:** none.
- **Output:** the response body of `product-dump-s3-<branch>`, which rebuilds the dump `allQuery` reads; `None` if the response cannot be parsed.
- **Errors:** a Lambda error is raised.

### Helpers

- `FunctionNames(branchName)`: builds the resource names in the stage table above.
- `ProductSdk.printFirst(d)`: returns the first `(key, value)` pair of a dict.
- `ProductSdk.generalInvoke(functionName, payload)`: invokes any Lambda function synchronously and returns its body; errors as for `queryList`.
- `ProductSdk.returnLambdaResponse(response)`: parses a Lambda proxy response and returns its body, or logs and returns `None` if it cannot be parsed.

## Security

- **Never embed AWS keys** in code, notebooks, or pickled files, and never commit them. Use an AWS profile, environment variables, or a role. The `user`/`pw` arguments exist for compatibility; prefer leaving them unset.
- Use credentials that can reach **only the stage you need**: dev credentials for `dev-manual`, and production credentials only on production systems.
- **API keys** (HTTPS mode, vps-8hj, not yet released) will be issued per caller by the Villa platform team and rotated by issuing a new key and then revoking the old one. Until that mode ships, there are no API keys for this SDK.
- **Reporting a problem:** do not open a public issue for a security problem. Contact the maintainer listed in `settings.ini` (`author_email`) privately, with steps to reproduce.

## Known issues

- Error handling is inconsistent: some failures print and return `None` or an error body instead of raising (vps-jg2, vps-b4r).
- `updateWithS3` uses a fixed S3 key by default (vps-jg2).
- The `urllib3==1.25.10` pin blocks Python 3.10+ and carries known advisories (vps-9kk).
- The PyPI release 0.0.20 and this repository differ (see above).
- The wheel also ships the `villaInventorySdk` and `nbdev_template` packages (vps-0ax).

## Contributing

See `CONTRIBUTING.md`.
