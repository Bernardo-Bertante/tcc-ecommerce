#!/usr/bin/env bash
# Uso: run_one.sh <qj|qn> <rate_iter_s> <tag>
# Exploratório (não é resultado formal): Quarkus JVM vs Native, mesmas imagens do F1 (ECR 20260616-160138),
# container 1 CPU dedicada (cpuset, sem cota) + 2 GB = ergonomia da task Fargate 1024/2048. GC log ligado.
set -euo pipefail
ver=$1; rate=$2; tag=$3
RAMP=${RAMP:-60s}; HOLD=${HOLD:-540s}
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
OUT="$HERE/results"; mkdir -p "$OUT"
name=gcexp-app
common=(--network gcexp --cpuset-cpus=3 -m 2g --memory-swap 2g
  -e SERVER_PORT=8081 -e QUARKUS_DATASOURCE_USERNAME=orderuser -e QUARKUS_DATASOURCE_PASSWORD=orderpass
  -e QUARKUS_DATASOURCE_REACTIVE_URL=postgresql://gcexp-pg:5432/orderdb
  -e QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://gcexp-pg:5432/orderdb
  -e QUARKUS_DATASOURCE_REACTIVE_MAX_SIZE=40 -p 127.0.0.1:9300:8081)

$D rm -f $name >/dev/null 2>&1 || true
$D exec gcexp-pg psql -q -U orderuser -d orderdb -c "TRUNCATE TABLE order_status_history, order_items, orders;" >/dev/null 2>&1 || true

if [[ $ver == qn ]]; then
  cid=$($D run -d --name $name "${common[@]}" gcexp-native -XX:+PrintGC -XX:+VerboseGC -XX:+PrintGCTimes)
else
  cid=$($D run -d --name $name "${common[@]}" \
    -e JAVA_OPTS_APPEND="-Dquarkus.http.host=0.0.0.0 -Xlog:gc*,safepoint:file=/tmp/gc.log:time,uptime,level,tags" gcexp-jvm)
fi
for i in $(seq 90); do curl -sf http://127.0.0.1:9300/q/health/ready >/dev/null && break; sleep 1; done

cg=/sys/fs/cgroup/system.slice/docker-$cid.scope
( while true; do
    echo "$(date +%s.%N) $(awk '/usage_usec/{print $2}' $cg/cpu.stat) $(cat $cg/memory.current)"; sleep 5
  done ) > "$OUT/$tag.cpu.tsv" 2>/dev/null &
sampler=$!

k6start=$(date +%s)
echo "ver=$ver rate=$rate ramp=$RAMP hold=$HOLD k6_start_epoch=$k6start cid=$cid" > "$OUT/$tag.meta"
vus=$(( rate > 100 ? 800 : 200 )); pre=$(( rate > 100 ? 400 : 80 ))
taskset -c 12-15 k6 run -q --no-summary -e BASE_URL=http://127.0.0.1:9300 -e F1_RATE=$rate \
  -e F1_RAMP_UP=$RAMP -e F1_DURATION=$HOLD -e F1_RAMP_DOWN=5s -e MAX_VUS=$vus -e PRE_ALLOCATED_VUS=$pre \
  --out csv="$OUT/$tag.k6.csv" "$REPO/benchmark/scenarios/f1_low_load.js" > "$OUT/$tag.k6.log" 2>&1 || echo "k6_exit=$?" >> "$OUT/$tag.meta"
echo "k6_end_epoch=$(date +%s)" >> "$OUT/$tag.meta"

kill $sampler 2>/dev/null || true
if [[ $ver == qj ]]; then $D cp $name:/tmp/gc.log "$OUT/$tag.gc.log"; fi
$D logs $name > "$OUT/$tag.container.log" 2>&1
$D rm -f $name >/dev/null
gzip -f "$OUT/$tag.k6.csv"
echo "done $tag"
