#!/usr/bin/env bash
# Uso: run_one.sh <sb|qj|qja|sbu> <free|lim> <tag> [duration]   (RESULTS_DIR opcional; imagem = cpuexp-proc-<ver>)
# Sobe um ambiente Lambda novo (RIE) para a versão, faz 1 invocação fria, roda carga sustentada e salva CSV do k6.
set -euo pipefail
ver=$1; cond=$2; tag=$3; duration=${4:-300s}
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="${RESULTS_DIR:-$HERE/results}"; mkdir -p "$OUT"
name=cpuexp-fn
cpuflag=""; [[ $cond == lim ]] && cpuflag="--cpus=0.29"

$D rm -f $name >/dev/null 2>&1 || true
$D run -d --name $name --network cpuexp --cpuset-cpus=2,4 $cpuflag -m 512m --memory-swap 512m \
  -e AWS_LAMBDA_FUNCTION_MEMORY_SIZE=512 \
  -e JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2 \
  -e AWS_ACCESS_KEY_ID=local -e AWS_SECRET_ACCESS_KEY=local \
  -e AWS_REGION=us-east-1 -e DYNAMODB_ENDPOINT=http://cpuexp-ddb:8000 \
  -e PROCESSED_ORDERS_TABLE=processed_orders -e STOCK_RESERVATIONS_TABLE=stock_reservations \
  -e SPRING_CLOUD_FUNCTION_DEFINITION=processOrder \
  -p 127.0.0.1:9100:8080 cpuexp-proc-$ver >/dev/null
sleep 2

base=http://127.0.0.1:9100
payload='{"orderId":"00000000-0000-4000-8000-000000000001","customerId":"00000000-0000-4000-8000-000000000002","items":[{"productId":"00000000-0000-4000-8000-000000000003","productName":"Mouse","quantity":1,"unitPrice":10.00}],"shippingAddress":{"zipCode":"37200-000","state":"MG","city":"Lavras"},"totalAmount":10.00}'
cold=$(curl -s -o "$OUT/$tag.cold.json" -w '%{time_total}' --max-time 180 -XPOST "$base/2015-03-31/functions/function/invocations" -d "$payload")
echo "cold_s=$cold" > "$OUT/$tag.meta"
$D exec $name cat /sys/fs/cgroup/cpu.stat > "$OUT/$tag.cpustat.before" 2>/dev/null || true
$D exec $name cat /proc/net/snmp > "$OUT/$tag.snmp.before" 2>/dev/null || true
# Snapshot de sockets no meio da carga (TIME_WAIT para :8000 indica conexões não reusadas).
mid=$(( ${duration%s} / 2 ))
(sleep $mid; $D exec $name sh -c "cat /proc/net/tcp /proc/net/tcp6" > "$OUT/$tag.tcp.mid" 2>/dev/null) &

taskset -c 6,7 k6 run -q --no-summary -e BASE_URL=$base -e LAMBDA_LOCAL_RIE=true -e DURATION=$duration \
  --out csv="$OUT/$tag.k6.csv" "$HERE/proc_load.js" > "$OUT/$tag.k6.log" 2>&1 || echo "k6_exit=$?" >> "$OUT/$tag.meta"

$D exec $name cat /sys/fs/cgroup/cpu.stat > "$OUT/$tag.cpustat.after" 2>/dev/null || true
$D exec $name cat /proc/net/snmp > "$OUT/$tag.snmp.after" 2>/dev/null || true
wait
$D logs $name > "$OUT/$tag.container.log" 2>&1
$D rm -f $name >/dev/null
echo "done $tag cold=$cold"
