#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  push-order-service-images.sh [options]

Options:
  --image-tag TAG             Docker/ECR tag for all three images. Default: current timestamp.
  --repository-prefix PREFIX  Optional ECR repository prefix.
  --profile PROFILE           AWS CLI profile.
  --region REGION             AWS region.
  --skip-build                Reuse existing local Docker images with --image-tag.
  --skip-gradle               Forwarded to prepare-order-service-images.sh.
  --skip-native-build         Forwarded to prepare-order-service-images.sh.
  --output-env PATH           Env file with pushed image URIs.
  -h, --help                  Show this help.
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"
REPOSITORY_PREFIX="${REPOSITORY_PREFIX:-}"
PROFILE=""
REGION=""
SKIP_BUILD=false
SKIP_GRADLE=false
SKIP_NATIVE_BUILD=false
OUTPUT_ENV="$AWS_DIR/build/order-service/image-uris.env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image-tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --repository-prefix)
      REPOSITORY_PREFIX="$2"
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
    --skip-gradle)
      SKIP_GRADLE=true
      shift
      ;;
    --skip-native-build)
      SKIP_NATIVE_BUILD=true
      shift
      ;;
    --output-env)
      OUTPUT_ENV="$2"
      shift 2
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

if ! command -v aws > /dev/null 2>&1; then
  echo "aws CLI is required." >&2
  exit 1
fi
if ! command -v docker > /dev/null 2>&1; then
  echo "docker is required." >&2
  exit 1
fi

AWS_ARGS=()
if [[ -n "$PROFILE" ]]; then
  AWS_ARGS+=(--profile "$PROFILE")
fi

if [[ -z "$REGION" ]]; then
  REGION="$(aws "${AWS_ARGS[@]}" configure get region || true)"
fi
if [[ -z "$REGION" ]]; then
  REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
fi
if [[ -z "$REGION" ]]; then
  echo "AWS region is required. Pass --region or configure the AWS CLI profile." >&2
  exit 1
fi
AWS_ARGS+=(--region "$REGION")

if [[ "$SKIP_BUILD" == false ]]; then
  PREPARE_ARGS=(--image-tag "$IMAGE_TAG")
  if [[ "$SKIP_GRADLE" == true ]]; then
    PREPARE_ARGS+=(--skip-gradle)
  fi
  if [[ "$SKIP_NATIVE_BUILD" == true ]]; then
    PREPARE_ARGS+=(--skip-native-build)
  fi
  "$SCRIPT_DIR/prepare-order-service-images.sh" "${PREPARE_ARGS[@]}"
fi

account_id="$(aws "${AWS_ARGS[@]}" sts get-caller-identity --query Account --output text)"
registry="$account_id.dkr.ecr.$REGION.amazonaws.com"

repository_name() {
  local base="$1"

  if [[ -n "$REPOSITORY_PREFIX" ]]; then
    printf '%s/%s' "$REPOSITORY_PREFIX" "$base"
  else
    printf '%s' "$base"
  fi
}

ensure_repository() {
  local repository="$1"

  if aws "${AWS_ARGS[@]}" ecr describe-repositories --repository-names "$repository" > /dev/null 2>&1; then
    return 0
  fi

  aws "${AWS_ARGS[@]}" ecr create-repository \
    --repository-name "$repository" \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 > /dev/null
}

springboot_repo="$(repository_name order-service-springboot)"
quarkus_jvm_repo="$(repository_name order-service-quarkus-jvm)"
quarkus_native_repo="$(repository_name order-service-quarkus-native)"

ensure_repository "$springboot_repo"
ensure_repository "$quarkus_jvm_repo"
ensure_repository "$quarkus_native_repo"

docker_config_dir="$(mktemp -d)"
trap 'rm -rf "$docker_config_dir"' EXIT
source_docker_config_dir="${DOCKER_CONFIG:-$HOME/.docker}"
current_docker_context="$(docker context show 2>/dev/null || true)"

if [[ -d "$source_docker_config_dir/contexts" ]]; then
  cp -a "$source_docker_config_dir/contexts" "$docker_config_dir/"
fi
if [[ -n "$current_docker_context" && "$current_docker_context" != "default" ]]; then
  printf '{"currentContext":"%s"}\n' "$current_docker_context" > "$docker_config_dir/config.json"
else
  printf '{}\n' > "$docker_config_dir/config.json"
fi

aws "${AWS_ARGS[@]}" ecr get-login-password | DOCKER_CONFIG="$docker_config_dir" docker login --username AWS --password-stdin "$registry" > /dev/null

push_image() {
  local local_image="$1"
  local repository="$2"
  local remote_image="$registry/$repository:$IMAGE_TAG"

  DOCKER_CONFIG="$docker_config_dir" docker tag "$local_image" "$remote_image" || return 1
  DOCKER_CONFIG="$docker_config_dir" docker push "$remote_image" >&2 || return 1
  printf '%s' "$remote_image"
}

springboot_image_uri="$(push_image "order-service-springboot:$IMAGE_TAG" "$springboot_repo")"
quarkus_jvm_image_uri="$(push_image "order-service-quarkus-jvm:$IMAGE_TAG" "$quarkus_jvm_repo")"
quarkus_native_image_uri="$(push_image "order-service-quarkus-native:$IMAGE_TAG" "$quarkus_native_repo")"

mkdir -p "$(dirname -- "$OUTPUT_ENV")"
cat > "$OUTPUT_ENV" <<EOF
IMAGE_TAG=$IMAGE_TAG
SPRINGBOOT_IMAGE_URI=$springboot_image_uri
QUARKUS_JVM_IMAGE_URI=$quarkus_jvm_image_uri
QUARKUS_NATIVE_IMAGE_URI=$quarkus_native_image_uri
EOF

echo "Pushed Order Service images:"
cat "$OUTPUT_ENV"