#!/usr/bin/env bash
# Teste da validation-query sob 1 vCPU (24/09/2026). Tudo identico a reconfirmacao
# de 20/09 (run_all_1vcpu.sh), exceto a variavel de validacao do SB.
#   sbnv-r1..r3 : Spring Boot com SPRING_R2DBC_POOL_VALIDATION_QUERY= (validacao desligada)
#   sbval-a1    : Spring Boot COMO NO ORIGINAL (validacao ligada), ancora do mesmo dia,
#                 para separar efeito da validacao de deriva do host entre 20/09 e 24/09.
# Ordem: nv, nv, ancora, nv. Quarkus JVM nao roda (nunca teve validation-query).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); cd "$HERE"
export CPU_QUOTA=1
export OUT_DIR="$HERE/results"
mkdir -p "$OUT_DIR"
for spec in sbnv-r1:off sbnv-r2:off sbval-a1:on sbnv-r3:off; do
  tag=${spec%%:*}; val=${spec##*:}
  [[ -f "$OUT_DIR/$tag.done" ]] && { echo "== pulando $tag =="; continue; }
  echo "===== $(date -Is) INICIO $tag (1 vCPU, validacao=$val) ====="
  SB_VALIDATION=$val ./run_one_valcon.sh sb "$tag" && touch "$OUT_DIR/$tag.done" || echo "!! falhou $tag"
  echo "===== $(date -Is) FIM $tag ====="
  sleep 20
done
echo "===== $(date -Is) TESTE VALIDACAO CONCLUIDO ====="
