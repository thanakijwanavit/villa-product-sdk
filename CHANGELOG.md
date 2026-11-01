# Changelog

## 0.1.0

Breaking (vps-jg2): callers that checked for `None` or read an error body must catch `ProductSdkError` instead.

- `ProductSdkError` (statusCode, functionName, body) is raised when an invoke fails, a response cannot be parsed, or a
  function answers with a status other than 200. `querySingleProduct`, `queryList`, `generalInvoke`, `syncS3`,
  `allQuery` and `returnLambdaResponse` no longer print and return `None` or the error body.
- `updateWithS3` uploads under a new key per call (`input-data-name-<uuid>`) unless `inputKeyName` is given, so
  concurrent uploads no longer overwrite each other. It returns
  `{key, bucket, functionName, invocationType, result}`; `result` is `None` for the default async (Event) call,
  which used to return "successfully sent event, please watch your slack".
- `updateWithS3` sends the INTCOLS fields (`iprcode`, `cprcode`, `oprcode`, `sellingPrice`) as integers (the notebook
  change of "convert keys to int", now in the library too). `allQuery` reads the zlib-compressed product table with
  pandas, which it imports when called.
- Barcodes (`BARCODECOLS`: `pr_barcode`, `pr_barcode2`) are not cast to int (vps-xh2). They are sent as strings of
  digits, unchanged, so a leading zero (a UPC-A written as a 13-digit EAN, `0012345678905`) survives. A barcode that
  is not a string of digits or a non-negative int is refused before anything is saved; leave the key out for a
  product with no barcode. No released version cast them: 0.0.20 and earlier sent every value as given.
- `products.py` takes `Event` and `Response` from `awsSchema.apigateway` only, and logs through `logging` (no print).
- `FunctionNames` and `validateConfig` are defined once, in `villaProductSdk.names` (from `names.ipynb`), and
  imported by `villaProductSdk.products`, `villaProductSdk.inventory` and `villaInventorySdk.inventory` (vps-u5v).
  `villaInventorySdk.inventory.FunctionNames` now also has `listQuery`.
