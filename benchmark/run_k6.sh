#!/usr/bin/env bash
# Canonical runner: this is the canonical benchmark `run_k6.sh` used by authors and CI.
# Compatibility: use `benchmark/run/run_k6.sh` only as a thin compatibility wrapper.
set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-pessoal}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-order-service-benchmark}"
K6_BIN="${K6_BIN:-k6}"
SCENARIO="${SCENARIO:-f3s_stress_300}"
RUNTIME="${RUNTIME:-springboot}"

if ! command -v "$K6_BIN" >/dev/null 2>&1; then
	echo "k6 was not found. Install k6 or set K6_BIN." >&2
	exit 1
fi

benchmark_dir="$(cd "$(dirname "$0")" && pwd)"

resolve_base_url() {
	local runtime="$1"

	if [[ -n "${BASE_URL:-}" ]]; then
		printf '%s' "$BASE_URL"
		return 0
	fi

	if ! command -v aws >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
		return 1
	fi

	local output_key
	case "$runtime" in
		springboot) output_key="SpringBootBaseUrl" ;;
		quarkus-jvm) output_key="QuarkusJvmBaseUrl" ;;
		quarkus-native) output_key="QuarkusNativeBaseUrl" ;;
		*) return 1 ;;
	esac

	aws cloudformation describe-stacks \
		--stack-name "$STACK_NAME" \
		--profile "$AWS_PROFILE" \
		--region "$AWS_REGION" 2>/dev/null \
		| jq -r --arg key "$output_key" '.Stacks[0].Outputs[] | select(.OutputKey==$key) .OutputValue' \
		| head -n 1
}

scenario_file="scenarios/${SCENARIO}.js"
if [[ ! -f "$benchmark_dir/$scenario_file" ]]; then
	echo "Scenario file not found: $scenario_file" >&2
	exit 1
fi

if [[ -z "${BASE_URL:-}" ]]; then
	BASE_URL="$(resolve_base_url "$RUNTIME" || true)"
fi

if [[ -z "${BASE_URL:-}" ]]; then
	echo "BASE_URL is required (or resolvable from CloudFormation outputs)." >&2
	exit 1
fi

export BASE_URL
export SERVICE_BASE_URL="$BASE_URL"
export ORDER_SERVICE_BASE_URL="$BASE_URL"
export TARGET_BASE_URL="$BASE_URL"
export ABORT_ON_FAIL="${ABORT_ON_FAIL:-false}"
export PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS:-1500}"
export MAX_VUS="${MAX_VUS:-3000}"

case "$SCENARIO" in
	f1_low_load)
		export F1_RATE="${F1_RATE:-30}"
		default_prefix="official-clean-8vcpu16gb-rds-t3medium-f1-30-${RUNTIME}-summaryonly"
		summary_name="f1_low_load_${RUNTIME}_run1-summary.json"
		;;
	f2_high_load)
		export F2_WARMUP_RATE="${F2_WARMUP_RATE:-30}"
		export F2_RATE="${F2_RATE:-60}"
		default_prefix="official-clean-8vcpu16gb-rds-t3medium-f2-60-${RUNTIME}-summaryonly"
		summary_name="f2_high_load_${RUNTIME}_run1-summary.json"
		;;
	f2s_summary_only)
		export F2S_RATE="${F2S_RATE:-60}"
		default_prefix="official-clean-8vcpu16gb-rds-t3medium-f2s-summary-60-${RUNTIME}-summaryonly"
		summary_name="f2s_summary_only_${RUNTIME}_run1-summary.json"
		;;
	f3_burst_autoscaling)
		export F3_BASELINE_RATE="${F3_BASELINE_RATE:-30}"
		export F3_AVERAGE_RATE="${F3_AVERAGE_RATE:-225}"
		export F3_STRESS_RATE="${F3_STRESS_RATE:-300}"
		default_prefix="official-clean-8vcpu16gb-rds-t3medium-f3-blackfriday-225-300-${RUNTIME}-summaryonly"
		summary_name="f3_burst_autoscaling_${RUNTIME}_run1-summary.json"
		;;
	f3s_stress_300)
		export F3S_RATE="${F3S_RATE:-300}"
		default_prefix="official-clean-8vcpu16gb-rds-t3medium-f3s-300-${RUNTIME}-vus1500max3000-summaryonly"
		summary_name="f3s_stress_300_${RUNTIME}_run1-summary.json"
		;;
	*)
		echo "Unsupported scenario: $SCENARIO" >&2
		exit 1
		;;
esac

timestamp="$(date +%Y%m%d-%H%M%S)"
run_id="${RUN_ID:-${default_prefix}-${timestamp}}"
result_dir="$benchmark_dir/results/$run_id"
mkdir -p "$result_dir"

echo "RUN_ID=$run_id"
echo "SCENARIO=$SCENARIO"
echo "BASE_URL=$BASE_URL"
echo "RESULT_DIR=$result_dir"

"$K6_BIN" run --summary-export "$result_dir/$summary_name" "$benchmark_dir/$scenario_file" > "$result_dir/run.log" 2>&1
echo "DONE scenario=$SCENARIO summary=$result_dir/$summary_name log=$result_dir/run.log"
