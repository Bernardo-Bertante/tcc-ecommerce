#!/usr/bin/env bash
# RECONFIRMACAO sob 1 vCPU (--cpus=1 = 1024 unidades = task Fargate oficial 1024/2048).
# Escopo reduzido: 2 repeticoes por versao. Tudo o mais identico ao teste original.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); cd "$HERE"
export CPU_QUOTA=1
export OUT_DIR="$HERE/results_1vcpu"
mkdir -p "$OUT_DIR"
for rep in 1 2; do
  for ver in sb qj; do
    tag="${ver}-r${rep}"
    [[ -f "$OUT_DIR/$tag.done" ]] && { echo "== pulando $tag =="; continue; }
    echo "===== $(date -Is) INICIO $tag (1 vCPU) ====="
    ./run_one.sh "$ver" "$tag" && touch "$OUT_DIR/$tag.done" || echo "!! falhou $tag"
    echo "===== $(date -Is) FIM $tag ====="
    sleep 20
  done
done
echo "===== $(date -Is) RECONFIRMACAO 1 vCPU CONCLUIDA ====="
