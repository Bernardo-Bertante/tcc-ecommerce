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
BASE=/home/ec2-user/f2f3
BENCH=/home/ec2-user/ecommerce-tcc/benchmark
K6=/home/ec2-user/.local/bin/k6
CLUSTER=pgss-f2f3-cluster
SUBNET=subnet-09021fc5dd37000fc          # us-east-1c, a mesma das coletas oficiais
SG=sg-01b33c030e7c695bf                  # order-service-fargate-sg (oficial)
S3=s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds/f2_f3
source /home/ec2-user/db.env       # DB_HOST, PGPASSWORD
export PGPASSWORD PGCONNECT_TIMEOUT=10 PGSSLMODE=require
PSQL=(psql -h "$DB_HOST" -U orderuser -d orderdb -X -q -tA -v ON_ERROR_STOP=1)
mkdir -p $BASE/out/f2 $BASE/out/f3
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

declare -A HEALTH=([springboot]=/actuator/health [springboot-noval]=/actuator/health [quarkus-jvm]=/q/health)
# famílias de task def por condicao
declare -A FAMILIA=([springboot]=pgss-f2f3-springboot [springboot-noval]=pgss-f2f3-springboot-noval [quarkus-jvm]=pgss-f2f3-quarkus-jvm)

stop_family() {
	local fam=$1 a
	for a in $(awsr ecs list-tasks --cluster $CLUSTER --family "$fam" --desired-status RUNNING --query taskArns --output text); do
		log "  stop-task $a"; awsr ecs stop-task --cluster $CLUSTER --task "$a" >/dev/null
	done
}
on_exit() {
	local p; for p in $(jobs -p); do kill "$p" 2>/dev/null; done
	for f in "${FAMILIA[@]}"; do stop_family $f; done
	log "orquestrador saiu (tasks paradas)"
}
trap on_exit EXIT
trap "exit 143" TERM INT

fresh_task() {   # $1 runtime  $2 dir -> echo "arn ip"
	local rt=$1 dir=$2 fam=${FAMILIA[$1]} arn ip eni i st f
	for f in "${FAMILIA[@]}"; do stop_family "$f"; done; sleep 15
	arn=$(awsr ecs run-task --cluster $CLUSTER --task-definition "$fam" --count 1 --launch-type FARGATE \
		--started-by pgss-f2f3 \
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
	local i
	for i in 1 2 3 4 5 6; do
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
	) to stdout with (format csv, header true)" > "$1" && [[ -s "$1" ]] && return 0
	log "  dump falhou (tentativa $i)"; sleep 10
	done
	return 1
}


# estado fisico das tabelas ao fim da rodada: testa a anomalia de blocos/linha
estado_fisico() {   # $1 dir
	"${PSQL[@]}" -F $'\t' -c "select 'stats', tablename, attname, correlation, n_distinct, null_frac
		from pg_stats where schemaname='public' and tablename in ('orders','order_items')
		  and attname in ('created_at','customer_id','id','order_id','status')" > "$1/estado_pg_stats.tsv"
	"${PSQL[@]}" -F $'\t' -c "select relname, n_live_tup, n_dead_tup, n_tup_ins, n_tup_upd, n_tup_hot_upd,
		n_tup_del, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch, autovacuum_count, autoanalyze_count,
		pg_relation_size(relid) bytes_tabela, pg_indexes_size(relid) bytes_indices,
		pg_relation_size(relid)/8192 paginas
		from pg_stat_user_tables where schemaname='public'" > "$1/estado_tabelas.tsv"
	"${PSQL[@]}" -F $'\t' -c "select relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch,
		pg_relation_size(indexrelid) bytes from pg_stat_user_indexes where schemaname='public'" > "$1/estado_indices.tsv"
	"${PSQL[@]}" -F $'\t' -c "select relname, heap_blks_read, heap_blks_hit, idx_blks_read, idx_blks_hit
		from pg_statio_user_tables where schemaname='public'" > "$1/estado_statio.tsv"
}

snap_db() {   # $1 arquivo
	"${PSQL[@]}" -F $'\t' -c "select extract(epoch from clock_timestamp()), numbackends, xact_commit, xact_rollback,
		blks_read, blks_hit, tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted,
		session_time, active_time, idle_in_transaction_time, sessions, sessions_abandoned, sessions_fatal, sessions_killed
		from pg_stat_database where datname='orderdb'" >> "$1"
}

run_round() {    # $1 fase  $2 posicao  $3 condicao
	local fase=$1 pos=$2 rt=$3 dir=$BASE/out/$1/r$2-$3
	rm -rf "$dir"; mkdir -p "$dir"; log "=== $fase rodada $pos: $rt ==="
	local arn ip ti
	ti=$(fresh_task "$rt" "$dir") || { log "ERRO: task não subiu"; return 2; }
	read -r arn ip <<< "$ti"
	log "  TRUNCATE + reset pg_stat_statements"
	"${PSQL[@]}" -c "TRUNCATE TABLE order_status_history, order_items, orders;" || return 2
	[[ "$("${PSQL[@]}" -c "select count(*) from orders")" == 0 ]] || { log "ERRO: orders não vazia"; return 2; }
	"${PSQL[@]}" -c "VACUUM ANALYZE orders, order_items, order_status_history;" >/dev/null 2>&1
	"${PSQL[@]}" -c "select pg_stat_statements_reset();" >/dev/null
	# configuração efetiva do auto_explain, registrada junto da rodada
	"${PSQL[@]}" -c "select name||'='||setting from pg_settings where name like 'auto_explain%' or name like 'pg_stat_statements%' or name='shared_preload_libraries'" > "$dir/auto_explain_settings.txt"
	snap_db "$dir/pg_stat_database.tsv"
	local t0 t0e; t0=$(date -u +%FT%TZ); t0e=$(date +%s)
	log "  k6 $fase começa $t0"
	local raw=/var/tmp/$fase-r$pos-$rt-raw.json.gz
	(
		cd $BENCH
		export BASE_URL="http://$ip:8081"
		if [[ $fase == f2 ]]; then
			# F2 reduzido: taxas oficiais (48 -> 96), durações encurtadas (oficial: 10m / 90s / 30m / 3m)
			export F2_WARMUP_RATE=48 F2_RATE=96 F2_PREWARM_DURATION=${OVR_F2_PREWARM:-2m} F2_RAMP_UP=${OVR_F2_RAMP:-90s} F2_DURATION=${OVR_F2_HOLD:-7m} F2_RAMP_DOWN=${OVR_F2_DOWN:-1m}
			export PRE_ALLOCATED_VUS=800 MAX_VUS=1500
			SCEN=scenarios/f2_high_load.js
		else
			# F3 completo, exatamente como nas coletas oficiais (25 min, 208.800 iterações)
			export F3_BASELINE_RATE=48 F3_PEAK_RATE=240 F3_RECOVERY_RATE=48
			# OVR_* existem só para o smoke; sem eles valem as durações oficiais
			export F3_BASELINE_DURATION=${OVR_F3_BASE:-5m} F3_RAMP_UP_DURATION=${OVR_F3_RAMP:-2m} F3_PEAK_DURATION=${OVR_F3_PEAK:-10m}
			export F3_RECOVERY_RAMP_DURATION=${OVR_F3_RAMP:-2m} F3_RECOVERY_DURATION=${OVR_F3_REC:-5m} F3_RAMP_DOWN_DURATION=${OVR_F3_DOWN:-1m}
			export PRE_ALLOCATED_VUS=1500 MAX_VUS=3000
			SCEN=scenarios/f3_black_friday_controlled.js
		fi
		timeout --signal=INT 3000 $K6 run --out json=$raw --summary-export="$dir/summary.json" $SCEN > "$dir/k6.log" 2>&1
		echo $? > "$dir/k6rc.txt"
	)
	local t1 t1e; t1=$(date -u +%FT%TZ); t1e=$(date +%s)
	snap_db "$dir/pg_stat_database.tsv"
	log "  k6 terminou $t1 (rc=$(cat $dir/k6rc.txt))"
	dump_pgss "$dir/pg_stat_statements.csv" || log "ERRO: dump perdido"
	"${PSQL[@]}" -c "ANALYZE orders, order_items;" >/dev/null 2>&1
	estado_fisico "$dir"
	"${PSQL[@]}" -F $'\t' -c "select relname, n_live_tup, seq_scan, idx_scan, n_tup_ins, n_tup_upd
		from pg_stat_user_tables where relname in ('orders','order_items','order_status_history')" > "$dir/pg_stat_user_tables.tsv"
	echo "{\"fase\":\"$fase\",\"posicao\":$pos,\"runtime\":\"$rt\",\"carga_inicio_utc\":\"$t0\",\"carga_fim_utc\":\"$t1\",\"epoch_inicio\":$t0e,\"epoch_fim\":$t1e,\"task_arn\":\"$arn\",\"task_ip\":\"$ip\",\"db_host\":\"$DB_HOST\"}" > "$dir/meta.json"
	log "  linhas no dump: $(( $(wc -l < "$dir/pg_stat_statements.csv") - 1 ))"
	awsr ecs stop-task --cluster $CLUSTER --task "$arn" >/dev/null && log "  task da rodada parada"
	local nreq; nreq=$(python3 $BASE/extrai_requisicoes.py "$raw" "$dir/requests.csv.gz" 2>>$BASE/out/orquestrador.log)
	log "  requisições extraídas: $nreq"
	mv "$raw" "$dir/k6_raw.json.gz"
	touch "$dir/DONE"
	awsr s3 sync --quiet "$dir" "$S3/$fase/r$pos-$rt/" || log "  AVISO: upload S3 falhou"
}

log "plano: $PLAN"
for item in $PLAN; do
	for ATTEMPT in 1 2 3; do
		IFS=: read -r _f _p _c <<< "$item"
		run_round "$_f" "$_p" "$_c"; rc=$?
		[[ $rc == 0 ]] && break
		log "rodada $item: falha de infra (tentativa $ATTEMPT) — nova em 2 min"; sleep 120
	done
done
log "plano concluído"
