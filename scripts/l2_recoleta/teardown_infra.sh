#!/usr/bin/env bash
# Derruba SO o runner EC2 temporario (instancia, security group, key pair) --
# isso e o que tem custo por hora. A stack CloudFormation (Lambda + DynamoDB
# + log groups com retencao de 90 dias) e MANTIDA de proposito: e o motivo
# de termos subido a retencao para 90 dias, e Lambda/DynamoDB on-demand nao
# tem custo de ficar parado. Pode ser rodado sozinho a qualquer momento
# (idempotente-ish: falha graciosamente se os recursos ja nao existirem).
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

INFRA_ENV_FILE="$STATE_DIR/infra.env"
if [[ ! -f "$INFRA_ENV_FILE" ]]; then
  log "teardown_infra: $INFRA_ENV_FILE nao existe -- nada a derrubar (infra nunca foi provisionada ou ja foi derrubada)."
  exit 0
fi
# shellcheck disable=SC1090
source "$INFRA_ENV_FILE"

AWS_ARGS=(--profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME")

if [[ -n "${INSTANCE_ID:-}" ]]; then
  log "Encerrando runner EC2 ($INSTANCE_ID)..."
  if aws "${AWS_ARGS[@]}" ec2 describe-instances --instance-ids "$INSTANCE_ID" >/dev/null 2>&1; then
    aws "${AWS_ARGS[@]}" ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null
    aws "${AWS_ARGS[@]}" ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
    log "Instancia $INSTANCE_ID terminada."
  else
    log "Instancia $INSTANCE_ID ja nao existe."
  fi
fi

if [[ -n "${SG_ID:-}" ]]; then
  log "Removendo security group temporario ($SG_ID)..."
  retry_cmd 5 10 aws "${AWS_ARGS[@]}" ec2 delete-security-group --group-id "$SG_ID" 2>&1 | tee -a "$LOG_FILE" || \
    log "Nao consegui remover o security group $SG_ID (pode ja ter sido removido, ou ainda estar associado a algo) -- siga em frente, nao e bloqueante."
fi

if [[ -n "${RUNNER_KEY_NAME:-}" ]]; then
  log "Removendo key pair temporario ($RUNNER_KEY_NAME)..."
  aws "${AWS_ARGS[@]}" ec2 delete-key-pair --key-name "$RUNNER_KEY_NAME" >/dev/null 2>&1 || true
fi

log "Runner desligado."
log "A stack CloudFormation ($STACK_NAME), as tabelas DynamoDB e os log groups (retencao 90 dias) foram"
log "MANTIDOS de proposito. Para derrubar tudo manualmente mais tarde:"
log "  aws cloudformation delete-stack --stack-name $STACK_NAME --profile $AWS_PROFILE_NAME --region $AWS_REGION_NAME"

rm -f "$INFRA_ENV_FILE"
