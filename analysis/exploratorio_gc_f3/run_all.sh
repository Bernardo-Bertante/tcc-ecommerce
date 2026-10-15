#!/usr/bin/env bash
# Uso: run_all.sh <sb|qj> <n_rodadas>
# Sobe o app UMA vez (igual ao oficial: a task nao era reiniciada entre rodadas),
# reseta o schema antes, e roda N repeticoes com intervalo de 75s (intervalo oficial: 1,1-1,5 min).
set -euo pipefail
ver=$1; n=$2
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/results"; mkdir -p "$OUT"
GAP=${GAP:-75}
name=gcf3-app
# filecount=0 desliga a rotacao em 20 MB (default filesize=20M) que quebrou o
# fatiamento por offset na 1a tentativa; o fatiamento agora e por timestamp de todo modo.
GCLOG='-Xlog:gc*,safepoint:file=/tmp/gc.log:time,uptime,level,tags:filecount=0'

echo "=== [$ver] reset do schema"
$D exec gcf3-pg psql -q -U orderuser -d orderdb -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' >/dev/null

$D rm -f $name >/dev/null 2>&1 || true
common=(--network gcf3 --cpus=1 -m 2g --memory-swap 2g -e SERVER_PORT=8081 -p 127.0.0.1:9301:8081)

echo "=== [$ver] subindo app (--cpus=1, 2g)"
if [[ $ver == sb ]]; then
  cid=$($D run -d --name $name "${common[@]}" \
    -e SPRING_R2DBC_POOL_MAX_SIZE=40 -e SPRING_R2DBC_POOL_INITIAL_SIZE=15 \
    -e SPRING_R2DBC_URL='r2dbc:postgresql://gcf3-pg:5432/orderdb' \
    -e SPRING_R2DBC_USERNAME=orderuser -e SPRING_R2DBC_PASSWORD=<SENHA_RDS> \
    -e SPRING_FLYWAY_URL='jdbc:postgresql://gcf3-pg:5432/orderdb' \
    -e SPRING_FLYWAY_USER=orderuser -e SPRING_FLYWAY_PASSWORD=<SENHA_RDS> \
    -e JAVA_OPTS_APPEND="$GCLOG" gcf3-sb:official)
  health=http://127.0.0.1:9301/actuator/health
else
  cid=$($D run -d --name $name "${common[@]}" \
    -e QUARKUS_DATASOURCE_REACTIVE_MAX_SIZE=40 \
    -e QUARKUS_DATASOURCE_REACTIVE_URL='postgresql://gcf3-pg:5432/orderdb' \
    -e QUARKUS_DATASOURCE_JDBC_URL='jdbc:postgresql://gcf3-pg:5432/orderdb' \
    -e QUARKUS_DATASOURCE_USERNAME=orderuser -e QUARKUS_DATASOURCE_PASSWORD=<SENHA_RDS> \
    -e JAVA_OPTS_APPEND="-Dquarkus.http.host=0.0.0.0 $GCLOG" gcf3-qj:official)
  health=http://127.0.0.1:9301/q/health/ready
fi

for i in $(seq 120); do curl -sf "$health" >/dev/null 2>&1 && { echo "    pronto em ${i}s"; break; }; sleep 1; done
curl -sf "$health" >/dev/null || { echo "!! app nao ficou pronto"; $D logs $name | tail -30; exit 1; }

# registra a ergonomia vista pela JVM -- aborta se nao for 1 CPU
$D exec $name sh -c 'grep -m1 "CPUs:" /tmp/gc.log' | tee "$OUT/$ver.ergonomia.txt"
if ! grep -q '1 available' "$OUT/$ver.ergonomia.txt"; then
  echo "!! ABORTADO: JVM nao detectou 1 CPU disponivel"; $D rm -f $name; exit 1
fi
$D exec $name sh -c 'cat /proc/1/cmdline | tr "\0" "\n"' > "$OUT/$ver.cmdline.txt"

for r in $(seq 1 "$n"); do
  echo "=== [$ver] rodada $r/$n  $(date +%H:%M:%S)"
  # Reset do dataset antes de cada rodada, com o app EM PE (JVM segue aquecida, como no
  # oficial). Sem isso o dataset cresce monotonicamente e o Postgres local satura: na 1a
  # tentativa a r3 colapsou (p95 18,3 s) com o PG em 1,999/2,0 vCPU, enquanto o RDS oficial
  # ficava em 58-62% no pico. O gargalo era o banco, nao o GC do app.
  $D exec gcf3-pg psql -q -U orderuser -d orderdb \
    -c "TRUNCATE TABLE order_status_history, order_items, orders RESTART IDENTITY;" >/dev/null
  "$HERE/run_round.sh" "$ver" "$r" "$cid"
  if (( r < n )); then echo "    descanso ${GAP}s"; sleep "$GAP"; fi
done

$D logs $name > "$OUT/$ver.container.log" 2>&1
$D rm -f $name >/dev/null
echo "=== [$ver] concluido $(date +%H:%M:%S)"
