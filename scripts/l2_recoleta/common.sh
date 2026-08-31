#!/usr/bin/env bash
# Funcoes compartilhadas pelos scripts de recoleta de L2. Deve ser
# "sourced", nunca executado diretamente.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR_COMMON="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR_COMMON/state"
mkdir -p "$STATE_DIR"

LOG_FILE="${L2_RECOLETA_LOG:-$REPO_ROOT/analysis/l2_recoleta_execucao.log}"
STATUS_FILE="${L2_RECOLETA_STATUS:-$REPO_ROOT/analysis/l2_recoleta_status.txt}"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"
}

status() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$STATUS_FILE" >> "$LOG_FILE"
}

fatal() {
  log "ERRO FATAL (nao transitorio): $*"
  status "PARADO -- erro fatal, ver $LOG_FILE para detalhes: $*"
  exit 1
}

# retry_cmd MAX_TENTATIVAS DELAY_BASE_SEG -- comando args...
# Backoff exponencial simples para chamadas AWS CLI sujeitas a erro
# transitorio (throttling, timeout de rede). NAO usar para a reconciliacao
# do CloudWatch Logs Insights -- essa tem sua propria politica de retry
# (ver cw_env_analysis.py), porque o criterio de "sucesso" la nao e so
# exit-code, e sim contagem de invocacoes reconciliada.
retry_cmd() {
  local max_attempts="$1"; shift
  local base_delay="$1"; shift
  local attempt=1
  until "$@"; do
    local rc=$?
    if (( attempt >= max_attempts )); then
      log "retry_cmd: comando falhou apos $attempt tentativas (status=$rc): $*"
      return "$rc"
    fi
    local delay=$(( base_delay * attempt ))
    log "retry_cmd: tentativa $attempt falhou (status=$rc), tentando de novo em ${delay}s: $*"
    sleep "$delay"
    attempt=$(( attempt + 1 ))
  done
  return 0
}
