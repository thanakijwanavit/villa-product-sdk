#!/usr/bin/env bash
# Delete the dev product API stack from villaai2 (vps-52s).
#   infra/teardown.sh --yes villa-product-api-dev
# Empties the two stack buckets first (CloudFormation cannot delete full buckets).
# Touches nothing outside this stack; the old product-* functions live in another account.
set -euo pipefail
# shellcheck source=infra/lib.sh
source "$(dirname "$0")/lib.sh"

[[ "${1:-}" == "--yes" && "${2:-}" == "$STACK_NAME" ]] \
  || die "this deletes stack $STACK_NAME and its data. Run: $0 --yes $STACK_NAME"
require_villaai2

for output in InputBucketName ProductBucketName; do
  bucket="$(stack_output "$output")"
  if [[ -n "$bucket" && "$bucket" != "None" ]]; then
    aws s3 rm "s3://$bucket" --recursive --region "$REGION"
  fi
done
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK_NAME"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK_NAME"
echo "deleted $STACK_NAME"
