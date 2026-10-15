#!/usr/bin/env bash
# Uso: run_one.sh <sb|qj> <tag>
#
# Exploratório (NÃO é resultado formal do desenho experimental): perfil de CPU de
# Spring Boot (WebFlux + Spring Data R2DBC) vs Quarkus JVM (RESTEasy Reactive +
# Hibernate Reactive/Panache) sob carga F1 (48 req/s, mix oficial 51/20/15/12/2).
#
# Imagens: as MESMAS do F1/F2/F3 oficiais (tag 20260616-160138), derivadas apenas
# para embutir o async-profiler 4.5 em /opt/async-profiler. Nenhum código recompilado.
# Em ambas o java é PID 1 e o entrypoint da UBI aplica as mesmas flags de ergonomia.
#
# Por repetição saem DOIS perfis da mesma execução, cada um em .jfr (bruto),
# .collapsed (quantificação) e .html (flame graph):
#   - cpu  : evento ctimer, CPU-time por thread
#   - wall : wall-clock, todas as threads (captura espera, não só CPU)
set -euo pipefail

ver=$1; tag=$2
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
OUT="${OUT_DIR:-$HERE/results}"; mkdir -p "$OUT"
JFRCONV="$HERE/build/async-profiler-4.5-linux-x64/bin/jfrconv"

RATE=${RATE:-48}
RAMP=${RAMP:-60s}
HOLD=${HOLD:-960s}          # 16 min de sustentação
WARMUP=${WARMUP:-60}        # s de carga de aquecimento antes de tudo (JIT)
CPU_AT=${CPU_AT:-120}       # s após início do k6 oficial
CPU_DUR=${CPU_DUR:-360}
WALL_AT=${WALL_AT:-520}
WALL_DUR=${WALL_DUR:-360}

name=pilhaexp-app
port=9400
APP_CPUSET=${APP_CPUSET:-0-7}
# Quota de CPU. Vazio = comportamento original (8 nucleos, sem quota).
# CPU_QUOTA=1 => --cpus=1 = 1024 unidades = task Fargate oficial (1024/2048).
CPU_QUOTA=${CPU_QUOTA:-}
K6_CPUS=${K6_CPUS:-12-15}

# DebugNonSafepoints melhora a precisão do stack walking; não altera o caminho quente.
PROF_FLAGS="-XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints"
HEAP="-Xms512m -Xmx2g -XX:MaxMetaspaceSize=256m"

common=(--network pilhaexp --cpuset-cpus="$APP_CPUSET" -m 3g --memory-swap 3g
  -e SERVER_PORT=8081 -p 127.0.0.1:$port:8081)
[[ -n $CPU_QUOTA ]] && common+=(--cpus="$CPU_QUOTA")

$D rm -f $name >/dev/null 2>&1 || true
$D exec pilhaexp-pg psql -q -U orderuser -d orderdb \
  -c "TRUNCATE TABLE order_status_history, order_items, orders;" >/dev/null 2>&1 || true

if [[ $ver == sb ]]; then
  health=/actuator/health/readiness
  cid=$($D run -d --name $name "${common[@]}" \
    -e SPRING_R2DBC_URL=r2dbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e SPRING_R2DBC_USERNAME=orderuser -e SPRING_R2DBC_PASSWORD=orderpass \
    -e SPRING_FLYWAY_URL=jdbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e SPRING_FLYWAY_USER=orderuser -e SPRING_FLYWAY_PASSWORD=orderpass \
    -e JAVA_OPTS_APPEND="$HEAP $PROF_FLAGS" pilhaexp-sb:prof)
else
  health=/q/health/ready
  cid=$($D run -d --name $name "${common[@]}" \
    -e QUARKUS_DATASOURCE_USERNAME=orderuser -e QUARKUS_DATASOURCE_PASSWORD=orderpass \
    -e QUARKUS_DATASOURCE_REACTIVE_URL=postgresql://pilhaexp-pg:5432/orderdb \
    -e QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://pilhaexp-pg:5432/orderdb \
    -e JAVA_OPTS_APPEND="-Dquarkus.http.host=0.0.0.0 $HEAP $PROF_FLAGS" pilhaexp-qj:prof)
fi

echo "[$tag] container ${cid:0:12} ($ver), aguardando readiness..."
for i in $(seq 120); do
  curl -sf "http://127.0.0.1:$port$health" >/dev/null 2>&1 && { echo "[$tag] ready em ${i}s"; break; }
  sleep 1
done
curl -sf "http://127.0.0.1:$port$health" >/dev/null || {
  echo "[$tag] ERRO: app nao ficou ready"; $D logs $name | tail -40; exit 1; }

jpid=1
asprof() { $D exec -u 185 $name /opt/async-profiler/bin/asprof "$@"; }

# TAREFA 1 (reconfirmacao 1 vCPU): quantos processadores a JVM enxerga DENTRO do
# container. Aborta antes de qualquer carga se nao bater com a quota pedida.
# Sem `grep -m1`: a saida precisa ser consumida ate o fim, senao o java leva
# SIGPIPE e o `set -o pipefail` transforma isso em falha da deteccao.
apc=$($D exec $name java -Xlog:os+container=trace -version 2>&1 \
        | grep "active_processor_count:" | tail -1 | sed "s/.*: //" | tr -d ' \r') || apc=""
echo "[$tag] JVM active_processor_count=${apc:-desconhecido} (cpu_quota=${CPU_QUOTA:-nenhuma})"
if [[ -n $CPU_QUOTA && "$apc" != "$CPU_QUOTA" ]]; then
  echo "[$tag] ERRO: esperava $CPU_QUOTA processador(es), JVM detectou '${apc:-?}'. Abortando."
  $D logs $name > "$OUT/$tag.container.log" 2>&1; $D rm -f $name >/dev/null; exit 1
fi

# --- TAREFA 1: aquecer e PROVAR que o profiler coleta amostras antes da carga ---
echo "[$tag] warm-up ${WARMUP}s + verificacao do profiler..."
taskset -c "$K6_CPUS" k6 run -q --no-summary --no-usage-report \
  -e BASE_URL="http://127.0.0.1:$port" -e F1_RATE=10 \
  -e F1_RAMP_UP=5s -e F1_DURATION=${WARMUP}s -e F1_RAMP_DOWN=5s \
  -e MAX_VUS=50 -e PRE_ALLOCATED_VUS=20 \
  "$REPO/benchmark/scenarios/f1_low_load.js" > "$OUT/$tag.warmup.k6.log" 2>&1 &
k6warm=$!
sleep 15
asprof -e ctimer -d 10 -o jfr -f /tmp/smoke.jfr "$jpid" > "$OUT/$tag.smoke.log" 2>&1 || true
$D cp "$name:/tmp/smoke.jfr" "$OUT/$tag.smoke.jfr" 2>/dev/null || true
"$JFRCONV" --cpu -o collapsed "$OUT/$tag.smoke.jfr" "$OUT/$tag.smoke.collapsed" >/dev/null 2>&1 || true
smoke_stacks=$(wc -l < "$OUT/$tag.smoke.collapsed" 2>/dev/null || echo 0)
smoke_samples=$(awk '{s+=$NF} END{print s+0}' "$OUT/$tag.smoke.collapsed" 2>/dev/null || echo 0)
echo "[$tag] SMOKE profiler: ${smoke_stacks} stacks distintos, ${smoke_samples} amostras em 10s"
wait $k6warm || true
if [[ "${smoke_samples:-0}" -lt 50 ]]; then
  echo "[$tag] ERRO: profiler nao coletou amostras suficientes ($smoke_samples). Abortando."
  $D logs $name > "$OUT/$tag.container.log" 2>&1; $D rm -f $name >/dev/null; exit 1
fi

# --- amostrador de CPU/memória do cgroup (a cada 5s) ---
cg=/sys/fs/cgroup/system.slice/docker-$cid.scope
( while true; do
    echo "$(date +%s.%N) $(awk '/usage_usec/{print $2}' $cg/cpu.stat 2>/dev/null) $(cat $cg/memory.current 2>/dev/null)"
    sleep 5
  done ) > "$OUT/$tag.cpu.tsv" 2>/dev/null &
sampler=$!

# --- carga oficial + janelas de profiling ---
k6start=$(date +%s)
cat > "$OUT/$tag.meta" <<META
ver=$ver rate=$RATE ramp=$RAMP hold=$HOLD
app_cpuset=$APP_CPUSET cpu_quota=${CPU_QUOTA:-nenhuma} k6_cpus=$K6_CPUS heap=$HEAP
active_processor_count=$apc
image=$($D inspect --format '{{index .Config.Image}}' $name)
java_pid=$jpid cid=$cid
smoke_stacks=$smoke_stacks smoke_samples=$smoke_samples
cpu_window=t+${CPU_AT}s/${CPU_DUR}s wall_window=t+${WALL_AT}s/${WALL_DUR}s
k6_start_epoch=$k6start
META

echo "[$tag] carga oficial: rate=$RATE ramp=$RAMP hold=$HOLD"
taskset -c "$K6_CPUS" k6 run -q --no-summary --no-usage-report \
  -e BASE_URL="http://127.0.0.1:$port" -e F1_RATE=$RATE \
  -e F1_RAMP_UP=$RAMP -e F1_DURATION=$HOLD -e F1_RAMP_DOWN=20s \
  -e MAX_VUS=200 -e PRE_ALLOCATED_VUS=80 \
  --summary-export "$OUT/$tag.k6.summary.json" \
  --out csv="$OUT/$tag.k6.csv" \
  "$REPO/benchmark/scenarios/f1_low_load.js" > "$OUT/$tag.k6.log" 2>&1 &
k6pid=$!

profile_window() {   # nome evento delay duracao flag_conv
  local nome=$1 ev=$2 at=$3 dur=$4 conv=$5
  local now target
  now=$(( $(date +%s) - k6start )); target=$(( at - now ))
  [[ $target -gt 0 ]] && sleep $target
  echo "[$tag] profiling $nome ($ev) por ${dur}s, inicio em t+$(( $(date +%s) - k6start ))s"
  asprof -e "$ev" -d "$dur" -o jfr -f "/tmp/$nome.jfr" "$jpid" >> "$OUT/$tag.prof.log" 2>&1 || true
  $D cp "$name:/tmp/$nome.jfr" "$OUT/$tag.$nome.jfr" 2>/dev/null || true
  "$JFRCONV" "$conv" -o collapsed "$OUT/$tag.$nome.jfr" "$OUT/$tag.$nome.collapsed" >/dev/null 2>&1 || true
  "$JFRCONV" "$conv" -o html      "$OUT/$tag.$nome.jfr" "$OUT/$tag.$nome.html"      >/dev/null 2>&1 || true
  local n; n=$(awk '{s+=$NF} END{print s+0}' "$OUT/$tag.$nome.collapsed" 2>/dev/null || echo 0)
  echo "[$tag]   -> $nome: $n amostras"
}

profile_window cpu  ctimer "$CPU_AT"  "$CPU_DUR"  --cpu
profile_window wall wall   "$WALL_AT" "$WALL_DUR" --wall

wait $k6pid || echo "k6_exit=$?" >> "$OUT/$tag.meta"
echo "k6_end_epoch=$(date +%s)" >> "$OUT/$tag.meta"
kill $sampler 2>/dev/null || true

$D logs $name > "$OUT/$tag.container.log" 2>&1
$D rm -f $name >/dev/null
gzip -f "$OUT/$tag.k6.csv" 2>/dev/null || true
echo "[$tag] done"
