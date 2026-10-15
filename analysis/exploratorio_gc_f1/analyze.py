#!/usr/bin/env python3
"""Exploratório GC F1: Quarkus JVM (ParallelGC) vs Native (Serial GC) em 48 e 240 iter/s.

Janela analisada por rodada = regime aquecido: do início da carga (primeira req phase=load)
+ rampa (60 s) + 120 s de aquecimento, até o fim do hold. Latência = http_req_duration das
requisições phase=load (mesmo recorte do F1 oficial). GC e CPU recortados na mesma janela.
"""
import glob
import gzip
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
RAMP_S, WARM_S, HOLD_S = 60, 120, 540

JVM_PAUSE = re.compile(r"^\[([^\]]+)\]\[[\d.]+s\]\[info\]\[gc\s*\] GC\(\d+\) (Pause \w+) \(([^)]*)\).* ([\d.]+)ms$")
NAT_PAUSE = re.compile(r"\[([\d.]+)s\] GC\(\d+\) Pause (Full|Incremental) GC \(([^)]*)\).* ([\d.]+)ms")
NAT_STARTED = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) INFO .*started in ([\d.]+)s")


def read_meta(tag):
    meta = {}
    for line in open(os.path.join(RES, f"{tag}.meta")):
        for kv in line.split():
            k, _, v = kv.partition("=")
            meta[k] = v
    return meta


def latencies(tag):
    ts, vals = [], []
    with gzip.open(os.path.join(RES, f"{tag}.k6.csv.gz"), "rt") as fh:
        for line in fh:
            if line.startswith("http_req_duration,") and "phase=load" in line:
                parts = line.split(",", 3)
                ts.append(int(parts[1]))
                vals.append(float(parts[2]))
    return np.array(ts), np.array(vals)


def jvm_pauses(tag):
    rows = []
    for line in open(os.path.join(RES, f"{tag}.gc.log")):
        m = JVM_PAUSE.match(line.strip())
        if m:
            t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
            rows.append((t, m.group(2), float(m.group(4))))
    return pd.DataFrame(rows, columns=["t", "kind", "ms"])


def native_pauses(tag):
    # Uptime do log nativo -> relógio: âncora na linha "started in Xs" (horário local do container = UTC).
    lines = open(os.path.join(RES, f"{tag}.container.log"), errors="replace").read().splitlines()
    t0 = None
    for line in lines:
        m = NAT_STARTED.match(line)
        if m:
            started = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=timezone.utc).timestamp()
            t0 = started - float(m.group(2))
            break
    rows = []
    for line in lines:
        for m in NAT_PAUSE.finditer(line):
            rows.append((t0 + float(m.group(1)), "Pause " + m.group(2), float(m.group(4))))
    return pd.DataFrame(rows, columns=["t", "kind", "ms"])


def cliffs_delta(a, b):
    u = mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2 * u / (len(a) * len(b)) - 1


def main():
    runs, lat_pool = [], {}
    for meta_path in sorted(glob.glob(os.path.join(RES, "q[jn]-*-r*.meta"))):
        tag = os.path.basename(meta_path)[:-5]
        if not os.path.exists(os.path.join(RES, f"{tag}.k6.csv.gz")):
            continue  # rodada em andamento
        meta = read_meta(tag)
        ver, rate = meta["ver"], int(meta["rate"])
        ts, lat = latencies(tag)
        load_start = ts.min()
        w0, w1 = load_start + RAMP_S + WARM_S, load_start + RAMP_S + HOLD_S
        sel = (ts >= w0) & (ts < w1)
        lat_w = lat[sel]
        lat_pool.setdefault((ver, rate), []).append(lat_w)
        win_s = w1 - w0

        gc = jvm_pauses(tag) if ver == "qj" else native_pauses(tag)
        gcw = gc[(gc.t >= w0) & (gc.t < w1)]
        full = gcw[gcw.kind.str.contains("Full")]

        cpu = pd.read_csv(os.path.join(RES, f"{tag}.cpu.tsv"), sep=" ", names=["t", "usec", "mem"])
        cw = cpu[(cpu.t >= w0) & (cpu.t <= w1)]
        vcpu = (cw.usec.iloc[-1] - cw.usec.iloc[0]) / 1e6 / (cw.t.iloc[-1] - cw.t.iloc[0])

        runs.append(dict(
            tag=tag, ver=ver, rate=rate, n_req=len(lat_w), rps=len(lat_w) / win_s,
            lat_mean=lat_w.mean(), lat_p50=np.percentile(lat_w, 50), lat_p90=np.percentile(lat_w, 90),
            lat_p95=np.percentile(lat_w, 95), lat_p99=np.percentile(lat_w, 99),
            gc_count=len(gcw), gc_per_min=len(gcw) / win_s * 60, gc_full=len(full),
            gc_pause_mean_ms=gcw.ms.mean() if len(gcw) else 0.0,
            gc_pause_max_ms=gcw.ms.max() if len(gcw) else 0.0,
            gc_full_mean_ms=full.ms.mean() if len(full) else np.nan,
            gc_pause_total_ms=gcw.ms.sum(), gc_time_frac_pct=gcw.ms.sum() / 1000 / win_s * 100,
            gc_ms_per_1k_req=gcw.ms.sum() / len(lat_w) * 1000,
            vcpu=vcpu, cpu_ms_per_req=vcpu * win_s * 1000 / len(lat_w),
            gc_share_of_cpu_pct=gcw.ms.sum() / 1000 / (vcpu * win_s) * 100,
            mem_mb_mean=cw.mem.mean() / 2**20,
        ))

    df = pd.DataFrame(runs).sort_values(["rate", "ver", "tag"])
    df.to_csv(os.path.join(HERE, "gc_por_rodada.csv"), index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.precision", 3)
    print(df.drop(columns=["lat_mean"]).to_string(index=False))

    agg = df.groupby(["rate", "ver"]).mean(numeric_only=True)
    agg.to_csv(os.path.join(HERE, "gc_resumo.csv"))
    print("\n== médias por condição\n", agg.T.to_string())

    print("\n== latência agregada (todas as rodadas) e Cliff's delta QJ vs QN")
    for rate in sorted({r for _, r in lat_pool}):
        if ("qj", rate) not in lat_pool or ("qn", rate) not in lat_pool:
            continue
        a, b = np.concatenate(lat_pool[("qj", rate)]), np.concatenate(lat_pool[("qn", rate)])
        print(f"rate={rate}: QJ med={np.median(a):.3f} p95={np.percentile(a, 95):.3f} | "
              f"QN med={np.median(b):.3f} p95={np.percentile(b, 95):.3f} | "
              f"QN/QJ med={np.median(b) / np.median(a):.3f} | cliff(QJ,QN)={cliffs_delta(a, b):+.3f}")


if __name__ == "__main__":
    main()
