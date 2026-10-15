#!/usr/bin/env bash
# Série do teste exploratório de build. Uso: run_series.sh warmup | measured
# Ordem: lista base rotacionada k posições na rodada k (k=0 aquecimento, k=1..5 medidas),
# de modo que cada versão ocupa cada posição uma vez. Sequencial; pausa de 30 s antes de cada build.
set -u
OUT=/home/bernardo/Programming/ecommerce-tcc/analysis/exploratorio_build
BASE=(os-sb os-qj os-qn op-sb op-qj op-qn)

run_round() {
  local k=$1 rep=$2 kind=$3
  for i in 0 1 2 3 4 5; do
    local v=${BASE[$(( (i + k) % 6 ))]}
    echo "[$(date '+%F %T')] round=$k rep=$rep pos=$i version=$v"
    if ! python3 "$OUT/run_one.py" --version "$v" --rep "$rep" --kind "$kind"; then
      echo "[$(date '+%F %T')] FALHA $v $rep -> uma nova tentativa (retry)"
      python3 "$OUT/run_one.py" --version "$v" --rep "${rep}b" --kind retry \
        || echo "[$(date '+%F %T')] FALHA DE NOVO $v ${rep}b (sem mais tentativas)"
    fi
  done
}

case "${1:-}" in
  warmup)   run_round 0 w warmup ;;
  measured) for k in 1 2 3 4 5; do run_round "$k" "r$k" measured; done ;;
  *) echo "uso: $0 warmup|measured" >&2; exit 2 ;;
esac
echo "[$(date '+%F %T')] fim ($1)"
