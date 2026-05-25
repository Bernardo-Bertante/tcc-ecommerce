#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  reset-order-service-db.sh [options]

Options:
  --stack-name NAME   CloudFormation stack name. Default: order-service-benchmark.
  --profile PROFILE   AWS CLI profile.
  --region REGION     AWS region.
  -h, --help          Show this help.
EOF
}

STACK_NAME="order-service-benchmark"
PROFILE=""
REGION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name)
      STACK_NAME="$2"
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

AWS_ARGS=()
if [[ -n "$PROFILE" ]]; then
  AWS_ARGS+=(--profile "$PROFILE")
fi
if [[ -n "$REGION" ]]; then
  AWS_ARGS+=(--region "$REGION")
fi

output_value() {
  local key="$1"
  aws "${AWS_ARGS[@]}" cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue | [0]" \
    --output text
}

cluster_name="$(output_value EcsClusterName)"
task_definition="$(output_value DbResetTaskDefinitionArn)"
subnet_ids="$(output_value PublicSubnetIds)"
security_group_id="$(output_value TaskSecurityGroupId)"

if [[ -z "$cluster_name" || -z "$task_definition" || -z "$subnet_ids" || -z "$security_group_id" ]]; then
  echo "Could not resolve reset task outputs from stack $STACK_NAME." >&2
  exit 1
fi

task_arn="$(aws "${AWS_ARGS[@]}" ecs run-task \
  --cluster "$cluster_name" \
  --launch-type FARGATE \
  --task-definition "$task_definition" \
  --network-configuration "awsvpcConfiguration={subnets=[$subnet_ids],securityGroups=[$security_group_id],assignPublicIp=ENABLED}" \
  --query 'tasks[0].taskArn' \
  --output text)"

if [[ -z "$task_arn" || "$task_arn" == "None" ]]; then
  echo "Failed to start database reset task." >&2
  exit 1
fi

aws "${AWS_ARGS[@]}" ecs wait tasks-stopped --cluster "$cluster_name" --tasks "$task_arn"

exit_code="$(aws "${AWS_ARGS[@]}" ecs describe-tasks \
  --cluster "$cluster_name" \
  --tasks "$task_arn" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)"

if [[ "$exit_code" != "0" ]]; then
  aws "${AWS_ARGS[@]}" ecs describe-tasks --cluster "$cluster_name" --tasks "$task_arn" --output table >&2
  exit 1
fi

echo "Order Service database reset completed: task=$task_arn"