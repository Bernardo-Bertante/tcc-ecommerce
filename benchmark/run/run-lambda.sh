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

is_true() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

looks_like_local_lambda() {
  case "$1" in
    http://localhost:*|http://127.0.0.1:*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

lambda_local_rie_for_version() {
  local base_url="$1"

  if [[ -n "${LAMBDA_LOCAL_RIE:-}" ]]; then
    printf '%s' "$LAMBDA_LOCAL_RIE"
    return 0
  fi

  if looks_like_local_lambda "$base_url"; then
    printf '%s' 'true'
    return 0
  fi

  printf '%s' 'false'
}

SMOKE="${SMOKE:-false}"
REPETITIONS="${REPETITIONS:-1}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
REST_SECONDS="${REST_SECONDS:-0}"
run_dir="${RUN_DIR:-$results_dir/$RUN_ID}"
mkdir -p "$run_dir"
log_file="$run_dir/run.log"

if [[ -n "${LAMBDA_VERSIONS:-}" ]]; then
  read -r -a versions <<< "$LAMBDA_VERSIONS"
else
  versions=(
    "springboot|http://127.0.0.1:9001"
    "quarkus-jvm|http://127.0.0.1:9002"
    "quarkus-native|http://127.0.0.1:9003"
  )
fi

scenarios=(
  "l1_sparse_coldstart"
  "l2_warm_burst"
  "l3_concurrency_burst"
)

if [[ -n "${LAMBDA_SCENARIOS:-}" ]]; then
  read -r -a scenarios <<< "${LAMBDA_SCENARIOS//,/ }"
fi

if [[ "${#scenarios[@]}" -eq 0 ]]; then
  echo "No Lambda scenarios were selected." >&2
  exit 1
fi

for scenario in "${scenarios[@]}"; do
  if [[ ! -f "$benchmark_dir/scenarios/${scenario}.js" ]]; then
    echo "Scenario file was not found: benchmark/scenarios/${scenario}.js" >&2
    exit 1
  fi
done

echo "Lambda benchmark run $RUN_ID started at $(date -Is)" | tee -a "$log_file"
echo "[$(date -Is)] SETTINGS smoke=$SMOKE repetitions=$REPETITIONS rest_seconds=$REST_SECONDS scenarios=${scenarios[*]} run_dir=$run_dir" | tee -a "$log_file"

overall_status=0

for repetition in $(seq 1 "$REPETITIONS"); do
  for version in "${versions[@]}"; do
    version_name="${version%%|*}"
    base_url="${version#*|}"
    version_lambda_local_rie="$(lambda_local_rie_for_version "$base_url")"

    for scenario in "${scenarios[@]}"; do
      if [[ "$scenario" == "l1_sparse_coldstart" && -z "${RESET_URL:-}" && "${ALLOW_UNRESET_L1:-false}" != "true" ]]; then
        echo "L1 requires RESET_URL to force cold starts. Set RESET_URL or ALLOW_UNRESET_L1=true for dry runs." >&2
        exit 1
      fi

      result_file="$run_dir/${scenario}_${version_name}_run${repetition}.json"
      summary_file="$run_dir/${scenario}_${version_name}_run${repetition}-summary.json"
      echo "[$(date -Is)] START scenario=$scenario version=$version_name repetition=$repetition base_url=$base_url lambda_local_rie=$version_lambda_local_rie" | tee -a "$log_file"

      set +e
      BASE_URL="$base_url" \
        SMOKE="$SMOKE" \
        RESET_URL="${RESET_URL:-}" \
        REQUIRE_COLD_RESET="${REQUIRE_COLD_RESET:-false}" \
        LAMBDA_LOCAL_RIE="$version_lambda_local_rie" \
        "$K6_BIN" run \
        --summary-export "$summary_file" \
        --out "json=$result_file" \
        "$benchmark_dir/scenarios/${scenario}.js" 2>&1 | tee -a "$log_file"
      k6_status=${PIPESTATUS[0]}
      set -e

      case "$k6_status" in
        0)
          verdict="PASS"
          ;;
        99)
          verdict="THRESHOLD_FAIL"
          if [[ "$overall_status" -eq 0 ]]; then
            overall_status=99
          fi
          ;;
        *)
          verdict="RUN_ERROR"
          overall_status=1
          ;;
      esac

      echo "[$(date -Is)] END scenario=$scenario version=$version_name repetition=$repetition status=$k6_status verdict=$verdict summary=$summary_file result=$result_file" | tee -a "$log_file"

      if [[ "$REST_SECONDS" -gt 0 ]]; then
        echo "[$(date -Is)] REST ${REST_SECONDS}s" | tee -a "$log_file"
        sleep "$REST_SECONDS"
      fi
    done
  done
done

echo "Lambda benchmark run $RUN_ID finished at $(date -Is)" | tee -a "$log_file"
exit "$overall_status"
