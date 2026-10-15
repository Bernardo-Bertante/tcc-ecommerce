#!/usr/bin/env bash
# Matriz 3 rodadas x {sb,qj} x {c1,c2}, 480 s a 20 rps (~9600 invocações), ordem contrabalanceada. Retomável.
cd "$(dirname "$0")"
orders=("sb-c1 qj-c1 sb-c2 qj-c2" "qj-c2 sb-c2 qj-c1 sb-c1" "sb-c2 qj-c1 qj-c2 sb-c1")
for r in 1 2 3; do
  for combo in ${orders[$((r-1))]}; do
    ver=${combo%-*}; cond=${combo#*-}; tag=r$r-$ver-$cond
    if grep -q load_end results/$tag.meta 2>/dev/null; then echo "skip $tag"; continue; fi
    echo "$(date +%T) start $tag load=$(cut -d' ' -f1-3 /proc/loadavg)"
    ./run_one.sh $ver $cond $tag 480s
    echo "load_start_end=$(cut -d' ' -f1-3 /proc/loadavg)" >> results/$tag.meta
    echo "load_end" >> results/$tag.meta
  done
done
echo ALL_DONE
