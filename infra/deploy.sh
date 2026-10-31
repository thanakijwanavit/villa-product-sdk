#!/usr/bin/env bash
# Deploy the dev product API to villaai2 (vps-52s).
#
#   infra/deploy.sh               build, create a change set, print and check it (no changes made)
#   infra/deploy.sh --execute CHANGE_SET_NAME
#                                 execute a change set created and checked earlier
#
# Refuses unless the caller is account 917866274866. Dev stage only.
set -euo pipefail
# shellcheck source=infra/lib.sh
source "$(dirname "$0")/lib.sh"

require_villaai2
cd "$INFRA_DIR"

if [[ "${1:-}" == "--execute" ]]; then
  name="${2:-}"; [[ -n "$name" ]] || die "usage: $0 --execute CHANGE_SET_NAME"
  out="$(mktemp)"; trap 'rm -f "$out"' EXIT
  aws cloudformation describe-change-set --region "$REGION" --stack-name "$STACK_NAME" \
    --change-set-name "$name" --output json > "$out"
  python3 check_changeset.py "$out" >/dev/null || die "change set $name holds forbidden resources"
  aws cloudformation execute-change-set --region "$REGION" --stack-name "$STACK_NAME" --change-set-name "$name"
  if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
       --query 'Stacks[0].StackStatus' --output text | grep -q '^CREATE'; then
    aws cloudformation wait stack-create-complete --region "$REGION" --stack-name "$STACK_NAME"
  else
    aws cloudformation wait stack-update-complete --region "$REGION" --stack-name "$STACK_NAME"
  fi
  echo "deployed. API: $(stack_output ApiUrl)"
  exit 0
fi

[[ $# -eq 0 ]] || die "usage: $0 [--execute CHANGE_SET_NAME]"

sam validate --lint --region "$REGION" -t template.yaml || echo "(lint warnings above; W3005 on SAM-generated resources is expected)"
sam build -t template.yaml --region "$REGION"
sam package --region "$REGION" --resolve-s3 --output-template-file .aws-sam/packaged.yaml >/dev/null

if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" >/dev/null 2>&1; then
  type=UPDATE
else
  type=CREATE
fi
name="vps-52s-$(date -u +%Y%m%dT%H%M%SZ)"
aws cloudformation create-change-set --region "$REGION" --stack-name "$STACK_NAME" \
  --change-set-name "$name" --change-set-type "$type" \
  --template-body file://.aws-sam/packaged.yaml \
  --parameters ParameterKey=Stage,ParameterValue="$STAGE" \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --tags Key=project,Value=villa-product-api Key=stage,Value="$STAGE" >/dev/null
aws cloudformation wait change-set-create-complete --region "$REGION" \
  --stack-name "$STACK_NAME" --change-set-name "$name"
aws cloudformation describe-change-set --region "$REGION" --stack-name "$STACK_NAME" \
  --change-set-name "$name" --output json > .aws-sam/changeset.json
python3 check_changeset.py .aws-sam/changeset.json
echo
echo "Paste the table above into the bead notes, then run:"
echo "  infra/deploy.sh --execute $name"
