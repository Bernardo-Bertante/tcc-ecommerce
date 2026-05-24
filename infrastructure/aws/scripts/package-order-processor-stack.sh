#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  package-order-processor-stack.sh --artifact-bucket BUCKET [options]

Options:
  --artifact-bucket BUCKET   Existing S3 bucket used by aws cloudformation package.
  --artifact-prefix PREFIX   S3 prefix for uploaded Lambda artifacts.
  --output-template PATH     Packaged template output path.
  --profile PROFILE          AWS CLI profile.
  --region REGION            AWS region.
  --skip-build               Reuse infrastructure/aws/build/artifacts/*.zip.
  -h, --help                 Show this help.
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_FILE="$AWS_DIR/order-processor-stack.yaml"
OUTPUT_TEMPLATE="$AWS_DIR/build/packaged/order-processor-stack.packaged.yaml"
ARTIFACT_BUCKET=""
ARTIFACT_PREFIX="order-processor-benchmark"
PROFILE=""
REGION=""
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --skip-build)
      SKIP_BUILD=true
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

if [[ "$SKIP_BUILD" == false ]]; then
  "$SCRIPT_DIR/prepare-order-processor-artifacts.sh"
fi

AWS_ARGS=()
if [[ -n "$PROFILE" ]]; then
  AWS_ARGS+=(--profile "$PROFILE")
fi
if [[ -n "$REGION" ]]; then
  AWS_ARGS+=(--region "$REGION")
fi

mkdir -p "$(dirname -- "$OUTPUT_TEMPLATE")"

pushd "$AWS_DIR" > /dev/null
aws "${AWS_ARGS[@]}" cloudformation package \
  --template-file "$TEMPLATE_FILE" \
  --s3-bucket "$ARTIFACT_BUCKET" \
  --s3-prefix "$ARTIFACT_PREFIX" \
  --output-template-file "$OUTPUT_TEMPLATE"
popd > /dev/null

echo "Packaged template written to $OUTPUT_TEMPLATE"