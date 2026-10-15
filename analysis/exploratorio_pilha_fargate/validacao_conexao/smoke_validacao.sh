#!/usr/bin/env bash
# Smoke ANTES da coleta: confirma que SPRING_R2DBC_POOL_VALIDATION_QUERY= (vazia) desliga
# de fato o "SELECT 1" do pool R2DBC nesta imagem local, com controle positivo.
#
# Liga log_statement=all no Postgres local (ALTER SYSTEM + reload, sem restart), roda o SB
# 60 s sob carga leve em cada condicao (on = controle positivo, off = condicao testada),
# conta "SELECT 1" no log do Postgres em cada janela e depois RESETA log_statement.
# Nenhuma coleta de perfil acontece aqui; as rodadas oficiais rodam com log_statement=none.
set -euo pipefail
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
OUT="$HERE/results"; mkdir -p "$OUT"
name=pilhaexp-smokeval; port=9401
psqlc() { $D exec pilhaexp-pg psql -q -U orderuser -d orderdb -Atc "$1"; }

cleanup() {
  $D rm -f $name >/dev/null 2>&1 || true
  psqlc "ALTER SYSTEM RESET log_statement;" >/dev/null
  psqlc "SELECT pg_reload_conf();" >/dev/null
  echo "log_statement apos reset: $(psqlc 'SHOW log_statement;')"
}
trap cleanup EXIT

psqlc "ALTER SYSTEM SET log_statement = 'all';" >/dev/null
psqlc "SELECT pg_reload_conf();" >/dev/null
sleep 2
echo "log_statement durante o smoke: $(psqlc 'SHOW log_statement;')"

for cond in on off; do
  extra=(); [[ $cond == off ]] && extra=(-e SPRING_R2DBC_POOL_VALIDATION_QUERY=)
  $D rm -f $name >/dev/null 2>&1 || true
  psqlc "TRUNCATE TABLE order_status_history, order_items, orders;" >/dev/null
  $D run -d --name $name --network pilhaexp --cpuset-cpus=0-7 --cpus=1 -m 3g --memory-swap 3g \
    -e SERVER_PORT=8081 -p 127.0.0.1:$port:8081 \
    -e SPRING_R2DBC_URL=r2dbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e SPRING_R2DBC_USERNAME=orderuser -e SPRING_R2DBC_PASSWORD=orderpass \
    -e SPRING_FLYWAY_URL=jdbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e SPRING_FLYWAY_USER=orderuser -e SPRING_FLYWAY_PASSWORD=orderpass \
    "${extra[@]}" \
    -e JAVA_OPTS_APPEND="-Xms512m -Xmx2g -XX:MaxMetaspaceSize=256m" pilhaexp-sb:prof >/dev/null
  for i in $(seq 120); do
    curl -sf "http://127.0.0.1:$port/actuator/health/readiness" >/dev/null 2>&1 && break; sleep 1
  done
  since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  taskset -c 12-15 k6 run -q --no-summary --no-usage-report \
    -e BASE_URL="http://127.0.0.1:$port" -e F1_RATE=10 \
    -e F1_RAMP_UP=5s -e F1_DURATION=60s -e F1_RAMP_DOWN=5s \
    -e MAX_VUS=50 -e PRE_ALLOCATED_VUS=20 \
    "$REPO/benchmark/scenarios/f1_low_load.js" > "$OUT/smoke-val-$cond.k6.log" 2>&1 || true
  $D logs --since "$since" pilhaexp-pg > "$OUT/smoke-val-$cond.pg.log" 2>&1
  n_sel1=$(grep -cE '(statement|execute [^:]*): SELECT 1[[:space:]]*$' "$OUT/smoke-val-$cond.pg.log" || true)
  n_all=$(grep -cE 'LOG:  (statement|execute)' "$OUT/smoke-val-$cond.pg.log" || true)
  echo "validation=$cond  SELECT 1 = $n_sel1   (total de statements logados: $n_all)" \
    | tee -a "$OUT/smoke-val.resumo.txt"
  $D rm -f $name >/dev/null
done
