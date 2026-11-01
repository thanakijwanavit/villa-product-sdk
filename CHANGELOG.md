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
- `updateWithS3` sends the INTCOLS fields as integers (the notebook change of "convert keys to int", now in the
  library too). `allQuery` reads the zlib-compressed product table with pandas, which it imports when called.
- `products.py` takes `Event` and `Response` from `awsSchema.apigateway` only, and logs through `logging` (no print).
- `parseLambdaResponse`, which every call that reads an answer goes through (`villaProductSdk.inventory` too), takes
  the `header` key the deployed product Lambdas send as well as API Gateway's `headers`, and drops the keys
  awsSchema's `Response` has no field for (`multiValueHeaders`, `isBase64Encoded`). Since the switch to awsSchema's
  `Response` (0.0.13 to 0.0.27 alike), every real answer had raised `ProductSdkError` ('could not be parsed') (vps-8z7).
- `FunctionNames` and `validateConfig` are defined once, in `villaProductSdk.names` (from `names.ipynb`), and
  imported by `villaProductSdk.products`, `villaProductSdk.inventory` and `villaInventorySdk.inventory` (vps-u5v).
  `villaInventorySdk.inventory.FunctionNames` now also has `listQuery`.
