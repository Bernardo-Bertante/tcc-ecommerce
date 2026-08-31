#!/usr/bin/env bash
# Orquestrador mestre da recoleta completa do cenario L2 (TCC). Feito para
# rodar sozinho via nohup, do inicio ao fim, sem supervisao manual:
#
#   nohup scripts/l2_recoleta/run_l2_recoleta.sh > /dev/null 2>&1 &
#   disown
#
# (o script ja redireciona seu proprio progresso para analysis/l2_recoleta_execucao.log
# e analysis/l2_recoleta_status.txt via common.sh -- o nohup so garante que o
# processo sobrevive ao fechamento do terminal.)
#
# Fases: (1) reconstroi a infraestrutura AWS do zero -- stack Lambda+DynamoDB
# com retencao de log de 90 dias, runner EC2 para o k6 -- porque tudo o que
# existia em julho/2026 foi destruido (nao e so log expirado, ver
# investigacao anterior); (2) para cada uma das 3 versoes, 5 rodadas de L2,
# SEM redeploy entre rodadas (fiel ao protocolo Lambda documentado em
# 03-methodology.md -- "funcao fresca entre rodadas" e exclusivo do Fargate),
# com um gap de ~48min entre rodadas da mesma versao (replica o gap natural
# observado em julho, que era efeito colateral do rodizio com L3/outras
# versoes); apos cada rodada, analisa distribuicao de invocacoes por
# log-stream via CloudWatch Logs Insights; (3) troca os dados antigos de L2
# pelos novos e reroda a analise estatistica oficial; (4) desliga o runner
# EC2 (mantem a stack, de proposito -- ver teardown_infra.sh).
#
# Resumivel: se for interrompido e relancado, pula rodadas ja concluidas
# (checkpoint por arquivo em staging + linha no CSV) e reaproveita a infra
# ja provisionada (state/infra.env).
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/provision_infra.sh"

ROUND_GAP_SECONDS=$(( 48 * 60 ))
K6_MAX_WAIT_SECONDS=1200   # 20min -- cenario real dura ~12min, com folga generosa
ROUNDS=(1 2 3 4 5)

declare -A VERSION_URL_VAR=(
  [springboot]="SPRINGBOOT_URL"
  [quarkus-jvm]="QUARKUS_JVM_URL"
  [quarkus-native]="QUARKUS_NATIVE_URL"
)
declare -A LOG_GROUPS=(
  [springboot]="/aws/lambda/order-processor-springboot"
  [quarkus-jvm]="/aws/lambda/order-processor-quarkus-jvm"
  [quarkus-native]="/aws/lambda/order-processor-quarkus-native"
)

STAGING_DIR="$REPO_ROOT/analysis/lambda/fase4_l2_recoleta_staging"
mkdir -p "$STAGING_DIR"
ENV_CSV="$REPO_ROOT/analysis/fase5/fase5_l2_ambientes_execucao.csv"

trap 'status "PARADO -- processo interrompido inesperadamente (sinal ou erro nao tratado). Ver $LOG_FILE. A infra AWS NAO foi derrubada de proposito -- relance este script para retomar de onde parou, ou rode teardown_infra.sh manualmente se for abandonar."' ERR

round_done() {
  local version="$1" round="$2"
  [[ -f "$STAGING_DIR/l2-${version}-r${round}-summary.json" && -f "$STAGING_DIR/l2-${version}-r${round}-latency.json" ]] \
    && [[ -f "$ENV_CSV" ]] && grep -q ",${version},${round},/aws/lambda/" "$ENV_CSV"
}

record_round_window() {
  local version="$1" round="$2" start="$3" end="$4"
  python3 -c "
import json, os
path = '$STAGING_DIR/_round_windows.json'
data = {}
if os.path.exists(path):
    with open(path) as fp:
        data = json.load(fp)
data['l2-${version}-r${round}'] = {'start': '$start', 'end': '$end'}
with open(path, 'w') as fp:
    json.dump(data, fp, indent=2, sort_keys=True)
"
}

run_one_round() {
  local version="$1" round="$2" url_var="$3" log_group="$4"
  local url="${!url_var}"

  log "=== $version rodada $round/5 -- iniciando (BASE_URL=$url) ==="
  status "$version rodada $round/5 iniciando..."

  local start_ts
  start_ts="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"

  # Dispara o k6 destacado (nohup) no runner, em vez de bloquear a sessao
  # SSH pelos ~12min do cenario -- assim um soluco de rede na conexao SSH
  # nao derruba o teste em andamento, so a checagem de progresso.
  local remote_launch
  read -r -d '' remote_launch <<EOF || true
rm -f /tmp/l2-done /tmp/l2-exit-code /tmp/l2-k6.log
nohup env BASE_URL='$url' L2_WARMUP_RATE=15 L2_RATE=31 L2_WARMUP_DURATION=2m L2_DURATION=10m \
  sh -c 'k6 run --out json=/tmp/l2-raw.json --summary-export=/tmp/l2-summary.json /tmp/scenarios/l2_warm_burst.js > /tmp/l2-k6.log 2>&1; echo \$? > /tmp/l2-exit-code; touch /tmp/l2-done' \
  >/dev/null 2>&1 &
disown
echo LAUNCHED
EOF
  retry_cmd 3 10 ssh -i "$RUNNER_KEY_PATH" -o StrictHostKeyChecking=accept-new "ec2-user@$RUNNER_IP" "$remote_launch"

  log "$version rodada $round: k6 disparado em background no runner, aguardando conclusao (max ${K6_MAX_WAIT_SECONDS}s)..."
  local waited=0 finished=false
  while (( waited < K6_MAX_WAIT_SECONDS )); do
    if ssh -i "$RUNNER_KEY_PATH" "ec2-user@$RUNNER_IP" '[ -f /tmp/l2-done ] && echo DONE' 2>/dev/null | grep -q DONE; then
      finished=true
      break
    fi
    sleep 15
    waited=$(( waited + 15 ))
  done
  local end_ts
  end_ts="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"

  if [[ "$finished" != true ]]; then
    fatal "$version rodada $round: k6 nao terminou apos ${K6_MAX_WAIT_SECONDS}s no runner. Verifique manualmente: ssh -i $RUNNER_KEY_PATH ec2-user@$RUNNER_IP 'tail -80 /tmp/l2-k6.log'"
  fi

  local remote_exit
  remote_exit=$(ssh -i "$RUNNER_KEY_PATH" "ec2-user@$RUNNER_IP" 'cat /tmp/l2-exit-code' 2>/dev/null || echo "unknown")
  if [[ "$remote_exit" != "0" ]]; then
    ssh -i "$RUNNER_KEY_PATH" "ec2-user@$RUNNER_IP" 'tail -80 /tmp/l2-k6.log' 2>&1 | tee -a "$LOG_FILE"
    fatal "$version rodada $round: k6 terminou com codigo $remote_exit no runner (log acima). Nao parece transitorio."
  fi

  record_round_window "$version" "$round" "$start_ts" "$end_ts"

  log "$version rodada $round: k6 concluido ($start_ts -> $end_ts). Extraindo latencias no runner..."
  ssh -i "$RUNNER_KEY_PATH" "ec2-user@$RUNNER_IP" "python3 -c \"
import json
vals = []
with open('/tmp/l2-raw.json') as fp:
    for line in fp:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get('type') == 'Point' and obj.get('metric') == 'http_req_duration':
            v = obj.get('data', {}).get('value')
            if v is not None:
                vals.append(v)
with open('/tmp/l2-latency.json', 'w') as fp:
    json.dump(vals, fp)
print(len(vals))
\""

  scp -i "$RUNNER_KEY_PATH" -q "ec2-user@$RUNNER_IP:/tmp/l2-summary.json" "$STAGING_DIR/l2-${version}-r${round}-summary.json"
  scp -i "$RUNNER_KEY_PATH" -q "ec2-user@$RUNNER_IP:/tmp/l2-latency.json" "$STAGING_DIR/l2-${version}-r${round}-latency.json"
  ssh -i "$RUNNER_KEY_PATH" "ec2-user@$RUNNER_IP" "rm -f /tmp/l2-raw.json /tmp/l2-summary.json /tmp/l2-latency.json /tmp/l2-k6.log /tmp/l2-done /tmp/l2-exit-code"

  local expected_count
  expected_count=$(python3 -c "import json; print(int(json.load(open('$STAGING_DIR/l2-${version}-r${round}-summary.json'))['metrics']['http_reqs']['count']))")

  local track_jit_flag=()
  if [[ "$version" == "springboot" || "$version" == "quarkus-jvm" ]]; then
    track_jit_flag=(--track-jit)
  fi

  log "$version rodada $round: consultando CloudWatch Logs Insights (log_group=$log_group, esperado=$expected_count invocacoes)..."
  local result_json
  result_json=$(python3 "$SCRIPT_DIR/cw_env_analysis.py" \
      --log-group "$log_group" --start "$start_ts" --end "$end_ts" \
      --versao "$version" --rodada "$round" --expected-count "$expected_count" \
      --out-csv "$ENV_CSV" --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" \
      "${track_jit_flag[@]}" 2>&1 | tee -a "$LOG_FILE") || \
    fatal "$version rodada $round: analise de ambientes CloudWatch falhou de forma nao transitoria (ver log acima)."

  local summary_line
  summary_line=$(printf '%s\n' "$result_json" | tail -1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"{d['versao']} rodada {d['rodada']}/5 concluída — ambientes: {d['num_ambientes']}, invocações min/mediana/max: {d['min_invocacoes_ambiente']}/{d['mediana_invocacoes_ambiente']}/{d['max_invocacoes_ambiente']}\")
")
  status "$summary_line"
  log "=== $version rodada $round/5 -- concluida ==="
}

main() {
  log "########## INICIO RECOLETA L2 ##########"
  status "Iniciando recoleta completa do cenario L2 (3 versoes x 5 rodadas, sem redeploy entre rodadas, gap ~48min)"

  if [[ -f "$STATE_DIR/infra.env" ]]; then
    log "state/infra.env ja existe -- reaproveitando infraestrutura ja provisionada (pulando fase de provisionamento)."
    # shellcheck disable=SC1090
    source "$STATE_DIR/infra.env"
  else
    provision_all
  fi

  for version in springboot quarkus-jvm quarkus-native; do
    url_var="${VERSION_URL_VAR[$version]}"
    log_group="${LOG_GROUPS[$version]}"
    for round in "${ROUNDS[@]}"; do
      if round_done "$version" "$round"; then
        log "$version rodada $round: ja concluida (checkpoint encontrado), pulando."
        continue
      fi
      if [[ "$round" != "1" ]]; then
        log "$version: aguardando ${ROUND_GAP_SECONDS}s (~48min) antes da proxima rodada, replicando o gap natural observado em julho/2026..."
        sleep "$ROUND_GAP_SECONDS"
      fi
      run_one_round "$version" "$round" "$url_var" "$log_group"
    done
  done

  log "Todas as 15 execucoes (3 versoes x 5 rodadas) concluidas. Rodando finalizacao (troca de dados + reanalise estatistica)..."
  python3 "$SCRIPT_DIR/finalize.py" --staging-dir "$STAGING_DIR" --repo-root "$REPO_ROOT" 2>&1 | tee -a "$LOG_FILE"

  log "Desligando o runner EC2 (a stack fica de pe -- ver teardown_infra.sh)..."
  "$SCRIPT_DIR/teardown_infra.sh" 2>&1 | tee -a "$LOG_FILE"

  status "CONCLUIDO -- ver analysis/l2_recoleta_resumo_final.md"
  log "########## FIM RECOLETA L2 ##########"
}

main
