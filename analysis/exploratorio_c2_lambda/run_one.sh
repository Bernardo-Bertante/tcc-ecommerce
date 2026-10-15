#!/usr/bin/env bash
# Uso: run_one.sh <sb|qj> <c1|c2> <tag> [duration]   (RESULTS_DIR opcional)
# Igual ao run_one.sh de ../exploratorio_cpu_lambda (mesma topologia/carga), mudando só o nível máximo do JIT.
#  c1: JAVA_TOOL_OPTIONS igual ao teste anterior -> bootstrap injeta -XX:+TieredCompilation -XX:TieredStopAtLevel=1 (default Lambda java21)
#  c2: +TieredCompilation em JAVA_TOOL_OPTIONS faz o bootstrap NÃO injetar StopAtLevel=1 (ver flagcheck/);
#      -XX:TieredStopAtLevel=4 só em JAVA_TOOL_OPTIONS é sobrescrito pela linha de comando e ignorado.
set -euo pipefail
ver=$1; cond=$2; tag=$3; duration=${4:-480s}
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="${RESULTS_DIR:-$HERE/results}"; mkdir -p "$OUT"
name=c2exp-fn
case $cond in
  c1) jto="-XX:ActiveProcessorCount=2" ;;
  c2) jto="-XX:ActiveProcessorCount=2 -XX:+UseSerialGC -XX:+TieredCompilation -XX:TieredStopAtLevel=4" ;;
  *) echo "cond inválida: $cond"; exit 2 ;;
esac

# Tabelas novas a cada execução (DynamoDB Local em memória; evita crescimento ao longo da sessão).
ddb_ip=$($D inspect cpuexp-ddb --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
A="env AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_REGION=us-east-1 aws --endpoint-url http://$ddb_ip:8000 dynamodb"
for t in processed_orders stock_reservations; do $A delete-table --table-name $t >/dev/null 2>&1 || true; done
$A create-table --table-name processed_orders --billing-mode PAY_PER_REQUEST --attribute-definitions AttributeName=orderId,AttributeType=S --key-schema AttributeName=orderId,KeyType=HASH >/dev/null
$A create-table --table-name stock_reservations --billing-mode PAY_PER_REQUEST --attribute-definitions AttributeName=orderId,AttributeType=S AttributeName=productId,AttributeType=S --key-schema AttributeName=orderId,KeyType=HASH AttributeName=productId,KeyType=RANGE >/dev/null

$D rm -f $name >/dev/null 2>&1 || true
$D run -d --name $name --network cpuexp --cpuset-cpus=2,4 -m 512m --memory-swap 512m \
  -e AWS_LAMBDA_FUNCTION_MEMORY_SIZE=512 \
  -e "JAVA_TOOL_OPTIONS=$jto" \
  -e AWS_ACCESS_KEY_ID=local -e AWS_SECRET_ACCESS_KEY=local \
  -e AWS_REGION=us-east-1 -e DYNAMODB_ENDPOINT=http://cpuexp-ddb:8000 \
  -e PROCESSED_ORDERS_TABLE=processed_orders -e STOCK_RESERVATIONS_TABLE=stock_reservations \
  -e SPRING_CLOUD_FUNCTION_DEFINITION=processOrder \
  -p 127.0.0.1:9100:8080 c2exp-proc-$ver >/dev/null
sleep 2

base=http://127.0.0.1:9100
payload='{"orderId":"00000000-0000-4000-8000-000000000001","customerId":"00000000-0000-4000-8000-000000000002","items":[{"productId":"00000000-0000-4000-8000-000000000003","productName":"Mouse","quantity":1,"unitPrice":10.00}],"shippingAddress":{"zipCode":"37200-000","state":"MG","city":"Lavras"},"totalAmount":10.00}'
cold=$(curl -s -o "$OUT/$tag.cold.json" -w '%{time_total}' --max-time 180 -XPOST "$base/2015-03-31/functions/function/invocations" -d "$payload")
echo "cold_s=$cold" > "$OUT/$tag.meta"
echo "jto=$jto" >> "$OUT/$tag.meta"
pid=$($D exec $name sh -c 'for p in /proc/[0-9]*; do grep -q "^/var/lang/bin/java" $p/cmdline 2>/dev/null && basename $p; done; true' | head -1)
for i in 1 2 3 4 5; do  # o primeiro attach logo após o init às vezes falha
  $D exec $name /var/lang/bin/jcmd $pid VM.flags -all > "$OUT/$tag.flags.all" 2>&1 && break; sleep 1
done
grep -E '\b(TieredStopAtLevel|TieredCompilation|UseSerialGC|MaxHeapSize|Tier4InvocationThreshold|ActiveProcessorCount)\b' "$OUT/$tag.flags.all" > "$OUT/$tag.flags" || true
$D exec $name cat /sys/fs/cgroup/cpu.stat > "$OUT/$tag.cpustat.before" 2>/dev/null || true

taskset -c 6,7 k6 run -q --no-summary -e BASE_URL=$base -e LAMBDA_LOCAL_RIE=true -e DURATION=$duration \
  --out csv="$OUT/$tag.k6.csv" "$HERE/../exploratorio_cpu_lambda/proc_load.js" > "$OUT/$tag.k6.log" 2>&1 || echo "k6_exit=$?" >> "$OUT/$tag.meta"

$D exec $name cat /sys/fs/cgroup/cpu.stat > "$OUT/$tag.cpustat.after" 2>/dev/null || true
$D exec $name /var/lang/bin/jcmd $pid Compiler.codelist > "$OUT/$tag.codelist" 2>&1 || true
$D exec $name /var/lang/bin/jcmd $pid PerfCounter.print 2>/dev/null | grep -E '^(sun|java)\.ci\.' > "$OUT/$tag.ci" || true
$D logs $name > "$OUT/$tag.container.log" 2>&1
$D rm -f $name >/dev/null
echo "done $tag cold=$cold"
