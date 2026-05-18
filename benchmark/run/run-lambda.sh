#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
benchmark_dir="$(cd "$script_dir/.." && pwd)"
results_dir="$benchmark_dir/results"
mkdir -p "$results_dir"

K6_BIN="${K6_BIN:-k6}"
if ! command -v "$K6_BIN" >/dev/null 2>&1; then
  echo "k6 was not found. Install k6 or set K6_BIN to its executable path." >&2
  exit 1
fi

SMOKE="${SMOKE:-false}"
REPETITIONS="${REPETITIONS:-1}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
REST_SECONDS="${REST_SECONDS:-0}"
log_file="$results_dir/lambda-$RUN_ID.log"

if [[ -n "${LAMBDA_VERSIONS:-}" ]]; then
  read -r -a versions <<< "$LAMBDA_VERSIONS"
else
  versions=(
    "quarkus-native|http://localhost:8081"
    "quarkus-jvm|http://localhost:8082"
    "springboot|http://localhost:8083"
  )
fi

scenarios=(
  "l1_sparse_coldstart"
  "l2_warm_burst"
  "l3_concurrency_burst"
)

echo "Lambda benchmark run $RUN_ID started at $(date -Is)" | tee -a "$log_file"

for repetition in $(seq 1 "$REPETITIONS"); do
  for version in "${versions[@]}"; do
    version_name="${version%%|*}"
    base_url="${version#*|}"

    for scenario in "${scenarios[@]}"; do
      if [[ "$scenario" == "l1_sparse_coldstart" && -z "${RESET_URL:-}" && "${ALLOW_UNRESET_L1:-false}" != "true" ]]; then
        echo "L1 requires RESET_URL to force cold starts. Set RESET_URL or ALLOW_UNRESET_L1=true for dry runs." >&2
        exit 1
      fi

      result_file="$results_dir/${scenario}_${version_name}_run${repetition}.json"
      echo "[$(date -Is)] START scenario=$scenario version=$version_name repetition=$repetition base_url=$base_url" | tee -a "$log_file"

      BASE_URL="$base_url" SMOKE="$SMOKE" RESET_URL="${RESET_URL:-}" REQUIRE_COLD_RESET="${REQUIRE_COLD_RESET:-false}" "$K6_BIN" run \
        --out "json=$result_file" \
        "$benchmark_dir/scenarios/${scenario}.js" 2>&1 | tee -a "$log_file"

      echo "[$(date -Is)] END scenario=$scenario version=$version_name repetition=$repetition result=$result_file" | tee -a "$log_file"

      if [[ "$REST_SECONDS" -gt 0 ]]; then
        echo "[$(date -Is)] REST ${REST_SECONDS}s" | tee -a "$log_file"
        sleep "$REST_SECONDS"
      fi
    done
  done
done

echo "Lambda benchmark run $RUN_ID finished at $(date -Is)" | tee -a "$log_file"
