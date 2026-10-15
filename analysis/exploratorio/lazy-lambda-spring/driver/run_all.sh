#!/bin/bash
# exp-lazy: runs everything on the exp-lazy-sb-driver EC2, with no human decisions.
#   MODE=smoke -> BLOCKS (default 3) + extraction + analysis + upload + teardown DRYRUN (deletes nothing)
#   MODE=full  -> BLOCKS (default 30) + extraction + analysis + upload + real teardown + EC2 shutdown (terminate)
set -Eeuo pipefail
MODE="${MODE:-full}"
HOME_DIR=/opt/exp-lazy-sb
export AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""
export BUCKET="${BUCKET:-exp-lazy-sb-results-776648109551}"
export RUN_ID="${MODE}-$(date -u +%Y%m%dT%H%M%SZ)"
export WORK="$HOME_DIR/work-$RUN_ID"
export RUN_START_MS=$(( $(date +%s) * 1000 - 60000 ))
if [[ "$MODE" == "smoke" ]]; then export BLOCKS="${BLOCKS:-3}"; else export BLOCKS="${BLOCKS:-30}"; fi
mkdir -p "$WORK"
cp "$HOME_DIR"/{driver.py,extract.py,analyze.py,l1_payloads.json,l1_duration_postinit.csv} "$WORK"/
printf 'RUN_ID=%s\nWORK=%s\nMODE=%s\nRUN_START_MS=%s\nBUCKET=%s\n' "$RUN_ID" "$WORK" "$MODE" "$RUN_START_MS" "$BUCKET" \
  > "$HOME_DIR/current.env"
exec > >(tee -a "$WORK/run.log") 2>&1

upload() {
  aws s3 cp --only-show-errors --recursive "$WORK" "s3://$BUCKET/$RUN_ID/" \
    --exclude "resp.json" --exclude "event_*.json" || true
}
status() {
  echo "$(date -Is) RUN_ID=$RUN_ID $*" > "$WORK/STATUS"
  aws s3 cp --only-show-errors "$WORK/STATUS" "s3://$BUCKET/$RUN_ID/STATUS" || true
  aws s3 cp --only-show-errors "$WORK/STATUS" "s3://$BUCKET/STATUS" || true
}
on_err() {
  local line="$1"
  trap - ERR
  echo "[$(date -Is)] ERROR at line $line"
  status "FAILED at run_all.sh line $line (teardown starting)"
  upload
  if [[ "$MODE" == "full" ]]; then "$HOME_DIR/teardown.sh" "FAILED: run_all.sh line $line"; else "$HOME_DIR/teardown.sh" DRYRUN; fi
  exit 1
}
trap 'on_err $LINENO' ERR

echo "[$(date -Is)] START mode=$MODE run=$RUN_ID blocks=$BLOCKS"
aws sts get-caller-identity
aws --version
python3 --version
status "STARTED mode=$MODE blocks=$BLOCKS"

python3 "$WORK/driver.py"
status "EXTRACTING"
sleep 30
python3 "$WORK/extract.py"
upload
status "ANALYZING"
python3 "$WORK/analyze.py"
upload
status "ANALYSIS_DONE; teardown next"
trap - ERR
if [[ "$MODE" == "full" ]]; then
  "$HOME_DIR/teardown.sh" DONE
else
  "$HOME_DIR/teardown.sh" DRYRUN
fi
