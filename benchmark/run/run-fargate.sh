#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
benchmark_dir="$(cd "$script_dir/.." && pwd)"
repo_root="$(cd "$benchmark_dir/.." && pwd)"
results_dir="$benchmark_dir/results"
mkdir -p "$results_dir"

resolve_path() {
  local path="$1"

  if [[ "$path" = /* ]]; then
    printf '%s' "$path"
    return 0
  fi

  if [[ -e "$repo_root/$path" ]]; then
    printf '%s' "$repo_root/$path"
    return 0
  fi

  printf '%s' "$path"
}

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

if [[ -n "${RUN_CONFIG:-}" ]]; then
  run_config_path="$(resolve_path "$RUN_CONFIG")"

  if [[ ! -f "$run_config_path" ]]; then
    echo "Run config file was not found: $RUN_CONFIG" >&2
    exit 1
  fi

  set -a
  # shellcheck source=/dev/null
  source "$run_config_path"
  set +a
fi

K6_BIN="${K6_BIN:-k6}"
if ! command -v "$K6_BIN" >/dev/null 2>&1; then
  echo "k6 was not found. Install k6 or set K6_BIN to its executable path." >&2
  exit 1
fi

SMOKE="${SMOKE:-false}"
if is_true "$SMOKE"; then
  default_repetitions=1
  default_version_rest_seconds=0
else
  default_repetitions=5
  default_version_rest_seconds=600
fi

REPETITIONS="${REPETITIONS:-$default_repetitions}"
VERSION_REST_SECONDS="${VERSION_REST_SECONDS:-${REST_SECONDS:-$default_version_rest_seconds}}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
COMPOSE_FILE="${COMPOSE_FILE:-infrastructure/docker-compose.benchmark.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-}"
COLLECT_CONTAINER_STATS="${COLLECT_CONTAINER_STATS:-false}"
MEASURE_STARTUP="${MEASURE_STARTUP:-false}"
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-120}"
STATS_INTERVAL_SECONDS="${STATS_INTERVAL_SECONDS:-10}"
F2_RAW_FIRST_REP_ONLY="${F2_RAW_FIRST_REP_ONLY:-true}"
MIN_FREE_DISK_GB="${MIN_FREE_DISK_GB:-0}"
log_file="$results_dir/fargate-$RUN_ID.log"
stats_pid=""
compose_file_path="$(resolve_path "$COMPOSE_FILE")"

compose_cmd=(docker compose -f "$compose_file_path")
if [[ -n "$COMPOSE_PROJECT" ]]; then
  compose_cmd+=(-p "$COMPOSE_PROJECT")
fi

versions=(
  "quarkus-native|http://127.0.0.1:8081"
  "quarkus-jvm|http://127.0.0.1:8082"
  "springboot|http://127.0.0.1:8083"
)

scenarios=(
  "f1_low_load"
  "f2_high_load"
  "f2s_summary_only"
  "f3_burst_autoscaling"
)

if [[ -n "${FARGATE_SCENARIOS:-}" ]]; then
  read -r -a scenarios <<< "${FARGATE_SCENARIOS//,/ }"
fi

if [[ "${#scenarios[@]}" -eq 0 ]]; then
  echo "No Fargate scenarios were selected." >&2
  exit 1
fi

for scenario in "${scenarios[@]}"; do
  if [[ ! -f "$benchmark_dir/scenarios/${scenario}.js" ]]; then
    echo "Scenario file was not found: benchmark/scenarios/${scenario}.js" >&2
    exit 1
  fi
done

compose_services=(
  "postgres"
  "order-service-quarkus-native"
  "order-service-quarkus-jvm"
  "order-service-springboot"
)

epoch_ms() {
  date +%s%3N
}

iso_from_epoch_ms() {
  local epoch_ms_value="$1"
  local epoch_seconds=$((epoch_ms_value / 1000))

  date -d "@$epoch_seconds" -Is
}

compose_service_for_version() {
  local version_name="$1"

  case "$version_name" in
    quarkus-native)
      printf '%s' 'order-service-quarkus-native'
      ;;
    quarkus-jvm)
      printf '%s' 'order-service-quarkus-jvm'
      ;;
    springboot)
      printf '%s' 'order-service-springboot'
      ;;
    *)
      printf '%s' ''
      ;;
  esac
}

container_id_for_service() {
  local service_name="$1"

  "${compose_cmd[@]}" ps -q "$service_name" 2>/dev/null | head -n 1 || true
}

inspect_container_field() {
  local container_id="$1"
  local template="$2"

  if [[ -z "$container_id" ]]; then
    printf '%s' ''
    return 0
  fi

  docker inspect --format "$template" "$container_id" 2>/dev/null || true
}

container_started_ms() {
  local started_at="$1"

  if [[ -z "$started_at" || "$started_at" == "0001-01-01T00:00:00Z" ]]; then
    printf '%s' ''
    return 0
  fi

  date -d "$started_at" +%s%3N 2>/dev/null || true
}

health_path_for_version() {
  local version_name="$1"

  case "$version_name" in
    springboot)
      printf '%s' '/actuator/health'
      ;;
    *)
      printf '%s' '/q/health'
      ;;
  esac
}

print_start_hint() {
  local base_url="$1"

  case "$base_url" in
    http://localhost:8081|http://localhost:8082|http://localhost:8083|http://127.0.0.1:8081|http://127.0.0.1:8082|http://127.0.0.1:8083)
      echo "Start the local benchmark stack first:" >&2
      echo "  docker compose -f $COMPOSE_FILE up --build -d" >&2
      ;;
  esac
}

wait_for_service_ready() {
  local version_name="$1"
  local base_url="$2"
  local health_path
  local timeout_ms=$((STARTUP_TIMEOUT_SECONDS * 1000))
  local started_wait_ms
  local current_ms
  health_path="$(health_path_for_version "$version_name")"
  started_wait_ms="$(epoch_ms)"

  while true; do
    if curl --fail --silent --show-error "${base_url}${health_path}" >/dev/null 2>&1; then
      epoch_ms
      return 0
    fi

    current_ms="$(epoch_ms)"
    if (( current_ms - started_wait_ms >= timeout_ms )); then
      echo "Service $version_name is not reachable at ${base_url}${health_path} after ${STARTUP_TIMEOUT_SECONDS}s." >&2
      print_start_hint "$base_url"
      exit 1
    fi

    sleep 2
  done
}

ensure_service_ready() {
  wait_for_service_ready "$1" "$2" >/dev/null
}

measure_startup_for_version() {
  local version_name="$1"
  local base_url="$2"
  local compose_service
  local container_id
  local container_name
  local container_started_at
  local container_started_epoch_ms
  local check_started_ms
  local first_healthy_epoch_ms
  local first_healthy_at
  local startup_ms=""
  local readiness_wait_ms
  local health_path

  compose_service="$(compose_service_for_version "$version_name")"
  container_id="$(container_id_for_service "$compose_service")"
  container_name="$(inspect_container_field "$container_id" '{{.Name}}')"
  container_name="${container_name#/}"
  container_started_at="$(inspect_container_field "$container_id" '{{.State.StartedAt}}')"
  container_started_epoch_ms="$(container_started_ms "$container_started_at")"
  health_path="$(health_path_for_version "$version_name")"
  check_started_ms="$(epoch_ms)"
  first_healthy_epoch_ms="$(wait_for_service_ready "$version_name" "$base_url")"
  first_healthy_at="$(iso_from_epoch_ms "$first_healthy_epoch_ms")"
  readiness_wait_ms=$((first_healthy_epoch_ms - check_started_ms))

  if [[ -n "$container_started_epoch_ms" && "$first_healthy_epoch_ms" -ge "$container_started_epoch_ms" ]]; then
    startup_ms=$((first_healthy_epoch_ms - container_started_epoch_ms))
  fi

  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$RUN_ID" \
    "$version_name" \
    "$compose_service" \
    "$container_id" \
    "$container_name" \
    "$container_started_at" \
    "$first_healthy_at" \
    "$startup_ms" \
    "$readiness_wait_ms" \
    "${base_url}${health_path}" >> "$startup_file"

  echo "[$(date -Is)] STARTUP version=$version_name service=$compose_service startup_ms=${startup_ms:-unknown} readiness_wait_ms=$readiness_wait_ms health=${base_url}${health_path}" | tee -a "$log_file"
}

measure_startups() {
  startup_file="$results_dir/startup-$RUN_ID.csv"
  echo 'run_id,version,compose_service,container_id,container_name,container_started_at,first_healthy_at,startup_ms,readiness_wait_ms,health_url' > "$startup_file"

  for version in "${versions[@]}"; do
    measure_startup_for_version "${version%%|*}" "${version#*|}"
  done
}

collect_container_stats() {
  local stats_file="$1"
  local interval_seconds="$2"
  local container_ids
  local service_name
  local container_id
  local stats_output
  local timestamp

  while true; do
    timestamp="$(date -Is)"
    container_ids=()

    for service_name in "${compose_services[@]}"; do
      container_id="$(container_id_for_service "$service_name")"
      if [[ -n "$container_id" ]]; then
        container_ids+=("$container_id")
      fi
    done

    if [[ "${#container_ids[@]}" -gt 0 ]]; then
      if stats_output="$(docker stats --no-stream --format '{{.Container}}|{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}|{{.BlockIO}}|{{.PIDs}}' "${container_ids[@]}" 2>/dev/null)"; then
        while IFS='|' read -r container_id container_name cpu_pct mem_usage mem_pct net_io block_io pids; do
          if [[ -z "$container_id" ]]; then
            continue
          fi

          service_name="$(inspect_container_field "$container_id" '{{ index .Config.Labels "com.docker.compose.service" }}')"
          printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$timestamp" \
            "$service_name" \
            "$container_id" \
            "$container_name" \
            "$cpu_pct" \
            "$mem_usage" \
            "$mem_pct" \
            "$net_io" \
            "$block_io" \
            "$pids" >> "$stats_file"
        done <<< "$stats_output"
      fi
    fi

    sleep "$interval_seconds"
  done
}

start_stats_collector() {
  if ! is_true "$COLLECT_CONTAINER_STATS"; then
    return 0
  fi

  if [[ ! "$STATS_INTERVAL_SECONDS" =~ ^[0-9]+$ || "$STATS_INTERVAL_SECONDS" -lt 1 ]]; then
    STATS_INTERVAL_SECONDS=10
  fi

  stats_file="$results_dir/container-stats-$RUN_ID.csv"
  echo 'timestamp,compose_service,container_id,container_name,cpu_pct,mem_usage,mem_pct,net_io,block_io,pids' > "$stats_file"
  collect_container_stats "$stats_file" "$STATS_INTERVAL_SECONDS" &
  stats_pid="$!"
  echo "[$(date -Is)] STATS_START file=$stats_file interval_seconds=$STATS_INTERVAL_SECONDS" | tee -a "$log_file"
}

stop_stats_collector() {
  if [[ -n "$stats_pid" ]]; then
    kill "$stats_pid" 2>/dev/null || true
    wait "$stats_pid" 2>/dev/null || true
    stats_pid=""
  fi
}

trap stop_stats_collector EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Fargate benchmark run $RUN_ID started at $(date -Is)" | tee -a "$log_file"
if [[ -n "${run_config_path:-}" ]]; then
  echo "[$(date -Is)] CONFIG file=$run_config_path" | tee -a "$log_file"
fi
echo "[$(date -Is)] SETTINGS smoke=$SMOKE repetitions=$REPETITIONS version_rest_seconds=$VERSION_REST_SECONDS scenarios=${scenarios[*]} f2_raw_first_rep_only=$F2_RAW_FIRST_REP_ONLY min_free_disk_gb=$MIN_FREE_DISK_GB" | tee -a "$log_file"

# Disk precheck: refuse to start if free space under results_dir is below the
# configured minimum. Avoids a half-finished overnight run when the disk is
# already tight before the first F2 raw JSON is written.
if [[ "${MIN_FREE_DISK_GB:-0}" -gt 0 ]]; then
  free_kb="$(df -P -k "$results_dir" | awk 'NR==2 {print $4}')"
  free_gb=$(( free_kb / 1024 / 1024 ))
  echo "[$(date -Is)] DISK_CHECK results_dir=$results_dir free_gb=$free_gb required_gb=$MIN_FREE_DISK_GB" | tee -a "$log_file"
  if [[ "$free_gb" -lt "$MIN_FREE_DISK_GB" ]]; then
    echo "Free disk under $results_dir is ${free_gb} GB, below required ${MIN_FREE_DISK_GB} GB. Aborting." | tee -a "$log_file" >&2
    exit 1
  fi
fi

start_stats_collector

if is_true "$MEASURE_STARTUP"; then
  measure_startups
fi

for repetition in $(seq 1 "$REPETITIONS"); do
  for version_index in "${!versions[@]}"; do
    version="${versions[$version_index]}"
    version_name="${version%%|*}"
    base_url="${version#*|}"

    echo "[$(date -Is)] PRECHECK version=$version_name health=$(health_path_for_version "$version_name") base_url=$base_url" | tee -a "$log_file"
    ensure_service_ready "$version_name" "$base_url"

    for scenario in "${scenarios[@]}"; do
      result_file="$results_dir/${scenario}_${version_name}_run${repetition}.json"
      summary_file="$results_dir/${scenario}_${version_name}_run${repetition}-summary.json"

      # Output policy: F2 raw JSON is large (~3 GB). When F2_RAW_FIRST_REP_ONLY
      # is true, only repetition 1 of each version emits raw JSON for F2; other
      # repetitions still produce the summary file. All other scenarios always
      # emit raw JSON.
      emit_raw_json=true
      if [[ "$scenario" == "f2_high_load" ]] && is_true "$F2_RAW_FIRST_REP_ONLY" && [[ "$repetition" -ne 1 ]]; then
        emit_raw_json=false
      fi

      k6_args=(run --summary-export "$summary_file")
      if [[ "$emit_raw_json" == "true" ]]; then
        k6_args+=(--out "json=$result_file")
      fi
      k6_args+=("$benchmark_dir/scenarios/${scenario}.js")

      echo "[$(date -Is)] START scenario=$scenario version=$version_name repetition=$repetition base_url=$base_url raw_json=$emit_raw_json" | tee -a "$log_file"

      # Soft-fail the k6 invocation: a non-zero exit (notably 99 = thresholds
      # crossed) must not abort the loop. We capture the exit code and let the
      # orchestrator decide; thresholds remain visible in the summary file.
      set +e
      BASE_URL="$base_url" SMOKE="$SMOKE" "$K6_BIN" "${k6_args[@]}" 2>&1 | tee -a "$log_file"
      k6_status=${PIPESTATUS[0]}
      set -e

      case "$k6_status" in
        0)
          k6_verdict="PASS"
          ;;
        99)
          k6_verdict="THRESHOLD_FAIL"
          ;;
        *)
          k6_verdict="RUN_ERROR"
          ;;
      esac

      result_value="none"
      if [[ "$emit_raw_json" == "true" ]]; then
        result_value="$result_file"
      fi

      echo "[$(date -Is)] END scenario=$scenario version=$version_name repetition=$repetition status=$k6_status verdict=$k6_verdict summary=$summary_file result=$result_value" | tee -a "$log_file"

      # Defensive: if the run errored out in a way other than a normal pass or
      # threshold breach, re-confirm the service is reachable before the next
      # scenario so we do not stack failures on top of a broken container.
      if [[ "$k6_status" -ne 0 && "$k6_status" -ne 99 ]]; then
        echo "[$(date -Is)] RECHECK version=$version_name base_url=$base_url after status=$k6_status" | tee -a "$log_file"
        ensure_service_ready "$version_name" "$base_url"
      fi
    done

    if [[ "$VERSION_REST_SECONDS" -gt 0 && ( "$repetition" -lt "$REPETITIONS" || "$version_index" -lt $((${#versions[@]} - 1)) ) ]]; then
      echo "[$(date -Is)] VERSION_REST version=$version_name repetition=$repetition seconds=$VERSION_REST_SECONDS" | tee -a "$log_file"
      sleep "$VERSION_REST_SECONDS"
    fi
  done
done

echo "Fargate benchmark run $RUN_ID finished at $(date -Is)" | tee -a "$log_file"
