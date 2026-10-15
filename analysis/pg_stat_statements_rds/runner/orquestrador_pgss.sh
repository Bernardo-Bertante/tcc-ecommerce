#!/usr/bin/env bash
#
# orquestrador_pgss.sh — investigação EXPLORATÓRIA: custo por tipo de consulta no RDS,
# Spring Boot x Quarkus JVM (não é coleta oficial do TCC).
#
# Deriva de analysis/reproducao_f3_instabilidade/runner/orquestrador.sh. Diferenças:
#   - cenário F1 (48 req/s constante, ~14 min) em vez da rampa do F3;
#   - dump COMPLETO de pg_stat_statements ao fim de cada rodada (não só o top 25);
#   - marca a janela [inicio,fim] da carga para recortar os planos do auto_explain depois;
#   - sem amostradores de app/TCP/flow-log (não são necessários aqui).
#
# Protocolo por rodada: stop-task -> run-task fresca -> health -> TRUNCATE das 3 tabelas ->
#                       pg_stat_statements_reset() -> k6 F1 -> dump da view.
# Uso: orquestrador_pgss.sh "springboot quarkus-jvm"
set -uo pipefail

export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export AWS_RETRY_MODE=adaptive AWS_MAX_ATTEMPTS=10
PLAN="${1:?lista de runtimes, ex.: \"springboot quarkus-jvm\"}"
BASE=/home/ec2-user/pgss
BENCH=/home/ec2-user/ecommerce-tcc/benchmark
K6=/home/ec2-user/.local/bin/k6
CLUSTER=repro-f3-cluster
SUBNET=subnet-09021fc5dd37000fc          # us-east-1c, a mesma das coletas oficiais
SG=sg-01b33c030e7c695bf                  # order-service-fargate-sg (oficial)
S3=s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds
source /home/ec2-user/repro/db.env       # DB_HOST, PGPASSWORD
export PGPASSWORD PGCONNECT_TIMEOUT=10 PGSSLMODE=require
PSQL=(psql -h "$DB_HOST" -U orderuser -d orderdb -X -q -tA -v ON_ERROR_STOP=1)
mkdir -p $BASE/out
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a $BASE/out/orquestrador.log >&2; }

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
}
trap on_exit EXIT
trap "exit 143" TERM INT

fresh_task() {   # $1 runtime  $2 dir -> echo "arn ip"
	local rt=$1 dir=$2 fam=repro-f3-$1 arn ip eni i st
	stop_family "$fam"; sleep 8
	arn=$(awsr ecs run-task --cluster $CLUSTER --task-definition "$fam" --count 1 --launch-type FARGATE \
		--started-by pgss-probe \
		--network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
		--query 'tasks[0].taskArn' --output text) || return 1
	[[ -n "$arn" && "$arn" != None ]] || { log "  run-task sem ARN"; return 1; }
	log "  run-task $arn"; sleep 20
	if ! aws ecs wait tasks-running --cluster $CLUSTER --tasks "$arn" 2>>$BASE/out/aws_erros.log; then
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

# dump COMPLETO da view, em CSV, de todas as consultas do orderdb
dump_pgss() {    # $1 arquivo csv
	"${PSQL[@]}" -c "\copy (
		select queryid, calls, rows,
		       round(total_exec_time::numeric,3)  as total_exec_time_ms,
		       round(mean_exec_time::numeric,4)   as mean_exec_time_ms,
		       round(stddev_exec_time::numeric,4) as stddev_exec_time_ms,
		       round(min_exec_time::numeric,4)    as min_exec_time_ms,
		       round(max_exec_time::numeric,4)    as max_exec_time_ms,
		       shared_blks_hit, shared_blks_read, shared_blks_dirtied, shared_blks_written,
		       local_blks_hit, local_blks_read, temp_blks_read, temp_blks_written,
		       round(blk_read_time::numeric,3) as blk_read_time_ms,
		       round(total_plan_time::numeric,3) as total_plan_time_ms, plans,
		       wal_records, wal_fpi, wal_bytes,
		       regexp_replace(query, '[\n\r\t]+', ' ', 'g') as query
		from pg_stat_statements
		where dbid = (select oid from pg_database where datname='orderdb')
		order by total_exec_time desc
	) to stdout with (format csv, header true)" > "$1"
}

run_round() {    # $1 runtime
	local rt=$1 dir=$BASE/out/f1-$1
	rm -rf "$dir"; mkdir -p "$dir"; log "=== f1-$rt ==="
	local arn ip ti
	ti=$(fresh_task "$rt" "$dir") || { log "ERRO: task não subiu"; return 2; }
	read -r arn ip <<< "$ti"
	log "  TRUNCATE + reset pg_stat_statements"
	"${PSQL[@]}" -c "TRUNCATE TABLE order_status_history, order_items, orders;" || return 2
	[[ "$("${PSQL[@]}" -c "select count(*) from orders")" == 0 ]] || { log "ERRO: orders não vazia"; return 2; }
	"${PSQL[@]}" -c "VACUUM ANALYZE orders, order_items, order_status_history;" >/dev/null 2>&1
	"${PSQL[@]}" -c "select pg_stat_statements_reset();" >/dev/null
	# configuração efetiva do auto_explain, registrada junto da rodada
	"${PSQL[@]}" -c "select name||'='||setting from pg_settings where name like 'auto_explain%' or name='shared_preload_libraries'" > "$dir/auto_explain_settings.txt"
	local t0 t0e; t0=$(date -u +%FT%TZ); t0e=$(date +%s)
	log "  k6 F1 começa $t0"
	(
		cd $BENCH
		export BASE_URL="http://$ip:8081"
		export F1_RATE=48 F1_RAMP_UP=1m F1_DURATION=${F1_DURATION:-14m} F1_RAMP_DOWN=1m
		export PRE_ALLOCATED_VUS=80 MAX_VUS=200
		timeout --signal=INT 2400 $K6 run --summary-export="$dir/summary.json" \
			scenarios/f1_low_load.js > "$dir/k6.log" 2>&1
		echo $? > "$dir/k6rc.txt"
	)
	local t1 t1e; t1=$(date -u +%FT%TZ); t1e=$(date +%s)
	log "  k6 terminou $t1 (rc=$(cat $dir/k6rc.txt))"
	dump_pgss "$dir/pg_stat_statements.csv"
	"${PSQL[@]}" -F $'\t' -c "select relname, n_live_tup, seq_scan, idx_scan, n_tup_ins, n_tup_upd
		from pg_stat_user_tables where relname in ('orders','order_items','order_status_history')" > "$dir/pg_stat_user_tables.tsv"
	echo "{\"runtime\":\"$rt\",\"carga_inicio_utc\":\"$t0\",\"carga_fim_utc\":\"$t1\",\"epoch_inicio\":$t0e,\"epoch_fim\":$t1e,\"task_arn\":\"$arn\",\"task_ip\":\"$ip\",\"db_host\":\"$DB_HOST\"}" > "$dir/meta.json"
	log "  linhas no dump: $(( $(wc -l < "$dir/pg_stat_statements.csv") - 1 ))"
	touch "$dir/DONE"
	awsr s3 sync --quiet "$dir" "$S3/f1-$rt/" || log "  AVISO: upload S3 falhou"
}

log "plano: $PLAN"
for rt in $PLAN; do
	for ATTEMPT in 1 2 3; do
		run_round "$rt"; rc=$?
		[[ $rc == 0 ]] && break
		log "rodada $rt: falha de infra (tentativa $ATTEMPT) — nova em 2 min"; sleep 120
	done
done
log "plano concluído"
