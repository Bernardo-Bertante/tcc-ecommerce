#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy-order-processor-stack.sh --artifact-bucket BUCKET [options]

Options:
  --stack-name NAME                 CloudFormation stack name.
  --artifact-bucket BUCKET         Existing S3 bucket used by aws cloudformation package.
  --artifact-prefix PREFIX         S3 prefix for uploaded Lambda artifacts.
  --output-template PATH           Packaged template output path.
  --profile PROFILE                AWS CLI profile.
  --region REGION                  AWS region.
  --function-url-auth-type TYPE    NONE or AWS_IAM. Default: NONE.
  --lambda-memory-size MB          Default: 1024.
  --lambda-timeout-seconds SEC     Default: 30.
  --log-retention-days DAYS        Default: 14.
  --processed-orders-table NAME    Default: processed_orders.
  --stock-reservations-table NAME  Default: stock_reservations.
  --skip-build                     Reuse infrastructure/aws/build/artifacts/*.zip.
  --skip-package                   Reuse the packaged template output.
  -h, --help                       Show this help.
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
OUTPUT_TEMPLATE="$AWS_DIR/build/packaged/order-processor-stack.packaged.yaml"
STACK_NAME="order-processor-benchmark"
ARTIFACT_BUCKET=""
ARTIFACT_PREFIX=""
PROFILE=""
REGION=""
FUNCTION_URL_AUTH_TYPE="NONE"
LAMBDA_MEMORY_SIZE="1024"
LAMBDA_TIMEOUT_SECONDS="30"
LOG_RETENTION_DAYS="14"
PROCESSED_ORDERS_TABLE_NAME="processed_orders"
STOCK_RESERVATIONS_TABLE_NAME="stock_reservations"
SKIP_BUILD=false
SKIP_PACKAGE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --artifact-bucket)
      ARTIFACT_BUCKET="$2"
      shift 2
      ;;
    --artifact-prefix)
      ARTIFACT_PREFIX="$2"
      shift 2
      ;;
    --output-template)
      OUTPUT_TEMPLATE="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --function-url-auth-type)
      FUNCTION_URL_AUTH_TYPE="$2"
      shift 2
      ;;
    --lambda-memory-size)
      LAMBDA_MEMORY_SIZE="$2"
      shift 2
      ;;
    --lambda-timeout-seconds)
      LAMBDA_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --log-retention-days)
      LOG_RETENTION_DAYS="$2"
      shift 2
      ;;
    --processed-orders-table)
      PROCESSED_ORDERS_TABLE_NAME="$2"
      shift 2
      ;;
    --stock-reservations-table)
      STOCK_RESERVATIONS_TABLE_NAME="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --skip-package)
      SKIP_PACKAGE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$ARTIFACT_BUCKET" ]]; then
  echo "--artifact-bucket is required." >&2
  usage >&2
  exit 1
fi

if ! command -v aws > /dev/null 2>&1; then
  echo "aws CLI is required." >&2
  exit 1
fi

PROFILE="${PROFILE:-${AWS_PROFILE:-pessoal}}"
REGION="${REGION:-${AWS_REGION:-us-east-1}}"

if [[ -z "$ARTIFACT_PREFIX" ]]; then
  ARTIFACT_PREFIX="$STACK_NAME"
fi

AWS_ARGS=(--profile "$PROFILE" --region "$REGION")

echo "Template creates Lambda execution IAM role. CAPABILITY_IAM is required."
account_id="$(aws "${AWS_ARGS[@]}" sts get-caller-identity --query Account --output text)"
echo "Deploy target: account=$account_id profile=$PROFILE region=$REGION"

if [[ "$SKIP_PACKAGE" == false ]]; then
  PACKAGE_ARGS=(
    --artifact-bucket "$ARTIFACT_BUCKET"
    --artifact-prefix "$ARTIFACT_PREFIX"
    --output-template "$OUTPUT_TEMPLATE"
  )
  if [[ -n "$PROFILE" ]]; then
    PACKAGE_ARGS+=(--profile "$PROFILE")
  fi
  if [[ -n "$REGION" ]]; then
    PACKAGE_ARGS+=(--region "$REGION")
  fi
  if [[ "$SKIP_BUILD" == true ]]; then
    PACKAGE_ARGS+=(--skip-build)
  fi

  "$SCRIPT_DIR/package-order-processor-stack.sh" "${PACKAGE_ARGS[@]}"
fi

aws "${AWS_ARGS[@]}" cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file "$OUTPUT_TEMPLATE" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    FunctionUrlAuthType="$FUNCTION_URL_AUTH_TYPE" \
    LambdaMemorySize="$LAMBDA_MEMORY_SIZE" \
    LambdaTimeoutSeconds="$LAMBDA_TIMEOUT_SECONDS" \
    LogRetentionInDays="$LOG_RETENTION_DAYS" \
    ProcessedOrdersTableName="$PROCESSED_ORDERS_TABLE_NAME" \
    StockReservationsTableName="$STOCK_RESERVATIONS_TABLE_NAME"

aws "${AWS_ARGS[@]}" cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
  --output table