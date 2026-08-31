#!/usr/bin/env bash
#
# f1_rerun.sh — Re-coleta do cenário F1 (Fargate, fase3) na taxa CONFIRMADA F1_RATE=48 iter/s.
#
# Motivo: a coleta original de F1 (analysis/fargate/fase3/f1-*) rodou no antigo default
# silencioso do script (30 iter/s), não na taxa pretendida (48). F2 e F3 rodaram corretos
# (96 / 240) e NÃO são tocados aqui. Ver 08-known-problems.md e o commit que torna F1_RATE
# obrigatória em benchmark/scenarios/f1_low_load.js.
#
# Metodologia: idêntica ao bloco_fargate.sh original (porção F1). Para cada runtime × rodada:
#   stop-task -> run-task (task fresca) -> aguardar health -> TRUNCATE no RDS -> k6 no runner
#   -> extrair latency.json no runner -> scp de volta. Uma task fresca por rodada.
# Únicas diferenças em relação ao original: F1_RATE=48 explícito, script versionado (não /tmp),
# e um {runtime}-r{n}-meta.json por rodada com a proveniência completa da execução.
#
# NÃO cria infraestrutura. O preflight aborta se runner / cluster / task defs / RDS não
# estiverem prontos — restaure o que faltar e rode de novo.
#
# Uso:
#   RUNNER_IP=<ip-do-runner> benchmark/run/f1_rerun.sh
#   RUNNER_IP=<ip> ROUNDS="3 4 5" RUNTIMES="springboot" benchmark/run/f1_rerun.sh   # subconjunto
#   RUNNER_IP=<ip> DRY_RUN=1 benchmark/run/f1_rerun.sh                              # só preflight
#
set -euo pipefail

# ----------------------------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------------------------
export AWS_PROFILE="${AWS_PROFILE:-pessoal}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
# Guarda opcional contra rodar na conta errada. Não versionamos o ID da conta (regra do
# runbook). Defina EXPECTED_AWS_ACCOUNT=<id> no ambiente para ativar a checagem.
AWS_ACCOUNT_EXPECTED="${EXPECTED_AWS_ACCOUNT:-}"

F1_RATE="${F1_RATE:-48}"
F1_START_RATE="${F1_START_RATE:-1}"
F1_RAMP_UP="${F1_RAMP_UP:-2m}"
F1_DURATION="${F1_DURATION:-20m}"
F1_RAMP_DOWN="${F1_RAMP_DOWN:-2m}"
# Segundos correspondentes (para meta.json e volume teórico). Mantenha em sincronia com o acima.
RAMP_UP_S="${RAMP_UP_S:-120}"
HOLD_S="${HOLD_S:-1200}"
RAMP_DOWN_S="${RAMP_DOWN_S:-120}"

PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS:-80}"
MAX_VUS="${MAX_VUS:-200}"

ROUNDS="${ROUNDS:-1 2 3 4 5}"
RUNTIMES="${RUNTIMES:-springboot quarkus-jvm quarkus-native}"

# runtime -> "task_definition|health_path"
declare -A RUNTIME_CFG=(
	[springboot]="order-service-springboot:12|/actuator/health"
	[quarkus-jvm]="order-service-quarkus-jvm:10|/q/health"
	[quarkus-native]="order-service-quarkus-native:9|/q/health"
)
# Imagens esperadas (comparabilidade com F2/F3 já coletados).
declare -A RUNTIME_IMAGE_TAG=(
	[springboot]="latest"                 # MUTÁVEL — preflight só avisa; ver nota no README
	[quarkus-jvm]="20260616-160138"       # imutável
	[quarkus-native]="20260616-160138"    # imutável
)

CLUSTER="${CLUSTER:-order-service-cluster}"
FARGATE_SG_NAME="${FARGATE_SG_NAME:-order-service-fargate-sg}"
RDS_INSTANCE_ID="${RDS_INSTANCE_ID:-order-service-postgres}"
# SUBNET / SG / DB_HOST: resolvidos dinamicamente no preflight se não vierem do ambiente
# (evita versionar IDs de recurso específicos da conta).
SUBNET="${SUBNET:-}"
SG="${SG:-}"
AWS_ACCOUNT_ACTUAL=""
CONTAINER_PORT="${CONTAINER_PORT:-8081}"

DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-orderdb}"
DB_USER="${DB_USER:-orderuser}"
# Senha: nunca versionada. Puxada da task definition em runtime (extract_db_password), ou via
# env DB_PASSWORD / PGPASSWORD.
DB_PASSWORD="${DB_PASSWORD:-}"

RUNNER_IP="${RUNNER_IP:-}"
RUNNER_USER="${RUNNER_USER:-ec2-user}"
RUNNER_KEY="${RUNNER_KEY:-$HOME/.ssh/tcc-k6-runner-key.pem}"
REMOTE_BENCH_DIR="${REMOTE_BENCH_DIR:-\$HOME/ecommerce-tcc/benchmark}"
REMOTE_K6="${REMOTE_K6:-\$HOME/.local/bin/k6}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCENARIO_FILE="benchmark/scenarios/f1_low_load.js"   # caminho relativo ao REPO_ROOT (local)
REMOTE_SCENARIO="scenarios/f1_low_load.js"           # caminho relativo ao REMOTE_BENCH_DIR (runner)
RUNNER_SCRIPT_REL="benchmark/run/f1_rerun.sh"
OUT_DIR="$REPO_ROOT/analysis/fargate/fase3-f1-rerun"
OLD_DIR="$REPO_ROOT/analysis/fargate/fase3"

DRY_RUN="${DRY_RUN:-0}"

THEORETICAL_ITERS=$(( (F1_START_RATE + F1_RATE) * RAMP_UP_S / 2 + F1_RATE * HOLD_S + F1_RATE * RAMP_DOWN_S / 2 ))

log()  { echo "[$(date -u +%H:%M:%SZ)] $*" >&2; }
die()  { echo "ABORT: $*" >&2; exit 1; }

SSH_OPTS=(-i "$RUNNER_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10
	-o ServerAliveInterval=60 -o ServerAliveCountMax=10)

# ----------------------------------------------------------------------------------------------
# Preflight — NÃO cria nada. Aborta se algo estiver faltando.
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
		die "conta AWS = '$acct', esperado EXPECTED_AWS_ACCOUNT='$AWS_ACCOUNT_EXPECTED' (profile=$AWS_PROFILE)"
	fi
	AWS_ACCOUNT_ACTUAL="$acct"
	log "  conta=$acct  profile=$AWS_PROFILE  região=$AWS_REGION"
	[[ "$AWS_REGION" == "us-east-1" ]] || die "região = '$AWS_REGION', esperado us-east-1"

	log "preflight: cluster ECS $CLUSTER"
	local cstatus
	cstatus="$(aws ecs describe-clusters --clusters "$CLUSTER" \
		--query 'clusters[0].status' --output text 2>/dev/null || true)"
	[[ "$cstatus" == "ACTIVE" ]] || die "cluster $CLUSTER não está ACTIVE (status=$cstatus)"

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
		if [[ "$tag" != "$want_tag" ]]; then
			die "$rt: task def aponta para tag '$tag', esperado '$want_tag' — dados não comparáveis com F2/F3"
		fi
		if [[ "$tag" == "latest" ]]; then
			log "  AVISO: $rt usa tag MUTÁVEL ':latest'. Confirme que nenhum build novo foi"
			log "         publicado desde a coleta de F2/F3. Digest atual: ${got_digest:-?}"
		fi
	done

	log "preflight: RDS $RDS_INSTANCE_ID"
	local dbstatus dbendpoint
	read -r dbstatus dbendpoint < <(aws rds describe-db-instances --db-instance-identifier "$RDS_INSTANCE_ID" \
		--query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address]' --output text 2>/dev/null || echo "missing -")
	[[ "$dbstatus" == "available" ]] || die "RDS $RDS_INSTANCE_ID não está 'available' (status=$dbstatus)"
	[[ -n "$DB_HOST" ]] || DB_HOST="$dbendpoint"
	[[ -n "$DB_HOST" && "$DB_HOST" != "None" ]] || die "não resolvi o endpoint do RDS $RDS_INSTANCE_ID"
	log "  endpoint=$DB_HOST  status=$dbstatus"
	extract_db_password
	if ! PGPASSWORD="$DB_PASSWORD" PGCONNECT_TIMEOUT=10 psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
		--set=sslmode=require -tAc 'select 1' >/dev/null 2>&1; then
		die "psql não conecta no RDS. IP público atual precisa estar liberado no SG do RDS. IP: $(curl -s --max-time 5 https://checkip.amazonaws.com || echo '?')"
	fi

	log "preflight: runner k6"
	[[ -n "$RUNNER_IP" ]] || die "RUNNER_IP não definido. Não há runner EC2 no momento (todos terminados). Suba um t3.large com a key '$RUNNER_KEY' e passe RUNNER_IP=<ip>."
	[[ -f "$RUNNER_KEY" ]] || die "chave SSH não encontrada: $RUNNER_KEY"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "true" 2>/dev/null \
		|| die "SSH falhou para $RUNNER_USER@$RUNNER_IP (SG do runner precisa liberar a porta 22 para o IP atual)"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "$REMOTE_K6 version" >/dev/null 2>&1 \
		|| die "k6 não encontrado no runner em $REMOTE_K6"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "test -f $REMOTE_BENCH_DIR/$REMOTE_SCENARIO && test -f $REMOTE_BENCH_DIR/lib/workload.js" \
		|| die "runner não tem $REMOTE_BENCH_DIR/$REMOTE_SCENARIO (+ lib/) — sincronize scenarios/ e lib/ primeiro"

	if command -v k6 >/dev/null 2>&1; then
		log "preflight: script k6 exige F1_RATE (regressão do fix)"
		( cd "$REPO_ROOT/benchmark" && ! k6 inspect "scenarios/f1_low_load.js" >/dev/null 2>&1 ) \
			|| die "$SCENARIO_FILE não está falhando sem F1_RATE — o fix não está aplicado"
	else
		log "AVISO: k6 não instalado localmente — pulei a checagem de regressão do fix F1_RATE"
	fi

	mkdir -p "$OUT_DIR"
	[[ -d "$OLD_DIR" ]] && log "OK: coleta antiga preservada em $OLD_DIR (não será tocada)"
	log "preflight OK. F1_RATE=$F1_RATE  fases=${F1_RAMP_UP}/${F1_DURATION}/${F1_RAMP_DOWN}  volume teórico=~${THEORETICAL_ITERS} iterações/rodada"
}

# ----------------------------------------------------------------------------------------------
# Helpers de execução
# ----------------------------------------------------------------------------------------------
git_blob() { ( cd "$REPO_ROOT" && git hash-object "$1" 2>/dev/null || echo "unknown" ); }
git_head() { ( cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown" ); }
git_dirty() { ( cd "$REPO_ROOT" && git diff --quiet -- "$1" 2>/dev/null && echo false || echo true ); }

task_family_arns() {  # nome da família -> ARNs de tasks RUNNING
	aws ecs list-tasks --cluster "$CLUSTER" --family "$1" --desired-status RUNNING \
		--query 'taskArns' --output text 2>/dev/null || true
}

get_task_ip() {  # $1 = task ARN ; usa python3 (evita JMESPath com backtick)
	local arn="$1" eni ip
	eni="$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$arn" --output json 2>/dev/null \
		| python3 -c 'import sys,json;d=json.load(sys.stdin);ds=d["tasks"][0]["attachments"][0]["details"];print(next(x["value"] for x in ds if x["name"]=="networkInterfaceId"))' 2>/dev/null || true)"
	[[ -n "$eni" ]] || return 1
	ip="$(aws ec2 describe-network-interfaces --network-interface-ids "$eni" \
		--query 'NetworkInterfaces[0].Association.PublicIp' --output text 2>/dev/null || true)"
	[[ -n "$ip" && "$ip" != "None" ]] || return 1
	echo "$ip"
}

fresh_task() {  # $1 = task_def ; $2 = health_path ; ecoa o IP no stdout, diagnósticos no stderr
	local task_def="$1" health_path="$2" family="${1%%:*}" old arn ip status i
	for old in $(task_family_arns "$family"); do
		log "  stop-task antiga: $old"
		aws ecs stop-task --cluster "$CLUSTER" --task "$old" --query 'task.taskArn' --output text >/dev/null 2>&1 || true
	done
	sleep 8
	arn="$(aws ecs run-task --cluster "$CLUSTER" --task-definition "$task_def" --count 1 \
		--launch-type FARGATE --started-by "f1_rerun" \
		--network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
		--query 'tasks[0].taskArn' --output text 2>/dev/null)"
	[[ -n "$arn" && "$arn" != "None" ]] || die "run-task falhou para $task_def"
	log "  run-task: $arn"
	sleep 20
	aws ecs wait tasks-running --cluster "$CLUSTER" --tasks "$arn" 2>/dev/null || die "task não ficou RUNNING: $arn"
	ip="$(get_task_ip "$arn")" || die "não consegui o IP público da task $arn"
	log "  IP: $ip — aguardando health em $health_path"
	set +e
	for i in $(seq 1 24); do
		status="$(curl -s -m 5 "http://$ip:$CONTAINER_PORT$health_path" | tr -d ' \n')"
		case "$status" in
			*'"status":"UP"'*|*'"status":UP'*) set -e; log "  health UP (tentativa $i)"; echo "$ip"; return 0 ;;
		esac
		sleep 5
	done
	set -e
	die "health não ficou UP após 24 tentativas ($task_def)"
}

truncate_db() {
	log "  TRUNCATE orders / order_items / order_status_history"
	PGPASSWORD="$DB_PASSWORD" PGCONNECT_TIMEOUT=10 psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
		--set=sslmode=require -v ON_ERROR_STOP=1 \
		-c "TRUNCATE TABLE order_status_history, order_items, orders;" >/dev/null
}

write_meta() {  # $1 runtime $2 round $3 start_utc $4 end_utc $5 task_def $6 image_digest $7 k6ver $8 k6_rc
	local rt="$1" r="$2" start="$3" end="$4" td="$5" digest="$6" k6ver="$7" k6rc="${8:-unknown}"
	python3 - "$OUT_DIR/f1-$rt-r$r-meta.json" <<PY
import json, sys
meta = {
    "scenario": "f1_low_load",
    "runtime": "$rt",
    "round": int("$r"),
    "f1_rate_iter_per_s": int("$F1_RATE"),
    "start_rate_iter_per_s": int("$F1_START_RATE"),
    "phases": [
        {"name": "ramp_up",   "target_iter_per_s": int("$F1_RATE"), "duration_s": int("$RAMP_UP_S"),   "transition": "linear"},
        {"name": "hold",      "target_iter_per_s": int("$F1_RATE"), "duration_s": int("$HOLD_S"),      "transition": "step"},
        {"name": "ramp_down", "target_iter_per_s": 0,               "duration_s": int("$RAMP_DOWN_S"), "transition": "linear"},
    ],
    "phase_durations_k6": {"ramp_up": "$F1_RAMP_UP", "hold": "$F1_DURATION", "ramp_down": "$F1_RAMP_DOWN"},
    "theoretical_iterations": int("$THEORETICAL_ITERS"),
    "start_utc": "$start",
    "end_utc": "$end",
    "k6_version": "$k6ver",
    "k6_exit_code": "$k6rc",
    "runner_ip": "$RUNNER_IP",
    "task_definition": "$td",
    "image_digest": "$digest",
    "aws_account": "${AWS_ACCOUNT_ACTUAL:-}",
    "aws_region": "$AWS_REGION",
    "rds_instance": "$RDS_INSTANCE_ID",
    "script": {
        "path": "$SCENARIO_FILE",
        "git_commit": "$(git_head)",
        "git_blob_sha": "$(git_blob "$SCENARIO_FILE")",
        "git_dirty": ("$(git_dirty "$SCENARIO_FILE")" == "true"),
    },
    "runner_script": {
        "path": "$RUNNER_SCRIPT_REL",
        "git_blob_sha": "$(git_blob "$RUNNER_SCRIPT_REL")",
    },
}
json.dump(meta, open(sys.argv[1], "w"), indent=2)
print("  meta -> " + sys.argv[1], file=sys.stderr)
PY
}

run_k6() {  # $1 runtime $2 round $3 ip $4 task_def
	local rt="$1" r="$2" ip="$3" td="$4"
	local summary_local="$OUT_DIR/f1-$rt-r$r-summary.json"
	local latency_local="$OUT_DIR/f1-$rt-r$r-latency.json"
	if [[ -f "$summary_local" && -f "$latency_local" ]]; then
		log "  checkpoint: $rt r$r já existe — pulando"
		return 0
	fi
	local base="http://$ip:$CONTAINER_PORT"
	local rid="f1-$rt-r$r"
	local k6ver start end digest
	k6ver="$(ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "$REMOTE_K6 version" 2>/dev/null | head -1 || echo unknown)"
	digest="$(aws ecr describe-images --repository-name "order-service-$rt" \
		--image-ids "imageTag=${RUNTIME_IMAGE_TAG[$rt]}" \
		--query 'imageDetails[0].imageDigest' --output text 2>/dev/null || echo unknown)"

	start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	log "  k6 run (F1_RATE=$F1_RATE) -> $base"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" bash -s <<REMOTE
set -uo pipefail
cd $REMOTE_BENCH_DIR
export BASE_URL='$base'
export F1_RATE='$F1_RATE' F1_START_RATE='$F1_START_RATE'
export F1_RAMP_UP='$F1_RAMP_UP' F1_DURATION='$F1_DURATION' F1_RAMP_DOWN='$F1_RAMP_DOWN'
export PRE_ALLOCATED_VUS='$PRE_ALLOCATED_VUS' MAX_VUS='$MAX_VUS'
# k6 sai 99 se um threshold estourar no fim — não é falha de coleta; seguimos e gravamos o rc.
$REMOTE_K6 run \
  --out json=/tmp/$rid-raw.json \
  --summary-export=/tmp/$rid-summary.json \
  scenarios/f1_low_load.js
k6_rc=\$?
echo "\$k6_rc" > /tmp/$rid-k6rc.txt
test -s /tmp/$rid-summary.json || { echo "k6 não gerou summary (rc=\$k6_rc)" >&2; exit 1; }
python3 - <<'PYEXTRACT'
import json
out=[]
with open('/tmp/$rid-raw.json') as f:
    for line in f:
        try: o=json.loads(line)
        except Exception: continue
        if o.get('type')=='Point' and o.get('metric')=='http_req_duration':
            out.append(o['data']['value'])
json.dump(out, open('/tmp/$rid-latency.json','w'))
print('latency points:', len(out))
PYEXTRACT
rm -f /tmp/$rid-raw.json
REMOTE
	end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	local k6rc
	k6rc="$(ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "cat /tmp/$rid-k6rc.txt 2>/dev/null" || echo unknown)"
	[[ "$k6rc" == "0" ]] || log "  AVISO: k6 saiu com rc=$k6rc (threshold estourado — dado coletado mesmo assim; registrado no meta)"

	scp "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP:/tmp/$rid-summary.json" "$summary_local"
	scp "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP:/tmp/$rid-latency.json" "$latency_local"
	ssh "${SSH_OPTS[@]}" "$RUNNER_USER@$RUNNER_IP" "rm -f /tmp/$rid-summary.json /tmp/$rid-latency.json /tmp/$rid-k6rc.txt" || true
	write_meta "$rt" "$r" "$start" "$end" "$td" "$digest" "$k6ver" "$k6rc"
	log "  OK: $summary_local"
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
		if [[ -f "$OUT_DIR/f1-$rt-r$r-summary.json" && -f "$OUT_DIR/f1-$rt-r$r-latency.json" ]]; then
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

log "F1 re-run concluído. Saídas em $OUT_DIR"
log "Sanidade esperada por rodada: dropped_iterations~0, iterations.count~$THEORETICAL_ITERS"
