"""
Repouso REAL do RDS entre execuções de carga nos cenários Fargate oficiais (F1, F2, F3).

Repouso = início da carga k6 seguinte - fim da carga k6 anterior (intervalo sem carga
no RDS; inclui stop-task, run-task, health, TRUNCATE e init do k6 da rodada seguinte).

  F1 re-coleta (31/08)      meta.json: start_utc/end_utc (relógio local; envolvem o ssh
                            do k6 inteiro, então o repouso real é ~igual ou um pouco maior)
  F3 re-coleta (02-06/09)   meta.json: load_start_utc/load_end_utc (1º/último Point do k6,
                            relógio do runner — consistente entre si)
  F2/F3 jul (bloco_fargate) analysis/fase5/runtasks_july.json (RunTask do CloudTrail),
                            agrupado em blocos F1->F2->F3; início da carga = RunTask + PRE_K6
                            (mesmas constantes de fase5_rds_cpu_por_rodada.py) — aproximado ±1 min

Uso: python3 analysis/investigacao_repouso_entre_rodadas/repouso_real.py
"""
import glob, json, os, datetime as dt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
p = lambda s: dt.datetime.fromisoformat(s[:19])
S = lambda x: dt.timedelta(seconds=x)


def rerun(folder, k_start, k_end):
    ms = [json.load(open(f)) for f in glob.glob(os.path.join(REPO, "analysis/fargate", folder, "*-meta.json"))]
    ms.sort(key=lambda d: p(d[k_start]))
    print(f"\n== {folder}  (repouso = {k_start}[i] - {k_end}[i-1])")
    prev = None
    for d in ms:
        s, e = p(d[k_start]), p(d[k_end])
        gap = "" if prev is None else f"{(s - prev).total_seconds():7.0f} s"
        print(f"  {d['runtime']:15} r{d['round']}  {d[k_start][:19]} .. {d[k_end][11:19]}  {gap}"
              f"   runner_script blob {d['runner_script']['git_blob_sha'][:10]}")
        prev = e


rerun("fase3-f1-rerun", "start_utc", "end_utc")
rerun("fase3-f3-rerun", "load_start_utc", "load_end_utc")

# ---------------- julho: bloco_fargate.sh (F1 -> F2 -> F3 por runtime/rodada) ----------------
PRE_K6 = {"springboot": 105, "quarkus-jvm": 55, "quarkus-native": 50}
DUR = {"f1": 1440, "f2": 2672, "f3": 1502}
ev = sorted((p(x["t"]), x["fam"]) for x in json.load(open(os.path.join(REPO, "analysis/fase5/runtasks_july.json"))))
# bloco = 3 RunTasks da mesma família com espaçamentos ~F1+overhead (1500-1550 s) e ~F2+overhead (2820-2890 s)
blocks = []
for i in range(len(ev) - 2):
    (a, fa), (b, fb), (c, fc) = ev[i:i + 3]
    if fa == fb == fc and 1490 <= (b - a).total_seconds() <= 1560 and 2800 <= (c - b).total_seconds() <= 2900:
        blocks.append((fa, a, b, c))
print("\n== julho (bloco_fargate.sh) — repouso aproximado do RDS, s")
print(f"  {'runtime':15} {'F1 RunTask':20} {'F1->F2':>7} {'F2->F3':>7} {'bloco ant.->F1':>15}")
prev_f3_end = None
for rt, a, b, c in blocks:
    pre = PRE_K6[rt]
    f1s, f1e = a + S(pre), a + S(pre + DUR["f1"])
    f2s, f2e = b + S(pre), b + S(pre + DUR["f2"])
    f3s, f3e = c + S(pre), c + S(pre + DUR["f3"])
    inter = "" if prev_f3_end is None else f"{(f1s - prev_f3_end).total_seconds() / 60:12.0f} min"
    print(f"  {rt:15} {a.isoformat():20} {(f2s - f1e).total_seconds():7.0f} {(f3s - f2e).total_seconds():7.0f} {inter:>15}")
    prev_f3_end = f3e
