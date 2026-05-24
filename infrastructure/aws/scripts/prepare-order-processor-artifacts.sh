#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd -- "$AWS_DIR/../.." && pwd)"
ARTIFACT_DIR="$AWS_DIR/build/artifacts"

mkdir -p "$ARTIFACT_DIR"
rm -f "$ARTIFACT_DIR"/*.zip

echo "[1/3] Building Spring Boot Lambda artifact"
pushd "$ROOT_DIR/order-processor/springboot" > /dev/null
./gradlew clean build --no-daemon
cp build/distributions/order-processor-springboot-0.0.1-SNAPSHOT-lambda.zip \
  "$ARTIFACT_DIR/order-processor-springboot-lambda.zip"
popd > /dev/null

echo "[2/3] Building Quarkus JVM Lambda artifact"
pushd "$ROOT_DIR/order-processor/quarkus" > /dev/null
./gradlew clean build --no-daemon
cp build/function.zip "$ARTIFACT_DIR/order-processor-quarkus-jvm-function.zip"
cp build/function.zip build/function-jvm.zip

echo "[3/3] Building Quarkus Native Lambda artifact"
./gradlew build \
  -Dquarkus.package.type=native \
  -Dquarkus.native.container-build=true \
  -Dquarkus.native.native-image-xmx=6g \
  --no-daemon
cp build/function.zip "$ARTIFACT_DIR/order-processor-quarkus-native-function.zip"
cp build/function.zip build/function-native.zip
popd > /dev/null

echo "Prepared artifacts:"
ls -lh "$ARTIFACT_DIR"