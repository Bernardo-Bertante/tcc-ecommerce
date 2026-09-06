"""
Extração de CPU/memória de container (Fargate) para a RE-COLETA dedicada do F3
(analysis/fargate/fase3-f3-rerun/, 15 rodadas), isolando a FASE DE PICO (10 min)
com a granularidade de 1 minuto do CloudWatch.

Diferença vs. a coleta de julho: aqui cada rodada tem meta.json com o timestamp
EXATO de cada fase (extraído do 1º/último Point de carga no JSON bruto do k6),
então a janela de pico é exata — sem a suposição PRE_K6 que a reconstrução de
julho (fase5_recursos_fase_isolada.py, F3) precisou fazer, e com period=60
(≈10 datapoints/rodada) em vez de period=300 (≈2 datapoints/rodada).

Fonte: ECS/ContainerInsights, CpuUtilized/MemoryUtilized,
dims ClusterName=order-service-cluster + TaskDefinitionFamily=order-service-<runtime>.

Saída: analysis/fase5/fase5_recursos_f3_rerun_p60.csv
  (mesmo formato de fase5_fargate_recursos_novo.csv — NÃO sobrescreve nada).

Também imprime a tabela comparativa dos 3 métodos:
  1. janela contaminada  (mtime±600s, period=300)  <- fase5_fargate_recursos_novo.csv  (julho)
  2. fase isolada p300    (RunTask+PRE_K6, period=300, ~2 dp)  <- fase5_recursos_fase_isolada.csv  (julho)
  3. fase isolada p60     (meta.json exato, period=60, ~10 dp)  <- ESTE script  (re-coleta set/2026)
"""
import glob
import json
import os
import datetime as dt

import numpy as np
import pandas as pd
import boto3

SESSION = boto3.Session(profile_name="pessoal", region_name="us-east-1")
CW = SESSION.client("cloudwatch")

CLUSTER = "order-service-cluster"
CPU_UNITS = 1024
MEM_MB = 2048
FAMILY = {
    "springboot": "order-service-springboot",
    "quarkus-jvm": "order-service-quarkus-jvm",
    "quarkus-native": "order-service-quarkus-native",
}

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RERUN_DIR = os.path.join(REPO, "analysis/fargate/fase3-f3-rerun")
OUT = os.path.join(REPO, "analysis/fase5/fase5_recursos_f3_rerun_p60.csv")


def get_metric(family, metric, start, end, period):
    r = CW.get_metric_statistics(
        Namespace="ECS/ContainerInsights", MetricName=metric,
        Dimensions=[{"Name": "ClusterName", "Value": CLUSTER},
                    {"Name": "TaskDefinitionFamily", "Value": family}],
        StartTime=start, EndTime=end, Period=period,
        Statistics=["Average", "Maximum"])
    return sorted(r["Datapoints"], key=lambda d: d["Timestamp"])


def window_stats(cenario, runtime, rnd, win_start, win_end, period):
    fam = FAMILY[runtime]
    cpu = get_metric(fam, "CpuUtilized", win_start - dt.timedelta(seconds=period),
                     win_end + dt.timedelta(seconds=period), period)
    mem = get_metric(fam, "MemoryUtilized", win_start - dt.timedelta(seconds=period),
                     win_end + dt.timedelta(seconds=period), period)

    def inside(dp):
        mid = dp["Timestamp"] + dt.timedelta(seconds=period / 2)
        return win_start <= mid <= win_end

    cpu = [d for d in cpu if inside(d)]
    mem = [d for d in mem if inside(d)]
    if not cpu:
        print(f"  [!] {cenario}/{runtime}/r{rnd}: 0 datapoints na janela de pico")
        return None
    ca = [d["Average"] for d in cpu]
    cm = [d["Maximum"] for d in cpu]
    ma = [d["Average"] for d in mem]
    mm = [d["Maximum"] for d in mem]
    return {
        "cenario": cenario, "runtime": runtime, "round": rnd,
        "n_datapoints_cpu": len(cpu),
        "cpu_units_mean": float(np.mean(ca)), "cpu_units_max": float(np.max(cm)),
        "cpu_pct_mean": float(np.mean(ca) / CPU_UNITS * 100),
        "cpu_pct_max": float(np.max(cm) / CPU_UNITS * 100),
        "mem_mb_mean": float(np.mean(ma)), "mem_mb_max": float(np.max(mm)),
        "mem_pct_mean": float(np.mean(ma) / MEM_MB * 100),
        "mem_pct_max": float(np.max(mm) / MEM_MB * 100),
    }


def main():
    rows = []
    for mp in sorted(glob.glob(os.path.join(RERUN_DIR, "f3-*-meta.json"))):
        d = json.load(open(mp))
        rt, rnd = d["runtime"], d["round"]
        peak = next(p for p in d["phases"] if p["name"] == "peak")
        ws = dt.datetime.fromisoformat(peak["start_utc"].replace("Z", "+00:00"))
        we = dt.datetime.fromisoformat(peak["end_utc"].replace("Z", "+00:00"))
        r = window_stats("f3", rt, rnd, ws, we, 60)
        if r:
            r["peak_start_utc"] = peak["start_utc"]
            rows.append(r)

    cols = ["cenario", "runtime", "round", "n_datapoints_cpu",
            "cpu_units_mean", "cpu_units_max", "cpu_pct_mean", "cpu_pct_max",
            "mem_mb_mean", "mem_mb_max", "mem_pct_mean", "mem_pct_max"]
    df = pd.DataFrame(rows)
    df[cols].to_csv(OUT, index=False)
    print(f"[ok] {OUT}  ({len(df)} linhas)")
    print(df[["runtime", "round", "n_datapoints_cpu", "cpu_units_mean",
              "cpu_units_max", "mem_mb_max"]].to_string(index=False))

    # ---------- tabela comparativa dos 3 métodos ----------
    old = pd.read_csv(os.path.join(REPO, "analysis/fase5/fase5_fargate_recursos_novo.csv"))
    old = old[old.cenario == "f3"]
    iso300 = pd.read_csv(os.path.join(REPO, "analysis/fase5/fase5_recursos_fase_isolada.csv"))
    iso300 = iso300[iso300.cenario == "f3"]

    def agg(d):
        g = d.groupby("runtime")
        return pd.DataFrame({
            "cpu_max": g["cpu_units_max"].max(),
            "cpu_mean_of_rounds": g["cpu_units_mean"].mean(),
            "mem_max": g["mem_mb_max"].max(),
            "n_dp_med": g["n_datapoints_cpu"].median(),
        })

    a_old, a_i300, a_i60 = agg(old), agg(iso300), agg(df)
    print("\n" + "=" * 92)
    print("F3 — PICO de CPU (unidades de 1024 = 1 vCPU) e MEM (MB de 2048), 3 métodos")
    print("  [1] contaminada mtime±600 p300 (jul)   [2] fase isolada p300 recon (jul)   "
          "[3] fase isolada p60 exata (set)")
    print("=" * 92)
    hdr = f"{'runtime':15} | {'cpu_max':>21} | {'cpu_mean(rodadas)':>26} | {'mem_max':>21}"
    print(hdr)
    print(f"{'':15} | {'[1]':>6} {'[2]':>6} {'[3]':>6} | {'[1]':>8} {'[2]':>8} {'[3]':>8} | "
          f"{'[1]':>6} {'[2]':>6} {'[3]':>6}")
    print("-" * len(hdr))
    for rt in ("springboot", "quarkus-jvm", "quarkus-native"):
        print(f"{rt:15} | "
              f"{a_old.loc[rt,'cpu_max']:6.0f} {a_i300.loc[rt,'cpu_max']:6.0f} {a_i60.loc[rt,'cpu_max']:6.0f} | "
              f"{a_old.loc[rt,'cpu_mean_of_rounds']:8.0f} {a_i300.loc[rt,'cpu_mean_of_rounds']:8.0f} {a_i60.loc[rt,'cpu_mean_of_rounds']:8.0f} | "
              f"{a_old.loc[rt,'mem_max']:6.0f} {a_i300.loc[rt,'mem_max']:6.0f} {a_i60.loc[rt,'mem_max']:6.0f}")
    print(f"\ndatapoints/rodada (mediana): "
          f"[1]={a_old['n_dp_med'].mean():.0f}  [2]={a_i300['n_dp_med'].mean():.0f}  [3]={a_i60['n_dp_med'].mean():.0f}")

    # por dia (heterogeneidade do springboot)
    print("\n--- fase isolada p60, por rodada (springboot: r1-3 = 02/09, r4-5 = 05/09) ---")
    for _, r in df.sort_values(["runtime", "round"]).iterrows():
        print(f"  {r['runtime']:15} r{int(r['round'])}  "
              f"cpu_mean={r['cpu_units_mean']:6.1f}  cpu_max={r['cpu_units_max']:6.1f}  "
              f"mem_max={r['mem_mb_max']:6.0f}  (n={int(r['n_datapoints_cpu'])})  {r['peak_start_utc'][:10]}")


if __name__ == "__main__":
    main()
