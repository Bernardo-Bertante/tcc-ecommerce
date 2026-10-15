#!/usr/bin/env bash
# 3 repetições × {qj,qn} × {48,240}, ordem intercalada para não confundir deriva térmica/tempo com versão.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
order=(
  "qj 48 r1" "qn 48 r1" "qn 240 r1" "qj 240 r1"
  "qn 48 r2" "qj 48 r2" "qj 240 r2" "qn 240 r2"
  "qj 48 r3" "qn 48 r3" "qn 240 r3" "qj 240 r3"
)
for item in "${order[@]}"; do
  set -- $item
  echo "$(date -Is) start $1-$2-$3"
  "$HERE/run_one.sh" "$1" "$2" "$1-$2-$3" || echo "$(date -Is) FAILED $1-$2-$3"
  sleep 20
done
echo "$(date -Is) ALL DONE"
