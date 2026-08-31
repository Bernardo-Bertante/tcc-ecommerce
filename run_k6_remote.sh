#!/usr/bin/env bash
set -euo pipefail

# Require SPRINGBOOT_BASE_URL to be provided by the controller (avoid AWS calls on runner)
if [ -z "${SPRINGBOOT_BASE_URL:-}" ]; then
  echo "FAILED_ACTION=SPRINGBOOT_BASE_URL_NOT_PROVIDED"
  exit 1
fi

# Export URL aliases used by scenarios
export SPRINGBOOT_BASE_URL
export BASE_URL="$SPRINGBOOT_BASE_URL"
export SERVICE_BASE_URL="$SPRINGBOOT_BASE_URL"
export ORDER_SERVICE_BASE_URL="$SPRINGBOOT_BASE_URL"
export TARGET_BASE_URL="$SPRINGBOOT_BASE_URL"

# Ensure we're in the benchmark workspace so scenario paths resolve
cd ~/ecommerce-tcc/benchmark || exit 1

# Verify SPRINGBOOT_BASE_URL is not localhost and uses port 8083
if echo "$SPRINGBOOT_BASE_URL" | grep -Eiq "localhost|127\.0\.0\."; then
  echo "FAILED_ACTION=SPRINGBOOT_URL_LOCAL"
  exit 2
fi
if ! echo "$SPRINGBOOT_BASE_URL" | grep -q ":8083"; then
  echo "FAILED_ACTION=SPRINGBOOT_NO_8083"
  exit 3
fi

# Curl /actuator/health from runner and require UP
HEALTH=$(curl -sS --max-time 10 "$SPRINGBOOT_BASE_URL/actuator/health" || true)
echo "$HEALTH" | grep -q '"status":"UP"' || { echo "FAILED_ACTION=HEALTH_NOT_UP"; exit 4; }

# Ensure k6 is available; try user-local binary fallback if not present
if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 not found, attempting user-local binary install"
  mkdir -p "$HOME/.local/bin"
  export PATH="$HOME/.local/bin:$PATH"
  K6_URL="https://github.com/grafana/k6/releases/download/v0.45.0/k6-v0.45.0-linux-amd64.tar.gz"
  TMPDIR=$(mktemp -d)
  if ! curl -sSL "$K6_URL" -o "$TMPDIR/k6.tar.gz"; then
    echo "FAILED_ACTION=K6_DOWNLOAD_FAILED"
    rm -rf "$TMPDIR"
    exit 11
  fi
  tar -xzf "$TMPDIR/k6.tar.gz" -C "$TMPDIR"
  K6_EXTRACT_DIR=$(find "$TMPDIR" -maxdepth 1 -type d -name 'k6-*' | head -n1)
  if [ -z "${K6_EXTRACT_DIR:-}" ] || [ ! -f "$K6_EXTRACT_DIR/k6" ]; then
    echo "FAILED_ACTION=K6_EXTRACT_FAILED"
    rm -rf "$TMPDIR"
    exit 12
  fi
  mv "$K6_EXTRACT_DIR/k6" "$HOME/.local/bin/k6" || { sudo mv "$K6_EXTRACT_DIR/k6" /usr/local/bin/k6 || true; }
  rm -rf "$TMPDIR"
  command -v k6 >/dev/null 2>&1 || { echo "FAILED_ACTION=K6_INSTALL_FAILED"; exit 13; }
fi

# Verify disk free >= 20GB on root
AVAIL_GB=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
if [ -z "$AVAIL_GB" ] || [ "$AVAIL_GB" -lt 20 ]; then
  echo "FAILED_ACTION=NO_DISK_${AVAIL_GB:-0}G"
  exit 8
fi

# Verify no k6 process running
if pgrep -x k6 >/dev/null 2>&1; then
  echo "FAILED_ACTION=K6_RUNNING"
  exit 9
fi

# Run parameters
export F2_RATE=200
export F2_PREWARM_DURATION=2m
export F2_DURATION=3m
export PRE_ALLOCATED_VUS=1500
export MAX_VUS=3000
export ABORT_ON_FAIL=false

RUN_ID_PREFIX="8vcpu16gb-rds-t3medium-f2-200-springboot-vus1500max3000-clean-summaryonly"
RUN_ID="${RUN_ID_PREFIX}-$(date +%Y%m%d-%H%M%S)"
RESULT_DIR="results/${RUN_ID}"
mkdir -p "$RESULT_DIR"
SCENARIO_FILE="scenarios/f2_high_load.js"

# Start k6 in background (summary-export only)
K6_BIN=$(command -v k6 || true)
nohup "$K6_BIN" run --summary-export "$RESULT_DIR/f2_high_load_springboot_run1-summary.json" "$SCENARIO_FILE" > "$RESULT_DIR/run.log" 2>&1 &
K6_PID=$!

sleep 2
if kill -0 "$K6_PID" >/dev/null 2>&1; then
  echo "STATUS=STARTED"
  META_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || true)
  echo "RUNNER_IP=${META_IP:-}" 
  echo "RUN_ID=$RUN_ID"
  echo "K6_PID=$K6_PID"
  echo "RESULT_DIR=$RESULT_DIR"
  echo "---LOG_TAIL_LAST_40_LINES---"
  tail -n 40 "$RESULT_DIR/run.log" || true
  exit 0
else
  wait "$K6_PID" || true
  EXIT_CODE=$?
  echo "FAILED_ACTION=K6_EXITED_IMMEDIATELY"
  echo "EXIT_CODE=$EXIT_CODE"
  echo "RUN_ID=$RUN_ID"
  echo "RESULT_DIR=$RESULT_DIR"
  echo "---LOG_TAIL_LAST_120_LINES---"
  tail -n 120 "$RESULT_DIR/run.log" || true
  exit 10
fi
