#!/usr/bin/env bash
#
# orquestrador.sh — reprodução EXPLORATÓRIA do F3 na AWS (não é coleta oficial do TCC).
# Roda NO RUNNER EC2, disparado via `systemd-run` (desacoplado de SSH). Usa a IAM role da
# instância (repro-f3-runner), não credenciais do notebook.
#
# Protocolo por rodada = benchmark/run/f3_rerun.sh (oficial):
#   stop-task antiga -> run-task (task fresca, JVM fria) -> health -> TRUNCATE -> k6 F3
#   (48/240/48, 5m/2m/10m/2m/5m/1m, VUs 1500/3000, mesmo cenário) -> extração.
# Acréscimos exploratórios (fora do oficial), todos passivos ou de baixa intrusão:
#   - amostrador de métricas da app a cada 5 s (actuator / q/metrics)  -> app_metrics.tsv
#   - amostrador do Postgres a cada 5 s (pg_stat_activity, n_live_tup) -> pg_activity.tsv
#   - snapshot de pg_stat_statements a cada 60 s                        -> pg_statements.tsv
#   - sonda de conexão TCP runner->RDS:5432 e runner->task:8081, 1 s    -> tcp_probe.tsv
#   - requisições por timestamp (do JSON bruto do k6)                    -> requests.csv.gz
#   - p95/p99/max imediatos                                             -> ../status.tsv
#
# Uso: orquestrador.sh <plano>   plano = "springboot:1 springboot:2 ... quarkus-jvm:1"
set -uo pipefail

export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
# retry nativo do CLI (5xx/throttling) — o default de 3 tentativas não aguentou o incidente de 21/09
export AWS_RETRY_MODE=adaptive AWS_MAX_ATTEMPTS=10
PLAN="${1:?plano de rodadas}"
RUN_ID="${RUN_ID:?RUN_ID (prefixo no S3, ex.: dia2)}"
BASE=/home/ec2-user/repro
BENCH=/home/ec2-user/ecommerce-tcc/benchmark
K6=/home/ec2-user/.local/bin/k6
CLUSTER=repro-f3-cluster
SUBNET=subnet-09021fc5dd37000fc          # us-east-1c, a mesma das coletas oficiais
SG=sg-01b33c030e7c695bf                  # order-service-fargate-sg (oficial)
S3=s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/reproducao_f3_instabilidade/runner_out_$RUN_ID
source $BASE/db.env                      # DB_HOST, PGPASSWORD (chmod 600, fora do repo)
export PGPASSWORD PGCONNECT_TIMEOUT=10 PGSSLMODE=require
PSQL=(psql -h "$DB_HOST" -U orderuser -d orderdb -X -q -tA -v ON_ERROR_STOP=1)
ROUND_TIMEOUT=2700
mkdir -p $BASE/out
STATUS=$BASE/out/status.tsv
[[ -f $STATUS ]] || printf 'rotulo\tinicio_carga_utc\tfim_carga_utc\titers\tdropped\tfail_rate\tp50_ms\tp95_ms\tp99_ms\tmax_ms\tpct_gt_1s\tk6_rc\ttask_id\ttask_az\n' > $STATUS

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a $BASE/out/orquestrador.log >&2; }

# awsr: qualquer chamada AWS com até 8 tentativas extras (10 s, 20 s, ... 80 s) por cima do retry
# nativo do CLI. Erros vão para o log; stdout fica limpo para quem captura a saída.
awsr() {
	local i out
	for i in 1 2 3 4 5 6 7 8 9; do
		if out=$(aws "$@" 2>>$BASE/out/aws_erros.log); then printf '%s' "$out"; [[ -n "$out" ]] && echo; return 0; fi
		[[ $i == 9 ]] && break
		log "  aws $1 $2 falhou (tentativa $i) — nova em $((i*10)) s"; sleep $((i*10))
	done
	return 1
}

declare -A HEALTH=([springboot]=/actuator/health [quarkus-jvm]=/q/health)

CUR_TASK=""
stop_family() {
	local fam=$1 a
	for a in $(awsr ecs list-tasks --cluster $CLUSTER --family "$fam" --desired-status RUNNING --query taskArns --output text); do
		log "  stop-task $a"; awsr ecs stop-task --cluster $CLUSTER --task "$a" >/dev/null
	done
}
on_exit() {
	local p; for p in $(jobs -p); do kill "$p" 2>/dev/null; done
	for f in repro-f3-springboot repro-f3-quarkus-jvm; do stop_family $f; done
	log "orquestrador saiu (tasks paradas)"
	# Desligamento automático (AUTOSTOP=1): 2 h depois de o plano terminar — ou morrer —, PARA o RDS
	# repro (não apaga: o PI some com a instância apagada) e desliga o runner (comportamento
	# de shutdown = stop, EBS preservado). Unit de sistema própria: sobrevive ao fim deste processo.
	# Desarmar: sudo systemctl stop repro-f3-autostop.timer
	if [[ "${AUTOSTOP:-0}" == 1 ]]; then
		sudo systemd-run --unit=repro-f3-autostop --on-active=2h --timer-property=AccuracySec=1min \
			/bin/bash -c 'aws --region us-east-1 rds stop-db-instance --db-instance-identifier repro-f3-postgres >> /home/ec2-user/repro/out/autostop.log 2>&1; shutdown -h now' \
			&& log "autostop armado: RDS stop + runner shutdown em 2 h ($(date -u -d '+2 hours' +%FT%TZ))"
	fi
}
trap on_exit EXIT
trap "exit 143" TERM INT   # garante que o EXIT (parar tasks + autostop) roda também em SIGTERM

fresh_task() {   # $1 runtime  $2 dir  -> echo "arn ip"   (rc!=0 = falha de infra, rodada pode ser refeita)
	local rt=$1 dir=$2 fam=repro-f3-$1 arn ip eni i st
	stop_family "$fam"
	sleep 8
	# 21/09 23:06Z: ServerException "Internal Error" em todo RunTask por ~70 s derrubou 5 rodadas.
	arn=$(awsr ecs run-task --cluster $CLUSTER --task-definition "$fam" --count 1 --launch-type FARGATE \
		--started-by repro-f3 \
		--network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
		--query 'tasks[0].taskArn' --output text) || return 1
	[[ -n "$arn" && "$arn" != None ]] || { log "  run-task sem ARN (falha de capacidade?)"; return 1; }
	log "  run-task $arn"
	sleep 20
	# Sem awsr aqui: se a task foi para STOPPED (ex.: 22/09 CannotPullContainerError transitório do
	# ECR), esperar de novo é inútil — registra o motivo e devolve falha de infra (rodada refeita).
	if ! aws ecs wait tasks-running --cluster $CLUSTER --tasks "$arn" 2>>$BASE/out/aws_erros.log; then
		log "  task não ficou RUNNING: $(awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" \
			--query 'tasks[0].[lastStatus,stopCode,stoppedReason]' --output text | tr '\t' ' ' | cut -c1-300)"
		awsr ecs stop-task --cluster $CLUSTER --task "$arn" >/dev/null
		return 1
	fi
	awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" --output json > "$dir/task_running.json" || return 1
	eni=$(jq -r '.tasks[0].attachments[0].details[]|select(.name=="networkInterfaceId").value' "$dir/task_running.json")
	ip=$(awsr ec2 describe-network-interfaces --network-interface-ids "$eni" --query 'NetworkInterfaces[0].Association.PublicIp' --output text) || return 1
	[[ -n "$ip" && "$ip" != None ]] || return 1
	for i in $(seq 1 60); do
		st=$(curl -s -m 5 "http://$ip:8081${HEALTH[$rt]}" | tr -d ' \n')
		[[ "$st" == *'"status":"UP"'* ]] && { log "  health UP ($i) ip=$ip eni=$eni"; echo "$arn $ip"; return 0; }
		sleep 5
	done
	log "  health não ficou UP em 5 min"
	awsr ecs stop-task --cluster $CLUSTER --task "$arn" >/dev/null
	return 1
}

wait_rds() {     # espera o RDS aceitar conexão (até 30 min)
	local i
	for i in $(seq 1 180); do
		"${PSQL[@]}" -c "select 1" >/dev/null 2>&1 && return 0
		(( i % 6 == 1 )) && log "  RDS não responde — aguardando"
		sleep 10
	done
	return 1
}

# --- amostradores (rodam em background durante a rodada) -----------------------------------
sample_app() {   # $1 runtime $2 ip $3 out
	local rt=$1 ip=$2 out=$3 m v
	local sb_metrics="r2dbc.pool.acquired r2dbc.pool.pending r2dbc.pool.idle r2dbc.pool.allocated process.cpu.usage system.load.average.1m jvm.threads.live"
	while true; do
		if [[ $rt == springboot ]]; then
			for m in $sb_metrics; do
				v=$(curl -s -m 2 "http://$ip:8081/actuator/metrics/$m" | jq -r '[.measurements[]?|select(.statistic=="VALUE").value]|add // empty' 2>/dev/null)
				printf '%s\t%s\t%s\n' "$(date +%s.%N)" "$m" "${v:-NA}"
			done
		else
			curl -s -m 2 "http://$ip:8081/q/metrics" | grep -E '^(vertx_pool|process_cpu_usage|system_load_average_1m|jvm_threads_live|vertx_sql)' \
				| sed "s/^/$(date +%s.%N)\t/"
		fi
		sleep 5
	done >> "$out"
}
sample_pg() {    # $1 out_activity
	while true; do
		"${PSQL[@]}" -F $'\t' -c "select extract(epoch from now()), coalesce(wait_event_type,'CPU/none'), coalesce(wait_event,'-'), state, count(*)
			from pg_stat_activity where datname='orderdb' and pid<>pg_backend_pid() group by 2,3,4
			union all select extract(epoch from now()),'n_live_tup',relname,'-',n_live_tup from pg_stat_user_tables where relname in ('orders','order_items','order_status_history')" 2>/dev/null
		sleep 5
	done >> "$1"
}
sample_stmts() { # $1 out
	while true; do
		"${PSQL[@]}" -F $'\t' -c "select extract(epoch from now()), queryid, calls, round(total_exec_time::numeric,3), round(mean_exec_time::numeric,4),
			round(max_exec_time::numeric,3), rows, shared_blks_hit, shared_blks_read, left(regexp_replace(query,'\s+',' ','g'),160)
			from pg_stat_statements where dbid=(select oid from pg_database where datname='orderdb') order by total_exec_time desc limit 25" 2>/dev/null
		sleep 60
	done >> "$1"
}
tcp_probe() {    # $1 task ip $2 out
	python3 - "$DB_HOST" "$1" >> "$2" <<'PY'
import socket, sys, time
targets=[("rds",sys.argv[1],5432),("task",sys.argv[2],8081)]
while True:
    t0=time.time()
    for name,h,p in targets:
        s=socket.socket(); s.settimeout(3); a=time.perf_counter()
        try: s.connect((h,p)); dt=(time.perf_counter()-a)*1000
        except Exception: dt=-1
        finally: s.close()
        print(f"{t0:.3f}\t{name}\t{dt:.3f}", flush=True)
    time.sleep(max(0,1-(time.time()-t0)))
PY
}

# --- uma rodada ----------------------------------------------------------------------------
run_round() {    # rc 0 = rodada registrada (boa ou ruim) · rc 2 = falha de infra ANTES da carga (refazer)
	local rt=$1 r=$2 tag="f3-$1-r$2" dir=$BASE/out/f3-$1-r$2
	if [[ -f $dir/DONE ]]; then log "checkpoint: $tag já registrada"; return 0; fi
	if [[ -d $dir ]]; then   # resto de tentativa anterior (infra ou crash do orquestrador): arquiva, não apaga
		mv "$dir" "$BASE/out/_tentativa_falha_${tag}_$(date -u +%H%M%S)"
	fi
	mkdir -p "$dir"; log "=== $tag ==="
	wait_rds || { log "ERRO: RDS indisponível ($tag)"; return 2; }
	local ti arn ip
	ti=$(fresh_task "$rt" "$dir") || { log "ERRO: task não subiu ($tag)"; return 2; }
	read -r arn ip <<< "$ti"; CUR_TASK=$arn
	log "  TRUNCATE + reset pg_stat_statements"
	"${PSQL[@]}" -c "TRUNCATE TABLE order_status_history, order_items, orders;" || { log "ERRO truncate"; return 2; }
	[[ "$("${PSQL[@]}" -c "select count(*) from orders")" == 0 ]] || { log "ERRO: orders não está vazia após TRUNCATE"; return 2; }
	"${PSQL[@]}" -c "select pg_stat_statements_reset();" >/dev/null
	sample_app "$rt" "$ip" "$dir/app_metrics.tsv" & local p1=$!
	sample_pg "$dir/pg_activity.tsv" & local p2=$!
	sample_stmts "$dir/pg_statements.tsv" & local p3=$!
	tcp_probe "$ip" "$dir/tcp_probe.tsv" & local p4=$!
	local t0; t0=$(date -u +%FT%TZ)
	(
		cd $BENCH
		export BASE_URL="http://$ip:8081"
		export F3_BASELINE_RATE=48 F3_PEAK_RATE=240 F3_RECOVERY_RATE=48
		export F3_BASELINE_DURATION=5m F3_RAMP_UP_DURATION=2m F3_PEAK_DURATION=10m
		export F3_RECOVERY_RAMP_DURATION=2m F3_RECOVERY_DURATION=5m F3_RAMP_DOWN_DURATION=1m
		export PRE_ALLOCATED_VUS=1500 MAX_VUS=3000
		export ${EXTRA_K6_ENV:-_NOOP=1}
		timeout --signal=INT $ROUND_TIMEOUT $K6 run --out json=/var/tmp/$tag-raw.json.gz \
			--summary-export="$dir/summary.json" scenarios/f3_black_friday_controlled.js > "$dir/k6.log" 2>&1
		echo $? > "$dir/k6rc.txt"
	)
	kill $p1 $p2 $p3 $p4 2>/dev/null; wait $p1 $p2 $p3 $p4 2>/dev/null
	local t1; t1=$(date -u +%FT%TZ)
	awsr ecs describe-tasks --cluster $CLUSTER --tasks "$arn" --output json > "$dir/task_after.json"
	echo "{\"k6_invoke_utc\":\"$t0\",\"k6_return_utc\":\"$t1\",\"task_arn\":\"$arn\",\"task_ip\":\"$ip\",\"db_host\":\"$DB_HOST\",\"tentativa\":${ATTEMPT:-1},\"run_id\":\"$RUN_ID\"}" > "$dir/meta.json"
	python3 $BASE/extrai_rodada.py "/var/tmp/$tag-raw.json.gz" "$dir" "$tag" "$(cat $dir/k6rc.txt)" >> $STATUS 2>>$BASE/out/orquestrador.log
	log "  $(tail -1 $STATUS)"
	# task morreu durante a carga? registra como está (não refaz: descartar rodada ruim enviesaria)
	local last; last=$(jq -r '.tasks[0].lastStatus' "$dir/task_after.json" 2>/dev/null)
	[[ "$last" == RUNNING ]] || log "  AVISO: task em '$last' ao fim da carga — rodada registrada assim mesmo, ver task_after.json"
	touch "$dir/DONE"
	awsr s3 sync --quiet "$dir" "$S3/$tag/" && awsr s3 cp --quiet $STATUS "$S3/status.tsv" || log "  AVISO: upload S3 falhou (dados ficam no runner)"
	# a task NÃO é parada aqui: como no oficial, a antiga só cai no início da próxima rodada.
}

# um timer de autostop de execução anterior (ou de um restart deste serviço) não pode disparar no meio
sudo systemctl stop repro-f3-autostop.timer 2>/dev/null && log "autostop anterior desarmado"
sudo systemctl reset-failed repro-f3-autostop.service repro-f3-autostop.timer 2>/dev/null

log "plano ($RUN_ID): $PLAN"
for item in $PLAN; do
	for ATTEMPT in 1 2 3 4 5 6; do
		run_round "${item%%:*}" "${item##*:}"; rc=$?
		[[ $rc == 0 ]] && break
		if [[ $ATTEMPT == 6 ]]; then log "rodada $item: 6 tentativas de infra falharam — desistindo dela"; break; fi
		log "rodada $item: falha de infra antes da carga — nova tentativa em $((ATTEMPT*2)) min"
		sleep $((ATTEMPT*120))
	done
done
log "plano concluído"
