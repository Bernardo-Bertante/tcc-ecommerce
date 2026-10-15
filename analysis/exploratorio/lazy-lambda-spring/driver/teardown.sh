#!/bin/bash
# exp-lazy-sb idempotent teardown. Arg: DONE | FAILED:<reason> | SAFETY | DRYRUN
#  - deletes the 3 exp-lazy functions, the 2 exp-lazy tables, exp-lazy-sb-role, and the 3 /aws/lambda/exp-lazy-sb-*
#    log groups (only if their raw events are already in S3); writes DONE/FAILED + STATUS to S3; shuts the EC2
#    down (InstanceInitiatedShutdownBehavior=terminate). DRYRUN deletes nothing and does not shut down.
#  - exp-lazy-sb-driver-role/instance profile and the bucket stay for Phase C (the instance still uses them).
set -uo pipefail
REASON="${1:-SAFETY}"
HOME_DIR=/opt/exp-lazy-sb
export AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""
exec 9>"$HOME_DIR/teardown.lock"
flock -n 9 || { echo "teardown already running"; exit 0; }
# shellcheck disable=SC1091
source "$HOME_DIR/current.env" 2>/dev/null || { RUN_ID="no-run"; WORK="$HOME_DIR/work-no-run"; MODE=full; BUCKET=exp-lazy-sb-results-776648109551; RUN_START_MS=$(( ($(date +%s) - 14400) * 1000 )); }
export RUN_ID WORK BUCKET RUN_START_MS
mkdir -p "$WORK"
LOG="$WORK/teardown.log"
exec >>"$LOG" 2>&1
echo "[$(date -Is)] TEARDOWN reason=$REASON run=$RUN_ID"

FUNCS="exp-lazy-sb-v0 exp-lazy-sb-v1 exp-lazy-sb-v2"
TABLES="exp-lazy-sb-processed-orders exp-lazy-sb-stock-reservations"

if [[ "$REASON" == "SAFETY" ]]; then
  echo "safety timer fired: stopping driver"
  systemctl stop exp-lazy-sb-run.service 2>/dev/null || true
  pkill -f "$HOME_DIR/work-.*/driver.py" || true
  pkill -f "$HOME_DIR/run_all.sh" || true
  REASON="FAILED: safety timer fired before normal end"
fi

# 1) raw logs must be in S3 before the log groups can go
logs_in_s3() {
  for f in $FUNCS; do
    aws s3 ls "s3://$BUCKET/$RUN_ID/raw/logs_$f.jsonl.gz" >/dev/null 2>&1 || return 1
  done
  return 0
}
if ! logs_in_s3 && [[ -f "$WORK/samples.jsonl" ]]; then
  echo "raw logs not in S3 yet: trying extract.py once"
  (cd "$WORK" && timeout 900 python3 "$WORK/extract.py") || echo "extract.py failed/incomplete (rc=$?)"
  aws s3 cp --only-show-errors --recursive "$WORK/raw" "s3://$BUCKET/$RUN_ID/raw/" || true
  aws s3 cp --only-show-errors "$WORK/samples.jsonl" "s3://$BUCKET/$RUN_ID/raw/samples.jsonl" || true
fi
LOGS_OK=no; logs_in_s3 && LOGS_OK=yes
echo "raw logs in S3: $LOGS_OK"

if [[ "$REASON" == "DRYRUN" ]]; then
  echo "DRYRUN: would delete functions [$FUNCS], tables [$TABLES], role exp-lazy-sb-role, log groups (logs_ok=$LOGS_OK)"
  for f in $FUNCS; do aws lambda get-function-configuration --function-name "$f" --query '[FunctionName,LastUpdateStatus]' --output text; done
  for t in $TABLES; do aws dynamodb describe-table --table-name "$t" --query 'Table.[TableName,TableStatus]' --output text; done
  aws iam list-role-policies --role-name exp-lazy-sb-role --output text
  aws logs describe-log-groups --log-group-name-prefix /aws/lambda/exp-lazy-sb- --query 'logGroups[].logGroupName' --output text
  echo "$(date -Is) RUN_ID=$RUN_ID DRYRUN_TEARDOWN_OK logs_in_s3=$LOGS_OK" > "$WORK/STATUS"
  aws s3 cp --only-show-errors "$LOG" "s3://$BUCKET/$RUN_ID/teardown.log"
  aws s3 cp --only-show-errors "$WORK/STATUS" "s3://$BUCKET/$RUN_ID/STATUS"
  aws s3 cp --only-show-errors "$WORK/STATUS" "s3://$BUCKET/STATUS"
  exit 0
fi

for f in $FUNCS; do
  aws lambda delete-function --function-name "$f" && echo "deleted function $f" || echo "delete-function $f: failed/absent"
done
for t in $TABLES; do
  aws dynamodb delete-table --table-name "$t" --query 'TableDescription.TableStatus' --output text \
    && echo "deleted table $t" || echo "delete-table $t: failed/absent"
done
for p in $(aws iam list-role-policies --role-name exp-lazy-sb-role --query 'PolicyNames[]' --output text 2>/dev/null); do
  aws iam delete-role-policy --role-name exp-lazy-sb-role --policy-name "$p" && echo "deleted role policy $p"
done
aws iam delete-role --role-name exp-lazy-sb-role && echo "deleted role exp-lazy-sb-role" || echo "delete-role: failed/absent"
if [[ "$LOGS_OK" == "yes" ]]; then
  for f in $FUNCS; do
    aws logs delete-log-group --log-group-name "/aws/lambda/$f" && echo "deleted log group $f" || echo "delete-log-group $f: failed/absent"
  done
else
  echo "log groups KEPT (raw events not confirmed in S3; retention 7 days)"
fi

sleep 5
{
  echo "$(date -Is) RUN_ID=$RUN_ID FINAL reason=$REASON raw_logs_in_s3=$LOGS_OK"
  echo "residual lambda: $(aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`exp-lazy-sb-`)].FunctionName' --output text 2>&1)"
  echo "residual dynamodb: $(aws dynamodb list-tables --query 'TableNames[?starts_with(@,`exp-lazy-sb-`)]' --output text 2>&1)"
  for t in $TABLES; do echo "  table $t status: $(aws dynamodb describe-table --table-name "$t" --query Table.TableStatus --output text 2>&1 | head -1)"; done
  echo "residual role exp-lazy-sb-role: $(aws iam get-role --role-name exp-lazy-sb-role --query Role.RoleName --output text 2>&1 | head -1)"
  echo "residual log groups: $(aws logs describe-log-groups --log-group-name-prefix /aws/lambda/exp-lazy-sb- --query 'logGroups[].logGroupName' --output text 2>&1)"
  echo "kept for Phase C: exp-lazy-sb-driver-role + instance profile, bucket $BUCKET; this EC2 terminates on shutdown"
} > "$WORK/STATUS"
cat "$WORK/STATUS"
aws s3 cp --only-show-errors "$LOG" "s3://$BUCKET/$RUN_ID/teardown.log"
[[ -f "$WORK/run.log" ]] && aws s3 cp --only-show-errors "$WORK/run.log" "s3://$BUCKET/$RUN_ID/run.log"
aws s3 cp --only-show-errors "$WORK/STATUS" "s3://$BUCKET/$RUN_ID/STATUS"
aws s3 cp --only-show-errors "$WORK/STATUS" "s3://$BUCKET/STATUS"
if [[ "$REASON" == "DONE" ]]; then
  echo "$(date -Is) $RUN_ID" > "$WORK/DONE"
  aws s3 cp --only-show-errors "$WORK/DONE" "s3://$BUCKET/$RUN_ID/DONE"
  aws s3 cp --only-show-errors "$WORK/DONE" "s3://$BUCKET/DONE"
else
  echo "$(date -Is) $RUN_ID $REASON" > "$WORK/FAILED"
  aws s3 cp --only-show-errors "$WORK/FAILED" "s3://$BUCKET/$RUN_ID/FAILED"
  aws s3 cp --only-show-errors "$WORK/FAILED" "s3://$BUCKET/FAILED"
fi
echo "[$(date -Is)] shutting down (instance terminates)"
aws s3 cp --only-show-errors "$LOG" "s3://$BUCKET/$RUN_ID/teardown.log"
shutdown -h now
