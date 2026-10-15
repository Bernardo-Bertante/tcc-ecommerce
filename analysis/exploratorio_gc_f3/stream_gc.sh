#!/usr/bin/env bash
# Streama /tmp/gc.log do container gcf3-app para fora, sobrevivendo a troca de
# container (sb -> qj). Salvaguarda: o run_all.sh remove o container no fim de
# cada runtime, e o slice_gc.py precisa das fontes brutas.
set -uo pipefail
D="docker --context default"
HERE=$(cd "$(dirname "$0")" && pwd); RAW="$HERE/results/gc_raw"; mkdir -p "$RAW"
for _ in $(seq 400); do
  img=$($D inspect gcf3-app --format '{{.Config.Image}}' 2>/dev/null) || { sleep 5; continue; }
  case "$img" in
    gcf3-sb:official) ver=sb ;;
    gcf3-qj:official) ver=qj ;;
    *) sleep 5; continue ;;
  esac
  $D exec gcf3-app sh -c 'test -s /tmp/gc.log' 2>/dev/null || { sleep 3; continue; }
  echo "$(date +%H:%M:%S) streamando $ver"
  $D exec gcf3-app tail -F -c +1 /tmp/gc.log >> "$RAW/gc.stream.$ver.log" 2>>"$RAW/gc.stream.$ver.err"
  echo "$(date +%H:%M:%S) stream de $ver encerrado (container removido)"
  sleep 3
done
