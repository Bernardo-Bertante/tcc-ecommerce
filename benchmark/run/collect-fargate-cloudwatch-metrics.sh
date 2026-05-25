#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  collect-fargate-cloudwatch-metrics.sh --stack-name NAME --run-id RUN_ID --start-time ISO --end-time ISO [options]

Options:
  --profile PROFILE       AWS CLI profile.
  --region REGION         AWS region.
  --output-dir DIR        Output directory. Default: benchmark/results/<RUN_ID>.
  --period SECONDS        CloudWatch period. Default: 60.
  -h, --help              Show this help.
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
STACK_NAME=""
RUN_ID=""
START_TIME=""
END_TIME=""
PROFILE=""
REGION=""
OUTPUT_DIR=""
PERIOD="60"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    --start-time)
      START_TIME="$2"
      shift 2
      ;;
    --end-time)
      END_TIME="$2"
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
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --period)
      PERIOD="$2"
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

if [[ -z "$STACK_NAME" || -z "$RUN_ID" || -z "$START_TIME" || -z "$END_TIME" ]]; then
  echo "--stack-name, --run-id, --start-time, and --end-time are required." >&2
  usage >&2
  exit 1
fi
if ! command -v aws > /dev/null 2>&1; then
  echo "aws CLI is required." >&2
  exit 1
fi

AWS_ARGS=()
if [[ -n "$PROFILE" ]]; then
  AWS_ARGS+=(--profile "$PROFILE")
fi
if [[ -n "$REGION" ]]; then
  AWS_ARGS+=(--region "$REGION")
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$BENCHMARK_DIR/results/$RUN_ID"
fi
mkdir -p "$OUTPUT_DIR"

output_value() {
  local key="$1"
  aws "${AWS_ARGS[@]}" cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue | [0]" \
    --output text
}

metric_statistics() {
  local namespace="$1"
  local metric_name="$2"
  local dimensions="$3"
  local statistics="$4"

  aws "${AWS_ARGS[@]}" cloudwatch get-metric-statistics \
    --namespace "$namespace" \
    --metric-name "$metric_name" \
    --dimensions $dimensions \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --period "$PERIOD" \
    --statistics $statistics \
    --output json
}

cluster_name="$(output_value EcsClusterName)"
load_balancer_full_name="$(output_value LoadBalancerFullName)"
database_id="$(output_value DatabaseInstanceIdentifier)"

declare -A service_outputs=(
  [springboot]="$(output_value SpringBootServiceName)"
  [quarkus-jvm]="$(output_value QuarkusJvmServiceName)"
  [quarkus-native]="$(output_value QuarkusNativeServiceName)"
)

declare -A target_group_outputs=(
  [springboot]="$(output_value SpringBootTargetGroupArn)"
  [quarkus-jvm]="$(output_value QuarkusJvmTargetGroupArn)"
  [quarkus-native]="$(output_value QuarkusNativeTargetGroupArn)"
)

target_group_full_name() {
  local arn="$1"
  printf '%s' "$arn" | awk -F':targetgroup/' '{print $2}'
}

metrics_file="$OUTPUT_DIR/metrics_${RUN_ID}_cloudwatch.jsonl"
: > "$metrics_file"

for version in springboot quarkus-jvm quarkus-native; do
  service_name="${service_outputs[$version]}"
  target_group_name="$(target_group_full_name "${target_group_outputs[$version]}")"

  printf '{"run_id":"%s","version":"%s","namespace":"AWS/ECS","metric":"CPUUtilization","data":%s}\n' \
    "$RUN_ID" "$version" \
    "$(metric_statistics AWS/ECS CPUUtilization "Name=ClusterName,Value=$cluster_name Name=ServiceName,Value=$service_name" "Average Maximum")" >> "$metrics_file"

  printf '{"run_id":"%s","version":"%s","namespace":"AWS/ECS","metric":"MemoryUtilization","data":%s}\n' \
    "$RUN_ID" "$version" \
    "$(metric_statistics AWS/ECS MemoryUtilization "Name=ClusterName,Value=$cluster_name Name=ServiceName,Value=$service_name" "Average Maximum")" >> "$metrics_file"

  printf '{"run_id":"%s","version":"%s","namespace":"AWS/ApplicationELB","metric":"TargetResponseTime","data":%s}\n' \
    "$RUN_ID" "$version" \
    "$(metric_statistics AWS/ApplicationELB TargetResponseTime "Name=LoadBalancer,Value=$load_balancer_full_name Name=TargetGroup,Value=$target_group_name" "Average Maximum")" >> "$metrics_file"

  printf '{"run_id":"%s","version":"%s","namespace":"AWS/ApplicationELB","metric":"HTTPCode_Target_5XX_Count","data":%s}\n' \
    "$RUN_ID" "$version" \
    "$(metric_statistics AWS/ApplicationELB HTTPCode_Target_5XX_Count "Name=LoadBalancer,Value=$load_balancer_full_name Name=TargetGroup,Value=$target_group_name" "Sum")" >> "$metrics_file"
done

printf '{"run_id":"%s","namespace":"AWS/RDS","metric":"CPUUtilization","data":%s}\n' \
  "$RUN_ID" \
  "$(metric_statistics AWS/RDS CPUUtilization "Name=DBInstanceIdentifier,Value=$database_id" "Average Maximum")" >> "$metrics_file"

printf '{"run_id":"%s","namespace":"AWS/RDS","metric":"DatabaseConnections","data":%s}\n' \
  "$RUN_ID" \
  "$(metric_statistics AWS/RDS DatabaseConnections "Name=DBInstanceIdentifier,Value=$database_id" "Average Maximum")" >> "$metrics_file"

printf '{"run_id":"%s","namespace":"AWS/RDS","metric":"ReadLatency","data":%s}\n' \
  "$RUN_ID" \
  "$(metric_statistics AWS/RDS ReadLatency "Name=DBInstanceIdentifier,Value=$database_id" "Average Maximum")" >> "$metrics_file"

printf '{"run_id":"%s","namespace":"AWS/RDS","metric":"WriteLatency","data":%s}\n' \
  "$RUN_ID" \
  "$(metric_statistics AWS/RDS WriteLatency "Name=DBInstanceIdentifier,Value=$database_id" "Average Maximum")" >> "$metrics_file"

echo "CloudWatch metrics written to $metrics_file"