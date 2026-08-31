#!/bin/bash
set -euo pipefail
cd "$HOME/ecommerce-tcc/benchmark"
SPRINGBOOT_BASE_URL="http://order-service-alb-1171103051.us-east-1.elb.amazonaws.com:8083"
export SPRINGBOOT_BASE_URL
export BASE_URL="$SPRINGBOOT_BASE_URL"
export SERVICE_BASE_URL="$SPRINGBOOT_BASE_URL"
export ORDER_SERVICE_BASE_URL="$SPRINGBOOT_BASE_URL"
export TARGET_BASE_URL="$SPRINGBOOT_BASE_URL"

echo "ENV:"
env | grep -E 'BASE_URL|SPRING|ORDER|TARGET' || true

echo "Health:"
curl --max-time 10 "$SPRINGBOOT_BASE_URL/actuator/health" || true

RUN_ID_PREFIX='8vcpu16gb-rds-t3medium-f2-250-springboot-vus1500max3000-clean-summaryonly'
RUN_ID="${RUN_ID_PREFIX}-$(date +%Y%m%d-%H%M%S)"
RESULT_DIR="results/${RUN_ID}"
mkdir -p "$RESULT_DIR"
SCENARIO_FILE='scenarios/f2_high_load.js'
export F2_RATE=250
export F2_PREWARM_DURATION=2m
export F2_DURATION=3m
export PRE_ALLOCATED_VUS=1500
export MAX_VUS=3000
export ABORT_ON_FAIL=false

nohup "$HOME/.local/bin/k6" run --summary-export "$RESULT_DIR/f2_high_load_springboot_run1-summary.json" "$SCENARIO_FILE" > "$RESULT_DIR/run.log" 2>&1 &
K6_PID=$!
echo "STATUS=STARTED"
echo "RUN_ID=$RUN_ID"
echo "K6_PID=$K6_PID"
echo "RESULT_DIR=$RESULT_DIR"
exit 0
