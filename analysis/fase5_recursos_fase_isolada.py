"""
Re-extrai CPU/memoria de container (Fargate) para F1, F2 e F3 usando uma janela
que ISOLA a fase de carga sustentada (hold do F1/F2, peak do F3), em vez da
janela por mtime +/- padding do fase5_analise_estatistica.py (que capturava, em
parte dos casos, o arranque de uma task adjacente).

Fonte: ECS/ContainerInsights, CpuUtilized/MemoryUtilized, dims ClusterName +
TaskDefinitionFamily (mesma de sempre).

Janela por cenario:
  F1 (re-coleta 31/08, analysis/fargate/fase3-f1-rerun/):
     - timestamp EXATO de start/end do k6 vem do meta.json (mesmo relogio).
     - hold = [k6_start + 7s(setup) + 120s(rampup), + 1200s].  period=60 (1min,
       ainda dentro da retencao — coleta de 1 dia atras).
     - reporta tambem "inner" = hold com os primeiros 300s aparados (descarta
       warm-up de JIT/cache que ainda eleva CPU no inicio do hold).

  F2 / F3 (coleta de julho, analysis/fargate/fase3/):
     - NAO ha meta.json. Ancora = evento CloudTrail RunTask (relogio AWS, o mesmo
       das metricas), atribuido a cada (runtime, rodada) por correlacao com o
       mtime do summary.json (1 candidato por rodada, gap == duracao do teste).
     - period=60 ja EXPIROU para julho (retencao 15 dias) -> so period=300 (5min).
     - SUPOSICAO DECLARADA: atraso RunTask -> inicio da carga =
         PRE_K6[runtime] (Fargate provisiona + boot + health-check + truncate + k6 setup)
       calibrado a partir da assinatura de CPU da re-coleta do F1 (RunTask e platô
       de hold ambos em relogio AWS):
         springboot ~105s, quarkus-jvm ~55s, quarkus-native ~50s  (+/- ~40s)
       Nao foi medido diretamente: os logs da coleta de julho nao existem mais e
       o relogio local da maquina do autor esta dessincronizado (NTP off, ~30s
       atras do AWS em 31/08, ~71s em 01/09 -> julho desconhecido).
     - F2 hold  = [RunTask + PRE_K6 + 690s (prewarm 600 + rampup 90), + 1800s]  -> ~6 datapoints @300s
     - F3 peak  = [RunTask + PRE_K6 + 420s (baseline 300 + rampup 120), + 600s]  -> ~2 datapoints @300s  (MARGINAL)

Saida: analysis/fase5/fase5_recursos_fase_isolada.csv  (formato identico a
fase5_fargate_recursos_novo.csv). NAO sobrescreve nenhum CSV antigo.
"""
import json, os, glob, datetime as dt
import numpy as np
import pandas as pd
import boto3

SESSION = boto3.Session(profile_name="pessoal", region_name="us-east-1")
CW = SESSION.client("cloudwatch")

CLUSTER = "order-service-cluster"
CPU_UNITS = 1024
MEM_MB = 2048
FAMILY = {"springboot": "order-service-springboot",
          "quarkus-jvm": "order-service-quarkus-jvm",
          "quarkus-native": "order-service-quarkus-native"}

REPO = os.path.expanduser("~/Programming/ecommerce-tcc")
OUT = os.path.join(REPO, "analysis/fase5/fase5_recursos_fase_isolada.csv")
# Cache de eventos CloudTrail RunTask de julho ([{"t": ISO8601, "fam": runtime}, ...]).
# Extraido uma vez via `aws cloudtrail lookup-events` (retencao ~90 dias). Nao versionado
# (dado -> S3); aponte RUNTASK_CACHE para o arquivo local ou regere do CloudTrail.
RUNTASK_CACHE = os.environ.get(
    "RUNTASK_CACHE", os.path.join(REPO, "analysis/fase5/runtasks_july.json"))

PRE_K6 = {"springboot": 105, "quarkus-jvm": 55, "quarkus-native": 50}


def get_metric(family, metric, start, end, period):
    r = CW.get_metric_statistics(
        Namespace="ECS/ContainerInsights", MetricName=metric,
        Dimensions=[{"Name": "ClusterName", "Value": CLUSTER},
                    {"Name": "TaskDefinitionFamily", "Value": family}],
        StartTime=start, EndTime=end, Period=period, Statistics=["Average", "Maximum"])
    return sorted(r["Datapoints"], key=lambda d: d["Timestamp"])


def stats_row(cenario, runtime, rnd, win_start, win_end, period, note=""):
    fam = FAMILY[runtime]
    cpu = get_metric(fam, "CpuUtilized", win_start - dt.timedelta(seconds=period),
                     win_end + dt.timedelta(seconds=period), period)
    mem = get_metric(fam, "MemoryUtilized", win_start - dt.timedelta(seconds=period),
                     win_end + dt.timedelta(seconds=period), period)
    # datapoint cujo intervalo [T, T+period) cai dentro da janela (midpoint dentro)
    def inside(dp):
        mid = dp["Timestamp"] + dt.timedelta(seconds=period / 2)
        return win_start <= mid <= win_end
    cpu = [d for d in cpu if inside(d)]
    mem = [d for d in mem if inside(d)]
    if not cpu:
        print(f"  [!] {cenario}/{runtime}/r{rnd}: 0 datapoints na janela isolada ({note})")
        return None
    ca = [d["Average"] for d in cpu]; cm = [d["Maximum"] for d in cpu]
    ma = [d["Average"] for d in mem]; mm = [d["Maximum"] for d in mem]
    return {
        "cenario": cenario, "runtime": runtime, "round": rnd,
        "n_datapoints_cpu": len(cpu),
        "cpu_units_mean": float(np.mean(ca)), "cpu_units_max": float(np.max(cm)),
        "cpu_pct_mean": float(np.mean(ca) / CPU_UNITS * 100), "cpu_pct_max": float(np.max(cm) / CPU_UNITS * 100),
        "mem_mb_mean": float(np.mean(ma)) if ma else np.nan, "mem_mb_max": float(np.max(mm)) if mm else np.nan,
        "mem_pct_mean": float(np.mean(ma) / MEM_MB * 100) if ma else np.nan,
        "mem_pct_max": float(np.max(mm) / MEM_MB * 100) if mm else np.nan,
    }


rows = []

# ---------------- F1: meta.json, period=60, hold + inner ----------------
for mp in sorted(glob.glob(os.path.join(REPO, "analysis/fargate/fase3-f1-rerun/*-meta.json"))):
    d = json.load(open(mp))
    rt, rnd = d["runtime"], d["round"]
    k6_start = dt.datetime.fromisoformat(d["start_utc"].replace("Z", "+00:00"))
    hold_start = k6_start + dt.timedelta(seconds=7 + 120)
    hold_end = hold_start + dt.timedelta(seconds=1200)
    r = stats_row("f1", rt, rnd, hold_start, hold_end, 60, "hold completo")
    if r: rows.append(r)
    r2 = stats_row("f1_inner", rt, rnd, hold_start + dt.timedelta(seconds=300), hold_end, 60, "hold sem 1os 5min")
    if r2: rows.append(r2)

# ---------------- F2 / F3: RunTask-ancorado, period=300 ----------------
ev = [(dt.datetime.fromisoformat(x["t"].replace("Z", "+00:00")), x["fam"])
      for x in json.load(open(os.path.abspath(RUNTASK_CACHE)))]
ev.sort()
TEST_DUR = {"f2": 2672, "f3": 1502}
PHASE_OFFSET = {"f2": 690, "f3": 420}
PHASE_DUR = {"f2": 1800, "f3": 600}
BASE = os.path.join(REPO, "analysis/fargate/fase3")

for scen in ("f2", "f3"):
    for rt in FAMILY:
        for rnd in (1, 2, 3, 4, 5):
            sp = f"{BASE}/{scen}-{rt}-r{rnd}-summary.json"
            if not os.path.exists(sp):
                continue
            mt = dt.datetime.fromtimestamp(os.path.getmtime(sp), dt.timezone.utc)
            target = mt - dt.timedelta(seconds=TEST_DUR[scen] + 300)
            cands = [t for (t, f) in ev if f == rt and abs((t - target).total_seconds()) < 1200]
            if not cands:
                print(f"  [!] {scen}/{rt}/r{rnd}: nenhum RunTask correlacionado")
                continue
            runtask = min(cands, key=lambda t: abs((t - target).total_seconds()))
            ph_start = runtask + dt.timedelta(seconds=PRE_K6[rt] + PHASE_OFFSET[scen])
            ph_end = ph_start + dt.timedelta(seconds=PHASE_DUR[scen])
            r = stats_row(scen, rt, rnd, ph_start, ph_end, 300,
                          f"RunTask {runtask:%H:%M:%S} + {PRE_K6[rt]+PHASE_OFFSET[scen]}s")
            if r: rows.append(r)

df = pd.DataFrame(rows)
cols = ["cenario", "runtime", "round", "n_datapoints_cpu", "cpu_units_mean", "cpu_units_max",
        "cpu_pct_mean", "cpu_pct_max", "mem_mb_mean", "mem_mb_max", "mem_pct_mean", "mem_pct_max"]
df[cols].to_csv(OUT, index=False)
print(f"\n[ok] {OUT}  ({len(df)} linhas)")

# ---------------- comparacao pico por runtime ----------------
def peaks(d, label):
    print(f"\n=== {label} ===")
    for (c, rt), g in d.groupby(["cenario", "runtime"]):
        print(f"  {c:9} {rt:15} cpu_units_max={g['cpu_units_max'].max():7.1f} ({g['cpu_units_max'].max()/CPU_UNITS*100:4.1f}%)  "
              f"cpu_units_mean(med rodadas)={g['cpu_units_mean'].mean():6.1f}  "
              f"mem_mb_max={g['mem_mb_max'].max():6.1f}")

peaks(df, "NOVO — fase isolada")

old = pd.read_csv(os.path.join(REPO, "analysis/fase5/fase5_fargate_recursos_novo.csv"))
peaks(old[old.cenario.isin(["f1", "f2", "f3"])], "ANTIGO — janela mtime+-600s (fase5_fargate_recursos_novo.csv)")

f1c = os.path.join(REPO, "analysis/fase5/fase5_f1_corrigido_fargate_recursos.csv")
if os.path.exists(f1c):
    peaks(pd.read_csv(f1c), "F1 (48 iter/s, janela mtime+-600s) — fase5_f1_corrigido_fargate_recursos.csv")
