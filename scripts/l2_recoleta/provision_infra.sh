#!/usr/bin/env bash
# Reconstroi do zero toda a infraestrutura AWS necessaria para a recoleta de
# L2: artefatos Lambda das 3 versoes, stack CloudFormation (Lambda + DynamoDB
# + log groups com retencao de 90 dias) e um runner EC2 para o k6 (a stack e
# o runner originais de julho/2026 foram completamente destruidos -- ver
# investigacao anterior, nao e so retencao de log expirada).
#
# Deve ser "sourced" por run_l2_recoleta.sh (usa funcoes/variaveis de
# common.sh). Nao redesploya a funcao entre rodadas de L2 -- isso e feito
# apenas uma vez aqui, para as 3 versoes juntas, porque o protocolo Lambda
# documentado (03-methodology.md) nunca previu "funcao fresca entre
# rodadas" -- isso e exclusivo do protocolo Fargate ("task fresca").

AWS_PROFILE_NAME="${AWS_PROFILE:-pessoal}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
AWS_ARGS=(--profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME")

STACK_NAME="order-processor-benchmark"
RUNNER_KEY_NAME="l2-recoleta-runner-key"
RUNNER_KEY_PATH="$HOME/.ssh/${RUNNER_KEY_NAME}.pem"
RUNNER_SG_NAME="l2-recoleta-runner-sg"
RUNNER_TAG="l2-recoleta-runner"
INFRA_ENV_FILE="$STATE_DIR/infra.env"

_do_build_artifacts() {
  "$REPO_ROOT/infrastructure/aws/scripts/prepare-order-processor-artifacts.sh" 2>&1 | tee -a "$LOG_FILE"
}

step_build_artifacts() {
  log "[1/5] Buildando artefatos Lambda (Spring Boot, Quarkus JVM, Quarkus Native -- a build native usa Docker e e a mais demorada)..."
  # A deteccao de container runtime do Quarkus (docker info, via processo
  # interno do Quarkus) se mostrou ocasionalmente instavel/flaky em teste --
  # falhou uma vez com "Cannot get an executable name when no container
  # runtime is available" e passou de primeira na tentativa seguinte, com
  # docker funcionando identicamente nos dois casos. Retry cobre esse tipo
  # de instabilidade transitoria sem mascarar uma falha real (build
  # continua re-executando do zero, idempotente).
  if ! retry_cmd 2 15 _do_build_artifacts; then
    fatal "Build dos artefatos Lambda falhou 2x seguidas -- nao parece transitorio. Ver $LOG_FILE para o erro de cada tentativa."
  fi
  log "[1/5] Artefatos buildados."
}

step_ensure_artifact_bucket() {
  local account_id
  account_id=$(aws "${AWS_ARGS[@]}" sts get-caller-identity --query Account --output text)
  ARTIFACT_BUCKET="order-processor-l2-recoleta-${account_id}"
  if aws "${AWS_ARGS[@]}" s3api head-bucket --bucket "$ARTIFACT_BUCKET" 2>/dev/null; then
    log "[2/5] Bucket de artefatos ja existe: $ARTIFACT_BUCKET"
  else
    log "[2/5] Criando bucket de artefatos: $ARTIFACT_BUCKET"
    retry_cmd 5 5 aws "${AWS_ARGS[@]}" s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$AWS_REGION_NAME"
  fi
}

step_deploy_stack() {
  log "[3/5] Empacotando e implantando stack ($STACK_NAME) com LogRetentionInDays=90..."
  # As tabelas DynamoDB default (processed_orders, stock_reservations) ja
  # existem no ambiente desde 21/jun/2026, criadas fora de qualquer stack
  # CloudFormation, com dados reais acumulados (4101 e 12293 itens --
  # provavelmente residuo acumulado da propria coleta original de L1/L2/L3,
  # que nunca teve protocolo de reset para o Lambda). O hook
  # AWS::EarlyValidation::ResourceExistenceCheck do CloudFormation bloqueia
  # a criacao de uma tabela com nome ja existente fora do controle da stack
  # -- por isso usamos nomes isolados soh para esta recoleta, sem tocar nas
  # tabelas existentes. O conteudo da tabela nao entra em nenhuma metrica de
  # L2 (latencia/throughput vem do k6, ambientes vem do CloudWatch Logs
  # Insights), entao isso nao tem nenhum impacto na validade dos dados.
  retry_cmd 3 20 "$REPO_ROOT/infrastructure/aws/scripts/deploy-order-processor-stack.sh" \
    --stack-name "$STACK_NAME" \
    --artifact-bucket "$ARTIFACT_BUCKET" \
    --profile "$AWS_PROFILE_NAME" \
    --region "$AWS_REGION_NAME" \
    --log-retention-days 90 \
    --processed-orders-table processed_orders_l2_recoleta \
    --stock-reservations-table stock_reservations_l2_recoleta 2>&1 | tee -a "$LOG_FILE"

  log "Confirmando log groups com retencao de 90 dias (aws logs describe-log-groups)..."
  for fn in order-processor-springboot order-processor-quarkus-jvm order-processor-quarkus-native; do
    local retention
    retention=$(aws "${AWS_ARGS[@]}" logs describe-log-groups \
      --log-group-name-prefix "/aws/lambda/$fn" \
      --query "logGroups[0].retentionInDays" --output text)
    if [[ "$retention" != "90" ]]; then
      fatal "Log group /aws/lambda/$fn nao esta com retencao de 90 dias (retornou: '$retention'). Nao prosseguindo sem essa garantia."
    fi
    log "  /aws/lambda/$fn: retencao=$retention dias [ok]"
  done

  SPRINGBOOT_URL=$(aws "${AWS_ARGS[@]}" cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='SpringBootFunctionUrl'].OutputValue" --output text)
  QUARKUS_JVM_URL=$(aws "${AWS_ARGS[@]}" cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='QuarkusJvmFunctionUrl'].OutputValue" --output text)
  QUARKUS_NATIVE_URL=$(aws "${AWS_ARGS[@]}" cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='QuarkusNativeFunctionUrl'].OutputValue" --output text)

  if [[ -z "$SPRINGBOOT_URL" || -z "$QUARKUS_JVM_URL" || -z "$QUARKUS_NATIVE_URL" ]]; then
    fatal "Nao consegui capturar uma ou mais Function URLs da stack $STACK_NAME."
  fi
  log "[3/5] Stack implantada. Function URLs capturadas:"
  log "  springboot:     $SPRINGBOOT_URL"
  log "  quarkus-jvm:    $QUARKUS_JVM_URL"
  log "  quarkus-native: $QUARKUS_NATIVE_URL"
}

step_provision_runner() {
  log "[4/5] Provisionando runner EC2 para o k6 (m7i-flex.large, mesma regiao/tipo de julho)..."

  if [[ ! -f "$RUNNER_KEY_PATH" ]]; then
    aws "${AWS_ARGS[@]}" ec2 create-key-pair --key-name "$RUNNER_KEY_NAME" \
      --query "KeyMaterial" --output text > "$RUNNER_KEY_PATH"
    chmod 400 "$RUNNER_KEY_PATH"
  fi

  local vpc_id subnet_id sg_id my_ip ami_id instance_id
  vpc_id=$(aws "${AWS_ARGS[@]}" ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text)
  subnet_id=$(aws "${AWS_ARGS[@]}" ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc_id" "Name=default-for-az,Values=true" \
    --query "Subnets[0].SubnetId" --output text)

  sg_id=$(aws "${AWS_ARGS[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$RUNNER_SG_NAME" "Name=vpc-id,Values=$vpc_id" \
    --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || true)
  if [[ -z "$sg_id" || "$sg_id" == "None" ]]; then
    sg_id=$(aws "${AWS_ARGS[@]}" ec2 create-security-group --group-name "$RUNNER_SG_NAME" \
      --description "SSH temporario para runner k6 da recoleta L2 (TCC)" --vpc-id "$vpc_id" --query "GroupId" --output text)
    my_ip=$(curl -s https://checkip.amazonaws.com)
    aws "${AWS_ARGS[@]}" ec2 authorize-security-group-ingress --group-id "$sg_id" \
      --protocol tcp --port 22 --cidr "${my_ip}/32" >/dev/null
  fi
  SG_ID="$sg_id"

  ami_id=$(aws "${AWS_ARGS[@]}" ssm get-parameters \
    --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query "Parameters[0].Value" --output text)

  cat > "$STATE_DIR/userdata.sh" <<'USERDATA'
#!/bin/bash
cat > /etc/yum.repos.d/k6.repo <<'REPO'
[k6]
name=k6
baseurl=https://repo.k6.io/rpm
enabled=1
gpgcheck=1
gpgkey=https://repo.k6.io/key.gpg
REPO
yum install -y k6
USERDATA

  instance_id=$(aws "${AWS_ARGS[@]}" ec2 run-instances \
    --image-id "$ami_id" --instance-type m7i-flex.large \
    --key-name "$RUNNER_KEY_NAME" --security-group-ids "$sg_id" --subnet-id "$subnet_id" \
    --associate-public-ip-address \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$RUNNER_TAG}]" \
    --user-data "file://$STATE_DIR/userdata.sh" \
    --query "Instances[0].InstanceId" --output text)
  INSTANCE_ID="$instance_id"

  log "Instancia lancada: $instance_id -- aguardando status ok..."
  aws "${AWS_ARGS[@]}" ec2 wait instance-status-ok --instance-ids "$instance_id"
  RUNNER_IP=$(aws "${AWS_ARGS[@]}" ec2 describe-instances --instance-ids "$instance_id" \
    --query "Reservations[0].Instances[0].PublicIpAddress" --output text)
  log "Runner no ar: $instance_id ($RUNNER_IP)"

  log "Verificando SSH + instalacao do k6 (com retry -- user-data pode ainda estar rodando)..."
  local ok=false
  for i in $(seq 1 20); do
    if ssh -i "$RUNNER_KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
        "ec2-user@$RUNNER_IP" 'command -v k6 >/dev/null 2>&1 && echo K6_OK' 2>/dev/null | grep -q K6_OK; then
      ok=true
      break
    fi
    log "  tentativa $i/20: k6 ainda nao disponivel no runner, aguardando 15s..."
    sleep 15
  done
  if [[ "$ok" != true ]]; then
    fatal "k6 nao ficou disponivel no runner ($RUNNER_IP) apos 20 tentativas (~5min). Verifique manualmente: ssh -i $RUNNER_KEY_PATH ec2-user@$RUNNER_IP 'cat /var/log/cloud-init-output.log'"
  fi

  ssh -i "$RUNNER_KEY_PATH" -o StrictHostKeyChecking=accept-new "ec2-user@$RUNNER_IP" 'mkdir -p /tmp/scenarios /tmp/lib'
  scp -i "$RUNNER_KEY_PATH" -q -r "$REPO_ROOT/benchmark/scenarios/." "ec2-user@$RUNNER_IP:/tmp/scenarios/"
  scp -i "$RUNNER_KEY_PATH" -q -r "$REPO_ROOT/benchmark/lib/." "ec2-user@$RUNNER_IP:/tmp/lib/"
  log "[4/5] Runner provisionado e scripts do k6 copiados."
}

step_write_state() {
  cat > "$INFRA_ENV_FILE" <<EOF
AWS_PROFILE_NAME=$AWS_PROFILE_NAME
AWS_REGION_NAME=$AWS_REGION_NAME
STACK_NAME=$STACK_NAME
ARTIFACT_BUCKET=$ARTIFACT_BUCKET
RUNNER_KEY_NAME=$RUNNER_KEY_NAME
RUNNER_KEY_PATH=$RUNNER_KEY_PATH
RUNNER_SG_NAME=$RUNNER_SG_NAME
SG_ID=$SG_ID
INSTANCE_ID=$INSTANCE_ID
RUNNER_IP=$RUNNER_IP
SPRINGBOOT_URL=$SPRINGBOOT_URL
QUARKUS_JVM_URL=$QUARKUS_JVM_URL
QUARKUS_NATIVE_URL=$QUARKUS_NATIVE_URL
EOF
  log "[5/5] Estado de infraestrutura salvo em $INFRA_ENV_FILE"
}

provision_all() {
  step_build_artifacts
  step_ensure_artifact_bucket
  step_deploy_stack
  step_provision_runner
  step_write_state
}
