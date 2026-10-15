#!/usr/bin/env bash
# Teste do cliente HTTP: 3 rodadas x {sb, qj, qja (Quarkus+apache), sbu (Spring+UrlConnection)}, CPU livre, ordem contrabalanceada. Retomável.
cd "$(dirname "$0")"
export RESULTS_DIR="$PWD/results_httpclient"; mkdir -p "$RESULTS_DIR"
orders=("sb qj qja sbu" "sbu qja qj sb" "qja sb sbu qj")
for r in 1 2 3; do
  for ver in ${orders[$((r-1))]}; do
    tag=h$r-$ver-free
    if grep -q load_end $RESULTS_DIR/$tag.meta 2>/dev/null; then echo "skip $tag"; continue; fi
    echo "$(date +%T) start $tag load=$(cut -d' ' -f1-3 /proc/loadavg)"
    ./run_one.sh $ver free $tag 300s
    echo "load_start_end=$(cut -d' ' -f1-3 /proc/loadavg)" >> $RESULTS_DIR/$tag.meta
    echo "load_end" >> $RESULTS_DIR/$tag.meta
  done
done
echo ALL_DONE
