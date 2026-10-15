#!/usr/bin/env bash
# Matriz 3 rodadas x {sb,qj} x {free,lim}, ordem contrabalanceada. Pula rodadas já concluídas (retomável).
cd "$(dirname "$0")"
orders=("sb-free qj-free sb-lim qj-lim" "qj-lim sb-lim qj-free sb-free" "sb-lim qj-free qj-lim sb-free")
for r in 1 2 3; do
  for combo in ${orders[$((r-1))]}; do
    ver=${combo%-*}; cond=${combo#*-}; tag=r$r-$ver-$cond
    if grep -q load_end results/$tag.meta 2>/dev/null; then echo "skip $tag"; continue; fi
    echo "$(date +%T) start $tag load=$(cut -d' ' -f1-3 /proc/loadavg)"
    ./run_one.sh $ver $cond $tag 300s
    echo "load_start_end=$(cut -d' ' -f1-3 /proc/loadavg)" >> results/$tag.meta
    echo "load_end" >> results/$tag.meta
  done
done
echo ALL_DONE
