#!/usr/bin/env bash
# Smoke-test the deployed dev product API (vps-52s acceptance 4).
# Expects: no key -> 403; with key, GET /product?iprcode=0171670 -> 200 with that product.
# The key is read from API Gateway into memory and never printed.
set -euo pipefail
# shellcheck source=infra/lib.sh
source "$(dirname "$0")/lib.sh"

require_villaai2
api="$(stack_output ApiUrl)"
load_api_key
iprcode="${1:-0171670}"
fail=0

code="$(curl -sS -o /dev/null -w '%{http_code}' "$api/product?iprcode=$iprcode")"
echo "no key:   GET /product -> $code (want 403)"
[[ "$code" == 403 ]] || fail=1

body="$(mktemp)"; trap 'rm -f "$body"' EXIT
code="$(curl_with_key -o "$body" -w '%{http_code}' "$api/product?iprcode=$iprcode")"
echo "with key: GET /product -> $code (want 200)"
[[ "$code" == 200 ]] || fail=1
python3 - "$body" "$iprcode" <<'EOF' || fail=1
import json, sys
product = json.load(open(sys.argv[1]))
want = int(sys.argv[2])
got = product.get("iprcode")
print(f"          iprcode {got} (want {want}), name: {product.get('name') or product.get('hema_name_en') or '-'}")
sys.exit(0 if got == want else 1)
EOF

code="$(curl_with_key -o /dev/null -w '%{http_code}' -X POST "$api/upload-request")"
echo "with key: POST /upload-request -> $code (want 200)"
[[ "$code" == 200 ]] || fail=1

[[ $fail -eq 0 ]] && echo "SMOKE OK" || { echo "SMOKE FAILED"; exit 1; }
