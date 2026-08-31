#!/usr/bin/env bash
# Canonical remote runner: this is the canonical `remote_run_k6.sh` intended for runner machines.
# Compatibility: use `benchmark/run/remote_run_k6.sh` only as a thin compatibility wrapper.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 BASE_URL SCENARIO [RUNTIME] [RUN_ID_PREFIX]" >&2
  exit 2
fi

BASE_URL="$1"
SCENARIO="$2"
RUNTIME="${3:-springboot}"
RUN_ID_PREFIX="${4:-}"

AWS_PROFILE="${AWS_PROFILE:-pessoal}"
AWS_REGION="${AWS_REGION:-us-east-1}"
WORKDIR="${WORKDIR:-$HOME/ecommerce-tcc/benchmark}"
K6_BIN="${K6_BIN:-$HOME/.local/bin/k6}"

if ! command -v "$K6_BIN" >/dev/null 2>&1; then
  echo "k6 was not found at K6_BIN=$K6_BIN" >&2
  exit 1
fi

case "$SCENARIO" in
  f1_low_load)
    export F1_RATE="${F1_RATE:-30}"
    default_prefix="official-clean-8vcpu16gb-rds-t3medium-f1-30-${RUNTIME}-summaryonly"
    summary_file="f1_low_load_${RUNTIME}_run1-summary.json"
    ;;
  f2_high_load)
    export F2_WARMUP_RATE="${F2_WARMUP_RATE:-30}"
    export F2_RATE="${F2_RATE:-60}"
    default_prefix="official-clean-8vcpu16gb-rds-t3medium-f2-60-${RUNTIME}-summaryonly"
    summary_file="f2_high_load_${RUNTIME}_run1-summary.json"
    ;;
  f2s_summary_only)
    export F2S_RATE="${F2S_RATE:-60}"
    default_prefix="official-clean-8vcpu16gb-rds-t3medium-f2s-summary-60-${RUNTIME}-summaryonly"
    summary_file="f2s_summary_only_${RUNTIME}_run1-summary.json"
    ;;
  f3_burst_autoscaling)
    export F3_BASELINE_RATE="${F3_BASELINE_RATE:-30}"
    export F3_AVERAGE_RATE="${F3_AVERAGE_RATE:-225}"
    export F3_STRESS_RATE="${F3_STRESS_RATE:-300}"
    default_prefix="official-clean-8vcpu16gb-rds-t3medium-f3-blackfriday-225-300-${RUNTIME}-summaryonly"
    summary_file="f3_burst_autoscaling_${RUNTIME}_run1-summary.json"
    ;;
  f3s_stress_300)
    export F3S_RATE="${F3S_RATE:-300}"
    default_prefix="official-clean-8vcpu16gb-rds-t3medium-f3s-300-${RUNTIME}-vus1500max3000-summaryonly"
    summary_file="f3s_stress_300_${RUNTIME}_run1-summary.json"
    ;;
  *)
    echo "Unsupported scenario: $SCENARIO" >&2
    exit 1
    ;;
esac

timestamp="$(date +%Y%m%d-%H%M%S)"
run_id_prefix="${RUN_ID_PREFIX:-$default_prefix}"
RUN_ID="${run_id_prefix}-${timestamp}"
RESULT_DIR="$WORKDIR/results/$RUN_ID"
mkdir -p "$RESULT_DIR"
cd "$WORKDIR"

export AWS_PROFILE AWS_REGION
export BASE_URL
export SERVICE_BASE_URL="$BASE_URL"
export ORDER_SERVICE_BASE_URL="$BASE_URL"
export TARGET_BASE_URL="$BASE_URL"
export PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS:-1500}"
export MAX_VUS="${MAX_VUS:-3000}"
export ABORT_ON_FAIL="${ABORT_ON_FAIL:-false}"

START_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
nohup "$K6_BIN" run --summary-export "$RESULT_DIR/$summary_file" "scenarios/${SCENARIO}.js" > "$RESULT_DIR/run.log" 2>&1 &
K6_PID=$!

echo "K6_PID=$K6_PID"
echo "START_TIME=$START_TIME"
wait "$K6_PID"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "END_TIME=$END_TIME"
echo "RESULT_DIR=$RESULT_DIR"
