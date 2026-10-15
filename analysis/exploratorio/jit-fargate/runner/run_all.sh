#!/usr/bin/env bash
#
# run_all.sh — driver autônomo do teste EXPLORATÓRIO de nível JIT no Fargate (fora do desenho oficial).
# Roda no exp-jit-runner via systemd-run, com a instance role (sem sessão SSO).
#
# Por rodada (versão × cenário): stop-task -> run-task fresca (ECS Exec ligado) -> health ->
#   TRUNCATE (F2-S: + 50.000 linhas) -> k6 com a carga oficial -> jcmd (VM.command_line, VM.flags,
#   Compiler.codelist) via ECS Exec -> stop-task -> logs do CloudWatch -> análise -> upload ao S3.
# No fim: relatório preliminar, upload, teardown (teardown.sh) e DONE/FAILED no S3.
#
# Uso: run_all.sh <modo: full|smoke> "<plano: cen:rt ...>"
#   ex.: run_all.sh full "f1:springboot f1:quarkus-jvm f2:springboot f2:quarkus-jvm f2s:springboot f2s:quarkus-jvm f3:springboot f3:quarkus-jvm"
set -uo pipefail

MODO="${1:?modo full|smoke}"
PLANO="${2:?plano}"
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 AWS_RETRY_MODE=adaptive AWS_MAX_ATTEMPTS=10
BASE=/home/ec2-user/exp-jit
BENCH=$BASE/bench                      # cópia de benchmark/scenarios + benchmark/lib (HEAD 6b90310)
OUT=$BASE/out-$MODO
CLUSTER=exp-jit-cluster
SUBNET=subnet-09021fc5dd37000fc        # us-east-1c, a mesma das coletas oficiais
SG=sg-00ae93985944f5560                # exp-jit-task-sg
S3=s3://exp-jit-results-776648109551/$MODO
DB_HOST=exp-jit-postgres.ck1kkwa6og4s.us-east-1.rds.amazonaws.com
declare -A FAMILIA=([springboot]=exp-jit-springboot [quarkus-jvm]=exp-jit-quarkus-jvm)
declare -A CONTAINER=([springboot]=order-service-springboot [quarkus-jvm]=order-service-quarkus-jvm)
declare -A HEALTH=([springboot]=/actuator/health [quarkus-jvm]=/q/health)
declare -A PATHFILE=([springboot]=summary_path_springboot.txt [quarkus-jvm]=summary_path_quarkus.txt)

mkdir -p "$OUT/csv"
LOG=$OUT/driver.log
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG" >&2; }
STATUS_TXT=""
status() {   # STATUS = estado atual + histórico das rodadas; sobe ao S3 a cada etapa
	STATUS_TXT="$*"
	{ echo "modo=$MODO atualizado=$(date -u +%FT%TZ)"; echo "etapa: $*"; echo "--- rodadas:"; cat "$OUT/rodadas.txt" 2>/dev/null; } > "$OUT/STATUS"
	aws s3 cp --quiet "$OUT/STATUS" "$S3/STATUS" || true
	aws s3 cp --quiet "$LOG" "$S3/driver.log" || true
}

awsr() {   # aws com novas tentativas (erros transitórios do ECS/ECR já vistos em setembro)
	local i out
	for i in 1 2 3 4 5 6 7 8 9 10; do
		if out=$(aws "$@" 2>>"$OUT/aws_erros.log"); then printf '%s' "$out"; [[ -n "$out" ]] && echo; return 0; fi
		[[ $i == 10 ]] && break
		log "  aws $1 $2 falhou (tentativa $i) — nova em $((i*10)) s"; sleep $((i*10))
	done
	return 1
}

db_password() { aws secretsmanager get-secret-value --secret-id exp-jit-db --query SecretString --output text; }
PGPASSWORD="$(db_password)" || { log "ERRO: não li o segredo do banco"; exit 1; }
export PGPASSWORD PGCONNECT_TIMEOUT=15 PGSSLMODE=require
PSQL=(psql -h "$DB_HOST" -U orderuser -d orderdb -X -q -tA -v ON_ERROR_STOP=1)

stop_all() {
	local a
	for a in $(awsr ecs list-tasks --cluster $CLUSTER --desired-status RUNNING --query taskArns --output text); do
		[[ "$a" == None ]] && continue
		log "  stop-task $a"; awsr ecs stop-task --cluster $CLUSTER --task "$a" --reason exp-jit-driver >/dev/null
	done
}

FALHA_FATAL=""
on_exit() {
	local rc=$?
	trap - EXIT
	if [[ -z "$FALHA_FATAL" && $rc != 0 ]]; then FALHA_FATAL="driver saiu com rc=$rc na etapa: $STATUS_TXT"; fi
	stop_all
	if [[ -n "$FALHA_FATAL" ]]; then
		log "FALHA: $FALHA_FATAL"
		echo "$FALHA_FATAL" > "$OUT/FAILED"; aws s3 cp --quiet "$OUT/FAILED" "$S3/FAILED" || true
		status "FAILED: $FALHA_FATAL — teardown"
	fi
	"$BASE/teardown.sh" "$MODO" driver
}
trap on_exit EXIT
trap 'FALHA_FATAL="sinal TERM/INT recebido"; exit 143' TERM INT

fresh_task() {   # $1 runtime  $2 dir -> ecoa "arn ip"
	local rt=$1 dir=$2 arn ip eni i st
	stop_all; sleep 15
	arn=$(awsr ecs run-task --cluster $CLUSTER --task-definition "${FAMILIA[$rt]}" --count 1 --launch-type FARGATE \
		--platform-version 1.4.0 --enable-execute-command --started-by exp-jit \
		--network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
		--query 'tasks[0].taskArn' --output text) || return 1
	[[ -n "$arn" && "$arn" != None ]] || { log "  run-task sem ARN"; return 1; }
	log "  run-task $arn"; echo "$arn" > "$dir/task_arn.txt"; sleep 20
	if ! aws ecs wait tasks-running --cluster $CLUSTER --tasks "$arn" 2>>"$OUT/aws_erros.log"; then
		log "  task não ficou RUNNING: $(awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" \
			--query 'tasks[0].[lastStatus,stopCode,stoppedReason]' --output text | tr '\t' ' ' | cut -c1-300)"
		awsr ecs stop-task --cluster $CLUSTER --task "$arn" >/dev/null; return 1
	fi
	awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" --output json > "$dir/task_running.json" || return 1
	eni=$(jq -r '.tasks[0].attachments[0].details[]|select(.name=="networkInterfaceId").value' "$dir/task_running.json")
	ip=$(awsr ec2 describe-network-interfaces --network-interface-ids "$eni" --query 'NetworkInterfaces[0].Association.PublicIp' --output text) || return 1
	[[ -n "$ip" && "$ip" != None ]] || return 1
	for i in $(seq 1 60); do
		st=$(curl -s -m 5 "http://$ip:8081${HEALTH[$rt]}" | tr -d ' \n')
		[[ "$st" == *'"status":"UP"'* ]] && { log "  health UP ($i) ip=$ip"; echo "$arn $ip"; return 0; }
		sleep 5
	done
	log "  health não ficou UP em 5 min"; awsr ecs stop-task --cluster $CLUSTER --task "$arn" >/dev/null; return 1
}

ecs_exec() {   # $1 arn  $2 container  $3 comando (sh -c) -> stdout bruto da sessão
	# execute-command só existe no modo interativo; `script` fornece o pseudo-TTY que o plugin exige.
	local cmd
	cmd=$(printf '%q ' aws ecs execute-command --cluster "$CLUSTER" --task "$1" --container "$2" --interactive --command "sh -c '$3'")
	timeout 300 script -q -e -c "$cmd" /dev/null
}

jcmd_round() {   # $1 arn $2 runtime $3 dir — depois do k6 e antes de parar a task
	local arn=$1 rt=$2 dir=$3 i ag
	for i in $(seq 1 24); do   # agente do ECS Exec precisa estar RUNNING
		ag=$(awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" --query 'tasks[0].containers[0].managedAgents[0].lastStatus' --output text)
		[[ "$ag" == RUNNING ]] && break; sleep 5
	done
	echo "$ag" > "$dir/ecs_exec_agent.txt"
	for i in 1 2 3; do
		ecs_exec "$arn" "${CONTAINER[$rt]}" "jcmd 1 VM.command_line; jcmd 1 VM.flags; echo __FIM_FLAGS__" > "$dir/jcmd_vm_bruto.txt" 2>&1
		grep -q "__FIM_FLAGS__" "$dir/jcmd_vm_bruto.txt" && break
		log "  jcmd VM.* sem sentinela (tentativa $i)"; sleep 10
	done
	for i in 1 2 3; do
		ecs_exec "$arn" "${CONTAINER[$rt]}" "jcmd 1 Compiler.codelist; echo __FIM_CODELIST__ rc=\$?" > "$dir/codelist_bruto.txt" 2>&1
		grep -q "__FIM_CODELIST__ rc=0" "$dir/codelist_bruto.txt" && break
		log "  jcmd Compiler.codelist sem sentinela rc=0 (tentativa $i)"; sleep 10
	done
	tr -d '\r' < "$dir/codelist_bruto.txt" | grep -E '^[0-9]+ -?[0-9]+ [0-9]+ ' > "$dir/codelist.txt" || true
	log "  jcmd: agente=$ag, codelist=$(wc -l < "$dir/codelist.txt") entradas, sentinela=$(grep -c __FIM_CODELIST__ "$dir/codelist_bruto.txt")"
}

baixa_logs() {   # $1 runtime $2 arn $3 dir -> logs.jsonl.gz (todos os eventos do stream, em ordem)
	local rt=$1 arn=$2 dir=$3 grp=${FAMILIA[$1]} stream tok prev="" n=0 pag=0 resp
	stream="ecs/${CONTAINER[$rt]}/${arn##*/}"
	echo "$grp $stream" > "$dir/log_stream.txt"
	: > "$dir/logs.jsonl"
	resp=$(awsr logs get-log-events --log-group-name "$grp" --log-stream-name "$stream" --start-from-head --limit 10000 --output json) || return 1
	while :; do
		pag=$((pag+1))
		jq -c '.events[] | {t: .timestamp, m: .message}' <<< "$resp" >> "$dir/logs.jsonl"
		tok=$(jq -r .nextForwardToken <<< "$resp")
		[[ -z "$tok" || "$tok" == null || "$tok" == "$prev" || $pag -ge 3000 ]] && break
		prev=$tok
		resp=$(awsr logs get-log-events --log-group-name "$grp" --log-stream-name "$stream" --next-token "$tok" --limit 10000 --output json) || return 1
	done
	n=$(wc -l < "$dir/logs.jsonl"); gzip -f "$dir/logs.jsonl"
	log "  logs: $n eventos ($pag páginas) de $grp/$stream"
	[[ $n -gt 0 ]]
}

k6_env() {   # $1 cenário -> exports + echo do script k6. Carga oficial (metodologia; f1_rerun.sh/f3_rerun.sh/09-scripts.md)
	case $1 in
	f1)  export F1_RATE=48 F1_START_RATE=1 F1_RAMP_UP=${OVR_F1_RAMP:-2m} F1_DURATION=${OVR_F1_HOLD:-20m} F1_RAMP_DOWN=${OVR_F1_DOWN:-2m}
	     export PRE_ALLOCATED_VUS=80 MAX_VUS=200; echo scenarios/f1_low_load.js ;;
	f2)  export F2_WARMUP_RATE=48 F2_RATE=96 F2_PREWARM_DURATION=10m F2_RAMP_UP=90s F2_DURATION=30m F2_RAMP_DOWN=3m
	     export PRE_ALLOCATED_VUS=800 MAX_VUS=1500; echo scenarios/f2_high_load.js ;;
	f2s) export F2S_RATE=8; echo scenarios/f2s_summary_only.js ;;
	f3)  export F3_BASELINE_RATE=48 F3_PEAK_RATE=240 F3_RECOVERY_RATE=48
	     export F3_BASELINE_DURATION=5m F3_RAMP_UP_DURATION=2m F3_PEAK_DURATION=10m F3_RECOVERY_RAMP_DURATION=2m F3_RECOVERY_DURATION=5m F3_RAMP_DOWN_DURATION=1m
	     export PRE_ALLOCATED_VUS=1500 MAX_VUS=3000; echo scenarios/f3_black_friday_controlled.js ;;
	esac
}

prepara_banco() {   # $1 cenário
	"${PSQL[@]}" -c "TRUNCATE TABLE order_status_history, order_items, orders;" || return 1
	if [[ $1 == f2s ]]; then
		"${PSQL[@]}" -f "$BASE/db/popular_orders_summary.sql" || return 1
		local n; n=$("${PSQL[@]}" -c "select count(*) from orders")
		[[ "$n" == 50000 ]] || { log "  ERRO: F2-S com $n linhas (esperado 50000)"; return 1; }
		log "  F2-S: TRUNCATE + 50000 linhas conferidas"
	else
		[[ "$("${PSQL[@]}" -c "select count(*) from orders")" == 0 ]] || return 1
		log "  TRUNCATE conferido (orders vazia)"
	fi
}

run_round() {   # $1 cenário $2 runtime -> 0 ok | 2 falha de infra antes do k6 | 3 k6 rodou mas pós-processamento falhou
	local cen=$1 rt=$2 dir=$OUT/rodadas/$1-$2 arn ip ti scen t0 t1 rc raw
	[[ -d "$dir" ]] && mv "$dir" "$dir._tentativa_falha_$(date +%s)"
	mkdir -p "$dir"; log "=== rodada $cen / $rt ==="
	status "rodada $cen/$rt: subindo task fresca"
	ti=$(fresh_task "$rt" "$dir") || { log "ERRO: task não subiu"; return 2; }
	read -r arn ip <<< "$ti"
	status "rodada $cen/$rt: preparando banco"
	prepara_banco "$cen" || { log "ERRO: preparo do banco"; awsr ecs stop-task --cluster $CLUSTER --task "$arn" >/dev/null; return 2; }
	scen=$(k6_env "$cen")
	raw=$dir/k6_raw.json.gz
	t0=$(date +%s%3N); status "rodada $cen/$rt: k6 $scen em curso desde $(date -u +%T)Z"
	log "  k6 $scen (alvo $ip)"
	( cd "$BENCH" && k6_env "$cen" >/dev/null && BASE_URL="http://$ip:8081" timeout --signal=INT "${K6_TIMEOUT:-3300}" k6 run --out "json=$raw" \
		--summary-export="$dir/summary.json" "$scen" > "$dir/k6.log" 2>&1; echo $? > "$dir/k6rc.txt" )
	t1=$(date +%s%3N); rc=$(cat "$dir/k6rc.txt"); log "  k6 terminou rc=$rc ($(( (t1-t0)/1000 )) s)"
	status "rodada $cen/$rt: jcmd via ECS Exec"
	jcmd_round "$arn" "$rt" "$dir"
	awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" --output json > "$dir/task_pos_carga.json"
	awsr ecs stop-task --cluster $CLUSTER --task "$arn" --reason exp-jit-fim-da-rodada >/dev/null
	aws ecs wait tasks-stopped --cluster $CLUSTER --tasks "$arn" 2>>"$OUT/aws_erros.log"; sleep 20
	status "rodada $cen/$rt: baixando logs e analisando"
	baixa_logs "$rt" "$arn" "$dir" || log "  ERRO: logs não baixados (ficam no CloudWatch)"
	local nreq; nreq=$(python3 "$BASE/extrai_requisicoes.py" "$raw" "$dir/requests.csv.gz" 2>>"$LOG")
	python3 - "$dir" "$cen" "$rt" "$t0" "$t1" "$ip" "$nreq" <<'PY' || log "  ERRO: meta.json"
import csv, gzip, json, sys
d, cen, rt, t0, t1, ip, nreq = sys.argv[1:]
ts = [int(r["epoch_ms"]) for r in csv.DictReader(gzip.open(d + "/requests.csv.gz", "rt")) if r["phase"] != "setup"]
t = json.load(open(d + "/task_running.json"))["tasks"][0]
c = t["containers"][0]
json.dump({"runtime": rt, "cenario": cen, "carga_inicio_ms": min(ts), "carga_fim_ms": max(ts),
           "k6_lancado_ms": int(t0), "k6_fim_ms": int(t1), "requisicoes_k6": int(nreq), "requisicoes_carga": len(ts),
           "task_arn": t["taskArn"], "task_definition": t["taskDefinitionArn"], "image": c["image"],
           "image_digest": c.get("imageDigest"), "task_created_at": t.get("createdAt"), "task_started_at": t.get("startedAt"),
           "platform_version": t.get("platformVersion"), "az": t.get("availabilityZone"), "cpu": t.get("cpu"),
           "memory": t.get("memory"), "task_ip": ip, "db_host": "exp-jit-postgres"}, open(d + "/meta.json", "w"), indent=1)
PY
	log "  requisições: $nreq; $(jq -c '{image_digest,task_started_at}' "$dir/meta.json" 2>/dev/null)"
	python3 "$BASE/analisa_jit.py" "$dir" "$BASE/${PATHFILE[$rt]}" "$OUT/csv" >> "$LOG" 2>&1 || log "  ERRO: análise da rodada"
	touch "$dir/DONE"
	awsr s3 sync --quiet "$dir" "$S3/rodadas/$cen-$rt/" || log "  AVISO: upload da rodada falhou"
	awsr s3 sync --quiet "$OUT/csv" "$S3/csv/" || true
	[[ -s "$dir/logs.jsonl.gz" && -s "$dir/meta.json" ]] || return 3
	return 0
}

log "início: modo=$MODO plano=$PLANO"
status "início"
: > "$OUT/rodadas.txt"
for item in $PLANO; do
	IFS=: read -r cen rt <<< "$item"
	res="falhou"
	for tent in 1 2 3; do
		run_round "$cen" "$rt"; rc=$?
		if [[ $rc == 0 ]]; then res="ok"; break; fi
		if [[ $rc == 3 ]]; then res="k6 rodou; pós-processamento incompleto"; break; fi   # nunca repetir carga que rodou
		log "rodada $item: falha de infra antes do k6 (tentativa $tent) — nova em 2 min"; sleep 120
	done
	echo "$item: $res ($(date -u +%T)Z)" >> "$OUT/rodadas.txt"
	status "rodada $item: $res; pausa curta"
	sleep "${PAUSA_S:-120}"
done

status "relatório preliminar"
python3 "$BASE/relatorio_preliminar.py" "$OUT/csv" "$OUT/rodadas" > "$OUT/RESULTADOS_JIT_FARGATE_preliminar.md" 2>>"$LOG" || log "ERRO: relatório preliminar"
aws s3 cp --quiet "$OUT/RESULTADOS_JIT_FARGATE_preliminar.md" "$S3/" || true
awsr s3 sync --quiet "$OUT/csv" "$S3/csv/" || true
if grep -q "falhou" "$OUT/rodadas.txt"; then
	echo "rodadas com falha: $(grep -c falhou "$OUT/rodadas.txt")" > "$OUT/DONE"
else
	echo "todas as rodadas ok" > "$OUT/DONE"
fi
cat "$OUT/rodadas.txt" >> "$OUT/DONE"
aws s3 cp --quiet "$OUT/DONE" "$S3/DONE"
status "rodadas concluídas; teardown"
log "plano concluído"
exit 0
