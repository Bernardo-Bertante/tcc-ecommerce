#!/usr/bin/env bash
# Uso: run_round.sh <sb|qj> <round> <cid>
# Uma repeticao do F3 oficial (48 -> 240 -> 48, 25 min) contra app ja em pe.
# Exploratorio; nao e resultado formal do TCC.
set -euo pipefail
ver=$1; round=$2; cid=$3
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
OUT="$HERE/results"; mkdir -p "$OUT"
tag="$ver-r$round"
name=gcf3-app
cg=/sys/fs/cgroup/system.slice/docker-$cid.scope

# offset do gc.log ANTES da rodada -> permite fatiar a rodada exata depois
gcoff=$($D exec $name sh -c 'wc -c < /tmp/gc.log' | tr -d ' \r')
rows_before=$($D exec gcf3-pg psql -tAq -U orderuser -d orderdb -c 'select count(*) from orders;' | tr -d ' \r')

( while true; do
    echo "$(date +%s.%N)	$(awk '/usage_usec/{print $2}' $cg/cpu.stat)	$(cat $cg/memory.current)"
    sleep 1
  done ) > "$OUT/$tag.cpu.tsv" 2>/dev/null &
sampler=$!
trap 'kill $sampler 2>/dev/null || true' EXIT

k6start=$(date +%s)
# DUR_OVERRIDE so e usado no smoke de encanamento; vazio = duracoes oficiais do F3
read -r -a duropt <<< "${DUR_OVERRIDE:-}"
taskset -c 10-15 k6 run -q \
  -e BASE_URL=http://127.0.0.1:9301 \
  -e F3_BASELINE_RATE=48 -e F3_PEAK_RATE=240 -e F3_RECOVERY_RATE=48 \
  -e PRE_ALLOCATED_VUS=1500 -e MAX_VUS=3000 "${duropt[@]}" \
  --summary-export "$OUT/$tag.summary.json" \
  --out csv="$OUT/$tag.k6.csv" \
  "$REPO/benchmark/scenarios/f3_black_friday_controlled.js" \
  > "$OUT/$tag.k6.log" 2>&1 && k6exit=0 || k6exit=$?
k6end=$(date +%s)

kill $sampler 2>/dev/null || true; trap - EXIT
gcoff_end=$($D exec $name sh -c 'wc -c < /tmp/gc.log' | tr -d ' \r')
rows_after=$($D exec gcf3-pg psql -tAq -U orderuser -d orderdb -c 'select count(*) from orders;' | tr -d ' \r')

$D cp $name:/tmp/gc.log "$OUT/$tag.gc.full.log"
tail -c +$((gcoff+1)) "$OUT/$tag.gc.full.log" | head -c $((gcoff_end-gcoff)) > "$OUT/$tag.gc.log"
rm -f "$OUT/$tag.gc.full.log"

cat > "$OUT/$tag.meta.json" <<META
{"ver":"$ver","round":$round,"cid":"$cid","k6_start_epoch":$k6start,"k6_end_epoch":$k6end,
 "k6_exit":$k6exit,"gc_byte_offset":[$gcoff,$gcoff_end],
 "orders_rows_before":$rows_before,"orders_rows_after":$rows_after,
 "rates":{"baseline":48,"peak":240,"recovery":48},
 "pre_allocated_vus":1500,"max_vus":3000,
 "cpu_limit":"--cpus=1 (cpu.max 100000 100000)","mem_limit":"2g"}
META
gzip -f "$OUT/$tag.k6.csv"
echo "[done] $tag k6_exit=$k6exit gc_bytes=$((gcoff_end-gcoff)) rows=$rows_before->$rows_after"
