#!/usr/bin/env bash
# TAREFA 5 — "quantidade de máquina" de cada versão, de forma simétrica.
#
# Spring Boot: beans singleton instanciados no startup (log DEBUG do
#   DefaultListableBeanFactory) + classes de proxy dinâmico carregadas em runtime.
# Quarkus: classes geradas em BUILD time (generated-bytecode.jar / transformed-bytecode.jar,
#   contadas estaticamente) + classes carregadas em runtime, pelo mesmo -Xlog:class+load.
#
# Roda com carga leve (60s) para que os proxies do caminho quente sejam de fato carregados.
set -euo pipefail
ver=$1
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
OUT="$HERE/results"; mkdir -p "$OUT"
name=pilhaexp-count; port=9402
HEAP="-Xms512m -Xmx2g -XX:MaxMetaspaceSize=256m"
CL="-Xlog:class+load=info:file=/tmp/cl.log"

$D rm -f $name >/dev/null 2>&1 || true
$D exec pilhaexp-pg psql -q -U orderuser -d orderdb \
  -c "TRUNCATE TABLE order_status_history, order_items, orders;" >/dev/null 2>&1 || true

if [[ $ver == sb ]]; then
  health=/actuator/health/readiness
  $D run -d --name $name --network pilhaexp --cpuset-cpus=0-7 -m 3g --memory-swap 3g \
    -e SERVER_PORT=8081 -p 127.0.0.1:$port:8081 \
    -e SPRING_R2DBC_URL=r2dbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e SPRING_R2DBC_USERNAME=orderuser -e SPRING_R2DBC_PASSWORD=orderpass \
    -e SPRING_FLYWAY_URL=jdbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e SPRING_FLYWAY_USER=orderuser -e SPRING_FLYWAY_PASSWORD=orderpass \
    -e LOGGING_LEVEL_ORG_SPRINGFRAMEWORK_BEANS_FACTORY_SUPPORT=DEBUG \
    -e JAVA_OPTS_APPEND="$HEAP $CL" pilhaexp-sb:prof >/dev/null
else
  health=/q/health/ready
  $D run -d --name $name --network pilhaexp --cpuset-cpus=0-7 -m 3g --memory-swap 3g \
    -e SERVER_PORT=8081 -p 127.0.0.1:$port:8081 \
    -e QUARKUS_DATASOURCE_USERNAME=orderuser -e QUARKUS_DATASOURCE_PASSWORD=orderpass \
    -e QUARKUS_DATASOURCE_REACTIVE_URL=postgresql://pilhaexp-pg:5432/orderdb \
    -e QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e JAVA_OPTS_APPEND="-Dquarkus.http.host=0.0.0.0 $HEAP $CL" pilhaexp-qj:prof >/dev/null
fi

for i in $(seq 120); do curl -sf "http://127.0.0.1:$port$health" >/dev/null 2>&1 && break; sleep 1; done
curl -sf "http://127.0.0.1:$port$health" >/dev/null || { echo "ERRO count $ver"; $D logs $name | tail -20; exit 1; }

taskset -c 12-15 k6 run -q --no-summary --no-usage-report \
  -e BASE_URL="http://127.0.0.1:$port" -e F1_RATE=10 \
  -e F1_RAMP_UP=5s -e F1_DURATION=60s -e F1_RAMP_DOWN=5s \
  -e MAX_VUS=50 -e PRE_ALLOCATED_VUS=20 \
  "$REPO/benchmark/scenarios/f1_low_load.js" > "$OUT/count-$ver.k6.log" 2>&1 || true

$D cp "$name:/tmp/cl.log" "$OUT/count-$ver.classload.log"
$D logs $name > "$OUT/count-$ver.app.log" 2>&1
$D rm -f $name >/dev/null
gzip -f "$OUT/count-$ver.classload.log"
echo "count-$ver ok"
