#!/usr/bin/env bash
#
# f3_rerun.sh — Re-coleta dedicada do cenário F3 (Fargate, fase3) nas taxas CONFIRMADAS
#   baseline 48 / pico 240 / recuperação 48 iter/s, durações 5m/2m/10m/2m/5m/1m.
#
# Motivo: o F3 NÃO tem bug de taxa — a coleta original de julho (analysis/fargate/fase3/f3-*)
# rodou correta (208.799 iterações/rodada vs. 208.800 teóricas, dropped=0, 0 falha). O único
# problema é PRECISÃO DE MEDIÇÃO de CPU/memória: a métrica de 1 min do CloudWatch já expirou
# para julho, sobrando só pontos de 5 em 5 min (2 pontos na fase de pico de 10 min). Esta
# re-coleta captura a métrica fresca (1 min) e grava timestamps EXATOS de cada fase por rodada
# (via primeiro/último Point de carga no JSON bruto do k6), para extração isolada do pico.
#
# As taxas de julho foram passadas por env vars efêmeras nunca versionadas (mesmo padrão que
# causou o bug do F1). Aqui elas são explícitas e o scenario passa a exigi-las (sem default
# silencioso) — ver o guard em benchmark/scenarios/f3_black_friday_controlled.js.
#
# Metodologia: idêntica ao bloco_fargate.sh original (porção F3) e ao f1_rerun.sh:
#   stop-task -> run-task (task fresca) -> aguardar health -> TRUNCATE no RDS -> k6 no runner
#   -> extrair latency.json + timing de fase no runner -> scp de volta. Uma task fresca por
#   rodada. NÃO cria infraestrutura; o preflight aborta se algo faltar.
#
# Uso:
#   RUNNER_IP=<ip> benchmark/run/f3_rerun.sh
#   RUNNER_IP=<ip> DRY_RUN=1 benchmark/run/f3_rerun.sh                       # só preflight
#   RUNNER_IP=<ip> ROUNDS="4 5" RUNTIMES="springboot" benchmark/run/f3_rerun.sh
#
set -euo pipefail

# ----------------------------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------------------------
export AWS_PROFILE="${AWS_PROFILE:-pessoal}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_EXPECTED="${EXPECTED_AWS_ACCOUNT:-}"

F3_BASELINE_RATE="${F3_BASELINE_RATE:-48}"
F3_PEAK_RATE="${F3_PEAK_RATE:-240}"
F3_RECOVERY_RATE="${F3_RECOVERY_RATE:-48}"

F3_BASELINE_DURATION="${F3_BASELINE_DURATION:-5m}"
F3_RAMP_UP_DURATION="${F3_RAMP_UP_DURATION:-2m}"
F3_PEAK_DURATION="${F3_PEAK_DURATION:-10m}"
F3_RECOVERY_RAMP_DURATION="${F3_RECOVERY_RAMP_DURATION:-2m}"
F3_RECOVERY_DURATION="${F3_RECOVERY_DURATION:-5m}"
F3_RAMP_DOWN_DURATION="${F3_RAMP_DOWN_DURATION:-1m}"

# Segundos correspondentes (para meta.json + volume teórico). Mantenha em sincronia com o acima.
BASELINE_S="${BASELINE_S:-300}"
RAMP_UP_S="${RAMP_UP_S:-120}"
PEAK_S="${PEAK_S:-600}"
RECOVERY_RAMP_S="${RECOVERY_RAMP_S:-120}"
RECOVERY_S="${RECOVERY_S:-300}"
RAMP_DOWN_S="${RAMP_DOWN_S:-60}"

# VUs: a coleta de julho não passou estes — usou os defaults do scenario (1500 / 3000).
PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS:-1500}"
MAX_VUS="${MAX_VUS:-3000}"

ROUNDS="${ROUNDS:-1 2 3 4 5}"
RUNTIMES="${RUNTIMES:-springboot quarkus-jvm quarkus-native}"

# runtime -> "task_definition|health_path"
declare -A RUNTIME_CFG=(
	[springboot]="order-service-springboot:12|/actuator/health"
	[quarkus-jvm]="order-service-quarkus-jvm:10|/q/health"
	[quarkus-native]="order-service-quarkus-native:9|/q/health"
)
# Imagens esperadas (comparabilidade com a coleta de F1/F2/F3 de julho).
declare -A RUNTIME_IMAGE_TAG=(
	[springboot]="latest"                 # MUTÁVEL — preflight só avisa
	[quarkus-jvm]="20260616-160138"       # imutável
	[quarkus-native]="20260616-160138"    # imutável
)

CLUSTER="${CLUSTER:-order-service-cluster}"
FARGATE_SG_NAME="${FARGATE_SG_NAME:-order-service-fargate-sg}"
RDS_INSTANCE_ID="${RDS_INSTANCE_ID:-order-service-postgres}"
SUBNET="${SUBNET:-}"
SG="${SG:-}"
AWS_ACCOUNT_ACTUAL=""
CONTAINER_PORT="${CONTAINER_PORT:-8081}"

DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-orderdb}"
DB_USER="${DB_USER:-orderuser}"
DB_PASSWORD="${DB_PASSWORD:-}"

RUNNER_IP="${RUNNER_IP:-}"
RUNNER_USER="${RUNNER_USER:-ec2-user}"
RUNNER_KEY="${RUNNER_KEY:-$HOME/.ssh/tcc-k6-runner-key.pem}"
REMOTE_BENCH_DIR="${REMOTE_BENCH_DIR:-\$HOME/ecommerce-tcc/benchmark}"
REMOTE_K6="${REMOTE_K6:-\$HOME/.local/bin/k6}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCENARIO_FILE="benchmark/scenarios/f3_black_friday_controlled.js"   # relativo ao REPO_ROOT (local)
REMOTE_SCENARIO="scenarios/f3_black_friday_controlled.js"           # relativo ao REMOTE_BENCH_DIR (runner)
RUNNER_SCRIPT_REL="benchmark/run/f3_rerun.sh"
OUT_DIR="$REPO_ROOT/analysis/fargate/fase3-f3-rerun"
OLD_DIR="$REPO_ROOT/analysis/fargate/fase3"

DRY_RUN="${DRY_RUN:-0}"

# Integral da curva ramping-arrival-rate (startRate = baseline), interpolação linear:
#   baseline·B  +  (baseline+peak)/2·RU  +  peak·P  +  (peak+recov)/2·RR  +  recov·R  +  recov/2·RD
THEORETICAL_ITERS=$(python3 -c "
b=$F3_BASELINE_RATE; p=$F3_PEAK_RATE; r=$F3_RECOVERY_RATE
print(round(b*$BASELINE_S + (b+p)/2*$RAMP_UP_S + p*$PEAK_S + (p+r)/2*$RECOVERY_RAMP_S + r*$RECOVERY_S + r/2*$RAMP_DOWN_S))
")
TOTAL_S=$(( BASELINE_S + RAMP_UP_S + PEAK_S + RECOVERY_RAMP_S + RECOVERY_S + RAMP_DOWN_S ))

log()  { echo "[$(date -u +%H:%M:%SZ)] $*" >&2; }
die()  { echo "ABORT: $*" >&2; exit 1; }

SSH_OPTS=(-i "$RUNNER_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10
	-o ServerAliveInterval=60 -o ServerAliveCountMax=15)

# ----------------------------------------------------------------------------------------------
# Preflight — NÃO cria nada.
# ----------------------------------------------------------------------------------------------
extract_db_password() {
	[[ -n "$DB_PASSWORD" ]] && return 0
	DB_PASSWORD="${PGPASSWORD:-}"
	[[ -n "$DB_PASSWORD" ]] && return 0
	local td="${RUNTIME_CFG[springboot]%%|*}"
	DB_PASSWORD="$(aws ecs describe-task-definition --task-definition "$td" \
		--query "taskDefinition.containerDefinitions[0].environment[?name=='SPRING_R2DBC_PASSWORD'].value | [0]" \
		--output text 2>/dev/null || true)"
	[[ -n "$DB_PASSWORD" && "$DB_PASSWORD" != "None" ]] \
		|| die "não consegui obter a senha do banco (defina DB_PASSWORD ou PGPASSWORD)"
}

preflight() {
	log "preflight: identidade AWS"
	local acct
	acct="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
	[[ -n "$acct" ]] || die "aws sts get-caller-identity falhou (profile=$AWS_PROFILE)"
	if [[ -n "$AWS_ACCOUNT_EXPECTED" && "$acct" != "$AWS_ACCOUNT_EXPECTED" ]]; then
		die "conta AWS = '$acct', esperado EXPECTED_AWS_ACCOUNT='$AWS_ACCOUNT_EXPECTED'"
	fi
	AWS_ACCOUNT_ACTUAL="$acct"
	log "  conta=$acct  profile=$AWS_PROFILE  região=$AWS_REGION"
	[[ "$AWS_REGION" == "us-east-1" ]] || die "região = '$AWS_REGION', esperado us-east-1"

	log "preflight: cluster ECS $CLUSTER"
	local cstatus
	cstatus="$(aws ecs describe-clusters --clusters "$CLUSTER" \
		--query 'clusters[0].status' --output text 2>/dev/null || true)"
	[[ "$cstatus" == "ACTIVE" ]] || die "cluster $CLUSTER não está ACTIVE (status=$cstatus)"

	# Container Insights precisa estar ligado — é a fonte da métrica de CPU/mem a 1 min.
	local ci
	ci="$(aws ecs describe-clusters --clusters "$CLUSTER" --include SETTINGS \
		--query "clusters[0].settings[?name=='containerInsights'].value | [0]" --output text 2>/dev/null || true)"
	[[ "$ci" == "enabled" || "$ci" == "enhanced" ]] \
		|| die "containerInsights='$ci' no cluster $CLUSTER — sem isso não há métrica de CPU/mem a 1 min"
	log "  containerInsights=$ci"

	log "preflight: rede Fargate (SG '$FARGATE_SG_NAME')"
	if [[ -z "$SG" ]]; then
		SG="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$FARGATE_SG_NAME" \
			--query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
	fi
	[[ -n "$SG" && "$SG" != "None" ]] || die "não achei o SG Fargate '$FARGATE_SG_NAME' (passe SG=<id>)"
	local sg_vpc
	sg_vpc="$(aws ec2 describe-security-groups --group-ids "$SG" \
		--query 'SecurityGroups[0].VpcId' --output text 2>/dev/null || true)"
	if [[ -z "$SUBNET" ]]; then
		SUBNET="$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$sg_vpc" "Name=map-public-ip-on-launch,Values=true" \
			--query 'Subnets[0].SubnetId' --output text 2>/dev/null || true)"
		[[ -z "$SUBNET" || "$SUBNET" == "None" ]] && SUBNET="$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$sg_vpc" \
			--query 'Subnets[0].SubnetId' --output text 2>/dev/null || true)"
	fi
	[[ -n "$SUBNET" && "$SUBNET" != "None" ]] || die "não achei subnet na VPC $sg_vpc (passe SUBNET=<id>)"
	log "  SG=$SG  SUBNET=$SUBNET  VPC=$sg_vpc"

	log "preflight: task definitions + imagens"
	local rt td tag want_tag got_img got_digest
	for rt in $RUNTIMES; do
		[[ -n "${RUNTIME_CFG[$rt]:-}" ]] || die "runtime desconhecido: $rt"
		td="${RUNTIME_CFG[$rt]%%|*}"
		got_img="$(aws ecs describe-task-definition --task-definition "$td" \
			--query 'taskDefinition.containerDefinitions[0].image' --output text 2>/dev/null || true)"
		[[ -n "$got_img" && "$got_img" != "None" ]] || die "task def $td não existe / sem imagem"
		tag="${got_img##*:}"
		want_tag="${RUNTIME_IMAGE_TAG[$rt]}"
		got_digest="$(aws ecr describe-images --repository-name "order-service-$rt" \
			--image-ids "imageTag=$tag" \
			--query 'imageDetails[0].imageDigest' --output text 2>/dev/null || true)"
		log "  $rt: $td -> $got_img  (digest ${got_digest:-?})"
		[[ "$tag" == "$want_tag" ]] \
			|| die "$rt: task def aponta para tag '$tag', esperado '$want_tag' — dados não comparáveis"
		if [[ "$tag" == "latest" ]]; then
			log "  AVISO: $rt usa tag MUTÁVEL ':latest'. Confirme que nenhum build novo foi publicado"
			log "         desde a coleta de julho. Digest atual: ${got_digest:-?}"
		fi
	done

	log "preflight: RDS $RDS_INSTANCE_ID"
	local dbstatus dbendpoint
	read -r dbstatus dbendpoint < <(aws rds describe-db-instances --db-instance-identifier "$RDS_INSTANCE_ID" \
		--query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address]' --output text 2>/dev/null || echo "missing -")
	[[ "$dbstatus" == "available" ]] || die "RDS $RDS_INSTANCE_ID não está 'available' (status=$dbstatus)"
	[[ -n "$DB_HOST" ]] || DB_HOST="$dbendpoint"
	[[ -n "$DB_HOST" && "$DB_HOST" != "None" ]] || die "não resolvi o endpoint do RDS"
	log "  endpoint=$DB_HOST  status=$dbstatus"
	extract_db_password
	PGPASSWORD="$DB_PASSWORD" PGCONNECT_TIMEOUT=10 psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
		--set=sslmode=require -tAc 'select 1' >/dev/null 2>&1 \
		|| die "psql não conecta no RDS. Libere o IP atual no SG do RDS: $(curl -s --max-time 5 https://checkip.amazonaws.com || echo '?')"

	log "preflight: runner k6"
	[[ -n "$RUNNER_IP" ]] || die "RUNNER_IP não definido. Suba/ligue o runner e passe RUNNER_IP=<ip>."
	[[ -f "$RUNNER_KEY" ]] || die "chave SSH não encontrada: $RUNNER_KEY"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "true" 2>/dev/null \
		|| die "SSH falhou para $RUNNER_USER@$RUNNER_IP (SG do runner precisa liberar a porta 22 p/ o IP atual)"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "$REMOTE_K6 version" >/dev/null 2>&1 \
		|| die "k6 não encontrado no runner em $REMOTE_K6"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" \
		"test -f $REMOTE_BENCH_DIR/$REMOTE_SCENARIO && test -f $REMOTE_BENCH_DIR/scenarios/f2_high_load.js && test -f $REMOTE_BENCH_DIR/lib/workload.js" \
		|| die "runner não tem $REMOTE_SCENARIO (+ f2_high_load.js + lib/) — sincronize scenarios/ e lib/ primeiro"

	# O scenario no runner precisa ser a versão com o guard (exige as 3 taxas).
	local remote_md5 local_md5
	remote_md5="$(ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "md5sum $REMOTE_BENCH_DIR/$REMOTE_SCENARIO | cut -d' ' -f1" 2>/dev/null || echo x)"
	local_md5="$(md5sum "$REPO_ROOT/$SCENARIO_FILE" | cut -d' ' -f1)"
	[[ "$remote_md5" == "$local_md5" ]] \
		|| die "scenario no runner ($remote_md5) != local ($local_md5) — re-sincronize scenarios/f3_black_friday_controlled.js"

	if command -v k6 >/dev/null 2>&1; then
		log "preflight: scenario k6 exige as taxas (regressão do guard)"
		( cd "$REPO_ROOT/benchmark" && ! k6 inspect "scenarios/f3_black_friday_controlled.js" >/dev/null 2>&1 ) \
			|| die "$SCENARIO_FILE não falha sem as taxas — o guard não está aplicado"
		( cd "$REPO_ROOT/benchmark" && k6 inspect \
			-e F3_BASELINE_RATE="$F3_BASELINE_RATE" -e F3_PEAK_RATE="$F3_PEAK_RATE" -e F3_RECOVERY_RATE="$F3_RECOVERY_RATE" \
			"scenarios/f3_black_friday_controlled.js" >/dev/null 2>&1 ) \
			|| die "k6 inspect falha MESMO com as taxas — scenario quebrado"
	else
		log "AVISO: k6 não instalado localmente — pulei a checagem do guard"
	fi

	log "preflight: espaço em disco no runner (/var/tmp p/ raw JSON)"
	local free_kb
	free_kb="$(ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "df -Pk /var/tmp | awk 'NR==2{print \$4}'" 2>/dev/null || echo 0)"
	[[ "$free_kb" -ge 5242880 ]] \
		|| die "runner /var/tmp tem só $((free_kb/1024))MB livres — precisa de >=5GB p/ o raw JSON gzip do F3"
	log "  /var/tmp livre: $((free_kb/1024/1024))GB"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "command -v gzip >/dev/null && python3 -c 'import gzip'" \
		|| die "runner sem gzip / módulo gzip do python"

	mkdir -p "$OUT_DIR"
	[[ -d "$OLD_DIR" ]] && log "OK: coleta antiga preservada em $OLD_DIR (não será tocada)"
	log "preflight OK."
	log "  taxas: baseline=$F3_BASELINE_RATE  pico=$F3_PEAK_RATE  recuperação=$F3_RECOVERY_RATE iter/s"
	log "  fases: ${F3_BASELINE_DURATION}/${F3_RAMP_UP_DURATION}/${F3_PEAK_DURATION}/${F3_RECOVERY_RAMP_DURATION}/${F3_RECOVERY_DURATION}/${F3_RAMP_DOWN_DURATION}  (total ${TOTAL_S}s)"
	log "  volume teórico: ~${THEORETICAL_ITERS} iterações/rodada  (julho observou 208.799)"
}

# ----------------------------------------------------------------------------------------------
# Helpers de execução
# ----------------------------------------------------------------------------------------------
git_blob()  { ( cd "$REPO_ROOT" && git hash-object "$1" 2>/dev/null || echo "unknown" ); }
git_head()  { ( cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown" ); }
git_dirty() { ( cd "$REPO_ROOT" && git diff --quiet -- "$1" 2>/dev/null && echo false || echo true ); }

task_family_arns() {
	aws ecs list-tasks --cluster "$CLUSTER" --family "$1" --desired-status RUNNING \
		--query 'taskArns' --output text 2>/dev/null || true
}

get_task_ip() {
	local arn="$1" eni ip
	eni="$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$arn" --output json 2>/dev/null \
		| python3 -c 'import sys,json;d=json.load(sys.stdin);ds=d["tasks"][0]["attachments"][0]["details"];print(next(x["value"] for x in ds if x["name"]=="networkInterfaceId"))' 2>/dev/null || true)"
	[[ -n "$eni" ]] || return 1
	ip="$(aws ec2 describe-network-interfaces --network-interface-ids "$eni" \
		--query 'NetworkInterfaces[0].Association.PublicIp' --output text 2>/dev/null || true)"
	[[ -n "$ip" && "$ip" != "None" ]] || return 1
	echo "$ip"
}

fresh_task() {
	local task_def="$1" health_path="$2" family="${1%%:*}" old arn ip status i
	for old in $(task_family_arns "$family"); do
		log "  stop-task antiga: $old"
		aws ecs stop-task --cluster "$CLUSTER" --task "$old" --query 'task.taskArn' --output text >/dev/null 2>&1 || true
	done
	sleep 8
	arn="$(aws ecs run-task --cluster "$CLUSTER" --task-definition "$task_def" --count 1 \
		--launch-type FARGATE --started-by "f3_rerun" \
		--network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
		--query 'tasks[0].taskArn' --output text 2>/dev/null)"
	[[ -n "$arn" && "$arn" != "None" ]] || die "run-task falhou para $task_def"
	log "  run-task: $arn"
	sleep 20
	aws ecs wait tasks-running --cluster "$CLUSTER" --tasks "$arn" 2>/dev/null || die "task não ficou RUNNING: $arn"
	ip="$(get_task_ip "$arn")" || die "não consegui o IP público da task $arn"
	log "  IP: $ip — aguardando health em $health_path"
	set +e
	for i in $(seq 1 30); do
		status="$(curl -s -m 5 "http://$ip:$CONTAINER_PORT$health_path" | tr -d ' \n')"
		case "$status" in
			*'"status":"UP"'*|*'"status":UP'*) set -e; log "  health UP (tentativa $i)"; echo "$ip"; return 0 ;;
		esac
		sleep 5
	done
	set -e
	die "health não ficou UP após 30 tentativas ($task_def)"
}

truncate_db() {
	log "  TRUNCATE order_status_history / order_items / orders"
	PGPASSWORD="$DB_PASSWORD" PGCONNECT_TIMEOUT=10 psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
		--set=sslmode=require -v ON_ERROR_STOP=1 \
		-c "TRUNCATE TABLE order_status_history, order_items, orders;" >/dev/null
}

# $1 runtime $2 round $3 start_utc $4 end_utc $5 task_def $6 image_digest $7 k6ver $8 k6_rc
#   $9 load_start_utc  $10 load_end_utc
write_meta() {
	local rt="$1" r="$2" start="$3" end="$4" td="$5" digest="$6" k6ver="$7" k6rc="${8:-unknown}"
	local load_start="${9:-}" load_end="${10:-}"
	GIT_HEAD="$(git_head)" GIT_BLOB_SCEN="$(git_blob "$SCENARIO_FILE")" \
	GIT_DIRTY_SCEN="$(git_dirty "$SCENARIO_FILE")" GIT_BLOB_RUN="$(git_blob "$RUNNER_SCRIPT_REL")" \
	python3 - "$OUT_DIR/f3-$rt-r$r-meta.json" <<PY
import json, os, sys, datetime as dt

load_start = "$load_start" or None
phase_defs = [
    ("baseline",      0,                    $BASELINE_S,      $F3_BASELINE_RATE, "step"),
    ("ramp_up",       $BASELINE_S,          $RAMP_UP_S,       $F3_PEAK_RATE,     "linear"),
    ("peak",          $BASELINE_S+$RAMP_UP_S, $PEAK_S,        $F3_PEAK_RATE,     "step"),
    ("recovery_ramp", $BASELINE_S+$RAMP_UP_S+$PEAK_S, $RECOVERY_RAMP_S, $F3_RECOVERY_RATE, "linear"),
    ("recovery",      $BASELINE_S+$RAMP_UP_S+$PEAK_S+$RECOVERY_RAMP_S, $RECOVERY_S, $F3_RECOVERY_RATE, "step"),
    ("ramp_down",     $BASELINE_S+$RAMP_UP_S+$PEAK_S+$RECOVERY_RAMP_S+$RECOVERY_S, $RAMP_DOWN_S, 0, "linear"),
]

def iso(base, offs):
    if base is None:
        return None
    t = dt.datetime.fromisoformat(base.replace("Z", "+00:00")) + dt.timedelta(seconds=offs)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

phases = []
for name, off, dur, target, trans in phase_defs:
    phases.append({
        "name": name, "offset_s": off, "duration_s": dur,
        "target_iter_per_s": target, "transition": trans,
        "start_utc": iso(load_start, off), "end_utc": iso(load_start, off + dur),
    })

meta = {
    "scenario": "f3_black_friday_controlled",
    "runtime": "$rt",
    "round": int("$r"),
    "rates_iter_per_s": {"baseline": $F3_BASELINE_RATE, "peak": $F3_PEAK_RATE, "recovery": $F3_RECOVERY_RATE},
    "phase_durations_k6": {
        "baseline": "$F3_BASELINE_DURATION", "ramp_up": "$F3_RAMP_UP_DURATION",
        "peak": "$F3_PEAK_DURATION", "recovery_ramp": "$F3_RECOVERY_RAMP_DURATION",
        "recovery": "$F3_RECOVERY_DURATION", "ramp_down": "$F3_RAMP_DOWN_DURATION",
    },
    "phases": phases,
    "theoretical_iterations": int("$THEORETICAL_ITERS"),
    "total_duration_s": int("$TOTAL_S"),
    "k6_invoke_utc": "$start",
    "k6_return_utc": "$end",
    "load_start_utc": load_start,
    "load_end_utc": "$load_end" or None,
    "k6_version": "$k6ver",
    "k6_exit_code": "$k6rc",
    "runner_ip": "$RUNNER_IP",
    "task_definition": "$td",
    "image_digest": "$digest",
    "aws_account": "${AWS_ACCOUNT_ACTUAL:-}",
    "aws_region": "$AWS_REGION",
    "rds_instance": "$RDS_INSTANCE_ID",
    "pre_allocated_vus": int("$PRE_ALLOCATED_VUS"),
    "max_vus": int("$MAX_VUS"),
    "script": {
        "path": "$SCENARIO_FILE",
        "git_commit": os.environ["GIT_HEAD"],
        "git_blob_sha": os.environ["GIT_BLOB_SCEN"],
        "git_dirty": os.environ["GIT_DIRTY_SCEN"] == "true",
    },
    "runner_script": {"path": "$RUNNER_SCRIPT_REL", "git_blob_sha": os.environ["GIT_BLOB_RUN"]},
}
json.dump(meta, open(sys.argv[1], "w"), indent=2)
print("  meta -> " + sys.argv[1], file=sys.stderr)
PY
}

run_k6() {
	local rt="$1" r="$2" ip="$3" td="$4"
	local summary_local="$OUT_DIR/f3-$rt-r$r-summary.json"
	local latency_local="$OUT_DIR/f3-$rt-r$r-latency.json"
	if [[ -f "$summary_local" && -f "$latency_local" ]]; then
		log "  checkpoint: $rt r$r já existe — pulando"
		return 0
	fi
	local base="http://$ip:$CONTAINER_PORT"
	local rid="f3-$rt-r$r"
	local k6ver start end digest
	k6ver="$(ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "$REMOTE_K6 version" 2>/dev/null | head -1 || echo unknown)"
	digest="$(aws ecr describe-images --repository-name "order-service-$rt" \
		--image-ids "imageTag=${RUNTIME_IMAGE_TAG[$rt]}" \
		--query 'imageDetails[0].imageDigest' --output text 2>/dev/null || echo unknown)"

	start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	log "  k6 run (F3 $F3_BASELINE_RATE/$F3_PEAK_RATE/$F3_RECOVERY_RATE) -> $base  (~${TOTAL_S}s)"
	# teto de tempo: a corrida k6 dura ~1500s; 2700s cobre setup + extração + folga.
	# Sem isto, um SSH meio-aberto (ex.: laptop do operador dorme) trava o script pra sempre.
	local k6_timeout="${K6_SSH_TIMEOUT:-2700}"
	timeout --signal=INT "$k6_timeout" \
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" bash -s <<REMOTE
set -uo pipefail
cd $REMOTE_BENCH_DIR
export BASE_URL='$base'
export F3_BASELINE_RATE='$F3_BASELINE_RATE' F3_PEAK_RATE='$F3_PEAK_RATE' F3_RECOVERY_RATE='$F3_RECOVERY_RATE'
export F3_BASELINE_DURATION='$F3_BASELINE_DURATION' F3_RAMP_UP_DURATION='$F3_RAMP_UP_DURATION'
export F3_PEAK_DURATION='$F3_PEAK_DURATION' F3_RECOVERY_RAMP_DURATION='$F3_RECOVERY_RAMP_DURATION'
export F3_RECOVERY_DURATION='$F3_RECOVERY_DURATION' F3_RAMP_DOWN_DURATION='$F3_RAMP_DOWN_DURATION'
export PRE_ALLOCATED_VUS='$PRE_ALLOCATED_VUS' MAX_VUS='$MAX_VUS'
# raw JSON vai para /var/tmp (xfs, disco EBS) — /tmp no runner é tmpfs (RAM, 3.8G) e o
# raw do F3 (~234k http_reqs) não cabe. gzip corta ~10x.
$REMOTE_K6 run \
  --out json=/var/tmp/$rid-raw.json.gz \
  --summary-export=/tmp/$rid-summary.json \
  scenarios/f3_black_friday_controlled.js
k6_rc=\$?
echo "\$k6_rc" > /tmp/$rid-k6rc.txt
test -s /tmp/$rid-summary.json || { echo "k6 não gerou summary (rc=\$k6_rc)" >&2; exit 1; }
python3 - <<'PYEXTRACT'
import json, gzip
lat=[]
load_t=[]
all_t=[]
setup_n=0
with gzip.open('/var/tmp/$rid-raw.json.gz','rt') as f:
    for line in f:
        try: o=json.loads(line)
        except Exception: continue
        if o.get('type')!='Point': continue
        if o.get('metric')!='http_req_duration': continue
        d=o.get('data',{})
        tags=d.get('tags',{}) or {}
        ph=tags.get('phase')
        t=d.get('time')
        lat.append(d['value'])
        if t: all_t.append(t)
        if ph in ('load','auxiliary') and t:
            load_t.append(t)
        elif ph=='setup':
            setup_n+=1
json.dump(lat, open('/tmp/$rid-latency.json','w'))
timing={'load_points':len(load_t),'setup_req_points':setup_n,'http_req_points':len(lat)}
if load_t:
    load_t.sort()
    timing['load_start_utc']=load_t[0]
    timing['load_end_utc']=load_t[-1]
    timing['load_start_source']='phase_tag'
elif all_t:
    # fallback: sem tags de fase legíveis — pula os ~120 requests de setup (readPoolSize)
    all_t.sort()
    skip=setup_n if setup_n else min(120,len(all_t)-1)
    timing['load_start_utc']=all_t[skip]
    timing['load_end_utc']=all_t[-1]
    timing['load_start_source']='fallback_skip_%d'%skip
json.dump(timing, open('/tmp/$rid-timing.json','w'))
print('latency points:', len(lat), ' load window:', timing.get('load_start_utc'), '->', timing.get('load_end_utc'), '(', timing.get('load_start_source'), ')')
PYEXTRACT
rm -f /var/tmp/$rid-raw.json.gz
REMOTE
	end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	local k6rc
	k6rc="$(ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "cat /tmp/$rid-k6rc.txt 2>/dev/null" || echo unknown)"
	[[ "$k6rc" == "0" ]] || log "  AVISO: k6 saiu com rc=$k6rc (threshold estourado — dado coletado; registrado no meta)"

	scp "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP:/tmp/$rid-summary.json" "$summary_local"
	scp "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP:/tmp/$rid-latency.json" "$latency_local"
	local timing_local="$OUT_DIR/f3-$rt-r$r-timing.json"
	scp "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP:/tmp/$rid-timing.json" "$timing_local" 2>/dev/null || echo '{}' > "$timing_local"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "rm -f /tmp/$rid-summary.json /tmp/$rid-latency.json /tmp/$rid-timing.json /tmp/$rid-k6rc.txt" || true

	local load_start load_end
	load_start="$(python3 -c "import json;print(json.load(open('$timing_local')).get('load_start_utc',''))" 2>/dev/null || echo '')"
	load_end="$(python3 -c "import json;print(json.load(open('$timing_local')).get('load_end_utc',''))" 2>/dev/null || echo '')"
	write_meta "$rt" "$r" "$start" "$end" "$td" "$digest" "$k6ver" "$k6rc" "$load_start" "$load_end"
	log "  OK: $summary_local  (load_start=$load_start)"
}

sanity_check() {
	log "=== sanidade (iterations vs teórico ${THEORETICAL_ITERS}, dropped~0, 0 falha) ==="
	python3 - "$OUT_DIR" "$THEORETICAL_ITERS" <<'PY'
import json, glob, os, sys
outdir, theo = sys.argv[1], int(sys.argv[2])
rows = sorted(glob.glob(os.path.join(outdir, "f3-*-summary.json")))
print(f"{'round':28} {'iters':>9} {'Δteo':>7} {'dropped':>8} {'fail_rate':>10} {'dur_s':>7}  load_window")
bad = 0
for sp in rows:
    d = json.load(open(sp)); m = d["metrics"]
    it = m.get("iterations", {}).get("count", 0)
    di = m.get("dropped_iterations", {}).get("count", 0)
    hr = m.get("http_reqs", {})
    fr = m.get("http_req_failed", {}).get("value", m.get("http_req_failed", {}).get("rate", 0)) or 0
    dur = hr.get("count", 0) / hr.get("rate", 1) if hr.get("rate") else 0
    base = sp.replace("-summary.json", "")
    mp = base + "-meta.json"
    lw = ""
    if os.path.exists(mp):
        mm = json.load(open(mp))
        lw = f"{mm.get('load_start_utc','?')} .. {mm.get('load_end_utc','?')}"
    tag = os.path.basename(base)
    flag = ""
    if abs(it - theo) > theo * 0.01: flag += " ITERS!"
    if di > theo * 0.005: flag += " DROPPED!"
    if fr > 0.005: flag += " FAIL!"
    if flag: bad += 1
    print(f"{tag:28} {it:>9} {it-theo:>7} {di:>8} {fr:>10.5f} {dur:>7.0f}  {lw}{flag}")
print(f"\n{'OK — todas as rodadas dentro do esperado' if bad==0 else f'ATENCAO: {bad} rodada(s) fora do esperado'}")
PY
}

# ----------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------
preflight
if [[ "$DRY_RUN" == "1" ]]; then
	log "DRY_RUN=1 — preflight apenas, encerrando."
	exit 0
fi

for rt in $RUNTIMES; do
	cfg="${RUNTIME_CFG[$rt]}"
	td="${cfg%%|*}"
	health="${cfg##*|}"
	for r in $ROUNDS; do
		if [[ -f "$OUT_DIR/f3-$rt-r$r-summary.json" && -f "$OUT_DIR/f3-$rt-r$r-latency.json" ]]; then
			log "checkpoint: $rt r$r já existe — pulando"
			continue
		fi
		log "=== $rt rodada $r ==="
		ip="$(fresh_task "$td" "$health")"
		truncate_db
		run_k6 "$rt" "$r" "$ip" "$td"
	done
	log "parando task final de $rt"
	for old in $(task_family_arns "${td%%:*}"); do
		aws ecs stop-task --cluster "$CLUSTER" --task "$old" >/dev/null 2>&1 || true
	done
done

sanity_check
log "F3 re-run concluído. Saídas em $OUT_DIR"
