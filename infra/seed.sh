#!/usr/bin/env bash
# Load products into the dev table through the API itself:
# /upload-request -> PUT to the presigned URL -> /ingest.
#   infra/seed.sh products.json      (a JSON list of products, each with iprcode and cprcode)
# Make products.json from the old table with infra/export_old_product.py (read-only there).
set -euo pipefail
# shellcheck source=infra/lib.sh
source "$(dirname "$0")/lib.sh"

file="${1:-}"; [[ -f "$file" ]] || die "usage: $0 products.json"
require_villaai2
api="$(stack_output ApiUrl)"
load_api_key

grant="$(curl_with_key -X POST "$api/upload-request")"
key="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["key"])' <<<"$grant")"
url="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["url"])' <<<"$grant")"
code="$(curl -sS -o /dev/null -w '%{http_code}' -X PUT -H 'Content-Type: application/json' \
  --data-binary @"$file" "$url")"
[[ "$code" == 200 ]] || die "upload PUT returned $code"
curl_with_key -X POST -H 'Content-Type: application/json' \
  --data "{\"key\": \"$key\"}" "$api/ingest"
echo
aws lambda invoke --region "$REGION" --function-name "product-api-dump-$STAGE" /dev/stdout >/dev/null \
  && echo "all-products dump refreshed"
