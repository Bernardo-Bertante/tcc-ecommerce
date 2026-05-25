#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  prepare-order-service-images.sh [options]

Options:
  --image-tag TAG       Docker tag for all three local images. Default: current timestamp.
  --skip-gradle         Reuse existing Gradle artifacts.
  --skip-native-build   Reuse existing Quarkus native runner artifact.
  -h, --help            Show this help.
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"
SKIP_GRADLE=false
SKIP_NATIVE_BUILD=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image-tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --skip-gradle)
      SKIP_GRADLE=true
      shift
      ;;
    --skip-native-build)
      SKIP_NATIVE_BUILD=true
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

if ! command -v docker > /dev/null 2>&1; then
  echo "docker is required." >&2
  exit 1
fi

if [[ "$SKIP_GRADLE" == false ]]; then
  echo "[1/5] Building Spring Boot Order Service artifact"
  pushd "$REPO_ROOT/order-service/springboot" > /dev/null
  ./gradlew clean bootJar --no-daemon
  popd > /dev/null

  echo "[2/5] Building Quarkus JVM Order Service artifact"
  pushd "$REPO_ROOT/order-service/quarkus" > /dev/null
  ./gradlew clean build --no-daemon

  if [[ "$SKIP_NATIVE_BUILD" == false ]]; then
    echo "[3/5] Building Quarkus Native Order Service artifact"
    ./gradlew build \
      -Dquarkus.package.type=native \
      -Dquarkus.native.container-build=true \
      -Dquarkus.native.native-image-xmx=6g \
      --no-daemon
  else
    echo "[3/5] Reusing existing Quarkus Native Order Service artifact"
  fi
  popd > /dev/null
else
  echo "[1/5] Reusing existing Gradle artifacts"
  echo "[2/5] Reusing existing Quarkus JVM artifact"
  echo "[3/5] Reusing existing Quarkus Native artifact"
fi

echo "[4/5] Building local Docker images with tag $IMAGE_TAG"
docker build -t "order-service-springboot:$IMAGE_TAG" "$REPO_ROOT/order-service/springboot"
docker build -f "$REPO_ROOT/order-service/quarkus/Dockerfile.jvm" -t "order-service-quarkus-jvm:$IMAGE_TAG" "$REPO_ROOT/order-service/quarkus"
docker build -f "$REPO_ROOT/order-service/quarkus/Dockerfile.native" -t "order-service-quarkus-native:$IMAGE_TAG" "$REPO_ROOT/order-service/quarkus"

echo "[5/5] Prepared local images"
docker image inspect \
  "order-service-springboot:$IMAGE_TAG" \
  "order-service-quarkus-jvm:$IMAGE_TAG" \
  "order-service-quarkus-native:$IMAGE_TAG" \
  --format '{{.RepoTags}} {{.Size}}'

cat <<EOF
IMAGE_TAG=$IMAGE_TAG
SPRINGBOOT_LOCAL_IMAGE=order-service-springboot:$IMAGE_TAG
QUARKUS_JVM_LOCAL_IMAGE=order-service-quarkus-jvm:$IMAGE_TAG
QUARKUS_NATIVE_LOCAL_IMAGE=order-service-quarkus-native:$IMAGE_TAG
EOF