#!/bin/bash
set -euo pipefail
cd ~/ecommerce-tcc/benchmark || exit 0
RESULTS_DIR=results
LATEST=$(ls -1t "$RESULTS_DIR" 2>/dev/null | head -n1 || true)
K6_PIDS=$(pgrep -a k6 2>/dev/null || true)
SUMMARY_FILE="${RESULTS_DIR}/${LATEST}/f2_high_load_springboot_run1-summary.json"
RUN_LOG="${RESULTS_DIR}/${LATEST}/run.log"
if [ -n "$K6_PIDS" ]; then
  STATUS=RUNNING
elif [ -n "$LATEST" ] && [ -f "$SUMMARY_FILE" ]; then
  STATUS=COMPLETED
elif [ -n "$LATEST" ] && [ -f "$RUN_LOG" ]; then
  STATUS=FINISHED_NO_SUMMARY
else
  STATUS=NO_RUN
fi
# Output exactly the requested fields
echo "STATUS=$STATUS"
# Resolve public IP from metadata is not needed; caller knows IP. We'll print the arg if passed, else leave blank
if [ -n "${1-}" ]; then
  echo "RUNNER_IP=${1}"
else
  echo "RUNNER_IP="
fi
echo "RUN_ID=${LATEST}"
# ps aux | grep k6 | grep -v grep
if [ -n "$K6_PIDS" ]; then
  ps aux | grep k6 | grep -v grep || true
else
  echo "(no k6 process)"
fi
# latest results directory
if [ -n "$LATEST" ]; then
  echo "LATEST_RESULTS_DIR=${RESULTS_DIR}/${LATEST}"
else
  echo "LATEST_RESULTS_DIR="
fi
# ls -lh of latest results directory
if [ -n "$LATEST" ]; then
  ls -lh "${RESULTS_DIR}/${LATEST}" || true
else
  echo "(no dir)"
fi
# tail -n 80 run.log if exists
if [ -n "$LATEST" ] && [ -f "$RUN_LOG" ]; then
  echo "---BEGIN_RUN.LOG---"
  tail -n 80 "$RUN_LOG" || true
  echo "---END_RUN.LOG---"
else
  echo "(no run.log)"
fi
# whether summary JSON exists
if [ -n "$LATEST" ] && [ -f "$SUMMARY_FILE" ]; then
  echo "SUMMARY_EXISTS=YES"
else
  echo "SUMMARY_EXISTS=NO"
fi
