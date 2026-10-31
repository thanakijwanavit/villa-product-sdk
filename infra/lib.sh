# Shared guards for the product API scripts (vps-52s). Source, don't run.
# shellcheck shell=bash

EXPECTED_ACCOUNT=917866274866   # villaai2
REGION=ap-southeast-1
STAGE=dev
STACK_NAME="villa-product-api-${STAGE}"
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "error: $*" >&2; exit 1; }

require_villaai2() {
  local account
  account="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
    || die "aws sts get-caller-identity failed (no credentials?). Use the villaai2 profile, e.g. AWS_PROFILE=ai2."
  [[ "$account" == "$EXPECTED_ACCOUNT" ]] \
    || die "caller is account $account, not villaai2 $EXPECTED_ACCOUNT. Refusing."
}

stack_output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

# Prints nothing. Sets API_KEY in the caller's shell from API Gateway.
load_api_key() {
  local key_id
  key_id="$(stack_output ApiKeyId)"
  [[ -n "$key_id" && "$key_id" != "None" ]] || die "stack has no ApiKeyId output"
  API_KEY="$(aws apigateway get-api-key --region "$REGION" --api-key "$key_id" \
    --include-value --query value --output text)"
  [[ -n "$API_KEY" ]] || die "could not read the API key value"
}

# curl with the key passed on stdin, so it is never in argv or the terminal.
curl_with_key() {
  printf 'x-api-key: %s\n' "$API_KEY" | curl -sS -H @- "$@"
}
