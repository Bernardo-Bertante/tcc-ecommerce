#!/usr/bin/env bash
# 3 repetições por versão, alternando sb/qj para diluir deriva térmica/de máquina.
# Roda desacoplado: setsid + systemd-inhibit (bloqueia suspensão enquanto durar).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE"

for rep in 1 2 3; do
  for ver in sb qj; do
    tag="${ver}-r${rep}"
    if [[ -f "results/$tag.done" ]]; then echo "== pulando $tag (ja feito) =="; continue; fi
    echo "===== $(date -Is) INICIO $tag ====="
    ./run_one.sh "$ver" "$tag" && touch "results/$tag.done" || echo "!! falhou $tag"
    echo "===== $(date -Is) FIM $tag ====="
    sleep 20
  done
done
echo "===== $(date -Is) repeticoes concluidas, contagem de maquinaria (tarefa 5) ====="
for ver in sb qj; do ./count_machinery.sh "$ver" || echo "!! falhou count-$ver"; done
echo "===== $(date -Is) TUDO CONCLUIDO ====="
