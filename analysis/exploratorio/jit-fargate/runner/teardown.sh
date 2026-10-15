#!/usr/bin/env bash
#
# teardown.sh — desmonta o teste exploratório JIT/Fargate. Idempotente; pode ser chamado pelo driver
# (fim normal ou trap de erro), pelo cronômetro de segurança (systemd) ou à mão.
# Uso: teardown.sh <full|smoke> <origem: driver|failsafe|manual>
#   smoke* = ENSAIO: para as tasks de verdade, mas NÃO apaga RDS/cluster nem desliga a EC2;
#           só registra o que faria e o estado atual de cada alvo.
set -uo pipefail
MODO="${1:?full|smoke}"; ORIGEM="${2:-manual}"
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 AWS_RETRY_MODE=adaptive AWS_MAX_ATTEMPTS=10
BASE=/home/ec2-user/exp-jit
OUT=$BASE/out-$MODO; mkdir -p "$OUT"
S3=s3://exp-jit-results-776648109551/$MODO
CLUSTER=exp-jit-cluster
RDS=exp-jit-postgres
TLOG=$OUT/teardown.log
log() { echo "[$(date -u +%FT%TZ)] teardown($ORIGEM): $*" | tee -a "$TLOG" >&2; }

exec 9>/tmp/exp-jit-teardown.lock
flock -n 9 || { log "outro teardown em curso; saindo"; exit 0; }
log "início (modo=$MODO)"

# 1. tasks
for i in 1 2 3; do
	arns=$(aws ecs list-tasks --cluster $CLUSTER --desired-status RUNNING --query taskArns --output text 2>/dev/null)
	[[ -z "$arns" || "$arns" == None ]] && break
	for a in $arns; do log "stop-task $a"; aws ecs stop-task --cluster $CLUSTER --task "$a" --reason exp-jit-teardown >/dev/null 2>&1; done
	aws ecs wait tasks-stopped --cluster $CLUSTER --tasks $arns 2>/dev/null
done
restantes=$(aws ecs list-tasks --cluster $CLUSTER --desired-status RUNNING --query 'length(taskArns)' --output text 2>/dev/null)
log "tasks RUNNING no cluster após parada: ${restantes:-?}"

# 2. logs das rodadas já no S3?
faltam=""
for d in "$OUT"/rodadas/*/; do
	[[ -d "$d" ]] || continue; r=$(basename "$d"); [[ "$r" == *_tentativa_falha_* ]] && continue
	aws s3 ls "$S3/rodadas/$r/logs.jsonl.gz" >/dev/null 2>&1 || faltam="$faltam $r"
done
if [[ -n "$faltam" ]]; then
	log "AVISO: logs.jsonl.gz ausente no S3 para:$faltam (os eventos continuam no CloudWatch por 14 dias)"
	for r in $faltam; do aws s3 sync --quiet "$OUT/rodadas/$r" "$S3/rodadas/$r/" 2>/dev/null; done
else
	log "logs de todas as rodadas confirmados no S3"
fi
[[ -d "$OUT/csv" ]] && aws s3 sync --quiet "$OUT/csv" "$S3/csv/" 2>/dev/null

if [[ "$MODO" == smoke* ]]; then
	log "ENSAIO: apagaria RDS $RDS (estado: $(aws rds describe-db-instances --db-instance-identifier $RDS --query 'DBInstances[0].DBInstanceStatus' --output text 2>&1))"
	log "ENSAIO: apagaria cluster $CLUSTER (estado: $(aws ecs describe-clusters --clusters $CLUSTER --query 'clusters[0].status' --output text 2>&1))"
	log "ENSAIO: apagaria schedules exp-jit/* e desligaria esta EC2 (shutdown -> terminate). Nada disso executado."
	aws s3 cp --quiet "$TLOG" "$S3/teardown.log"
	exit 0
fi

# 3. RDS (sem snapshot final; os dados de interesse são os logs da JVM, que não estão no banco)
st=$(aws rds describe-db-instances --db-instance-identifier $RDS --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null)
if [[ -n "$st" && "$st" != deleting ]]; then
	log "delete-db-instance $RDS (estado $st)"
	aws rds delete-db-instance --db-instance-identifier $RDS --skip-final-snapshot --delete-automated-backups >/dev/null 2>>"$TLOG"
fi
for i in $(seq 1 40); do   # até 20 min para confirmar
	st=$(aws rds describe-db-instances --db-instance-identifier $RDS --query 'DBInstances[0].DBInstanceStatus' --output text 2>&1)
	[[ "$st" == *DBInstanceNotFound* ]] && { st=apagado; break; }
	sleep 30
done
log "RDS: $st"

# 4. cluster
for i in 1 2 3 4 5; do
	aws ecs delete-cluster --cluster $CLUSTER >/dev/null 2>>"$TLOG" && break
	sleep 30
done
cst=$(aws ecs describe-clusters --clusters $CLUSTER --query 'clusters[0].status' --output text 2>&1)
log "cluster: $cst"

# 5. cronômetros de segurança do EventBridge Scheduler (desnecessários após teardown normal)
for s in exp-jit-failsafe-rds exp-jit-failsafe-ec2; do
	aws scheduler delete-schedule --group-name exp-jit --name $s >/dev/null 2>&1 && log "schedule $s apagado"
done

# 6. inventário do que sobrou
{
	echo "modo=$MODO teardown($ORIGEM) concluído em $(date -u +%FT%TZ)"
	echo "RDS $RDS: $st"
	echo "cluster $CLUSTER: $cst (tasks RUNNING após parada: ${restantes:-?})"
	echo "--- sobram (Fase C apaga com aprovação):"
	aws ecs list-task-definitions --family-prefix exp-jit --query taskDefinitionArns --output text 2>&1 | tr '\t' '\n' | sed 's/^/task def: /'
	aws logs describe-log-groups --log-group-name-prefix exp-jit --query 'logGroups[].logGroupName' --output text 2>&1 | tr '\t' '\n' | sed 's/^/log group: /'
	aws ec2 describe-security-groups --filters Name=group-name,Values='exp-jit-*' --query 'SecurityGroups[].[GroupName,GroupId]' --output text 2>&1 | sed 's/^/sg: /'
	echo "iam: exp-jit-runner-role (+profile), exp-jit-task-exec-role, exp-jit-task-role, exp-jit-scheduler-role"
	echo "secret: exp-jit-db; bucket: exp-jit-results-776648109551; rds param group: exp-jit-pg16; schedule group: exp-jit"
	echo "EC2 exp-jit-runner: desligando agora (shutdown -> terminate)"
	echo "--- rodadas:"; cat "$OUT/rodadas.txt" 2>/dev/null
} > "$OUT/STATUS"
aws s3 cp --quiet "$OUT/STATUS" "$S3/STATUS"
[[ -f "$OUT/driver.log" ]] && aws s3 cp --quiet "$OUT/driver.log" "$S3/driver.log"
if [[ "$ORIGEM" == failsafe && ! -f "$OUT/DONE" ]]; then
	echo "cronômetro de segurança disparou antes do fim do driver" > "$OUT/FAILED"; aws s3 cp --quiet "$OUT/FAILED" "$S3/FAILED"
fi
log "desligando a instância"
aws s3 cp --quiet "$TLOG" "$S3/teardown.log"
shutdown -h +1 "exp-jit teardown"
