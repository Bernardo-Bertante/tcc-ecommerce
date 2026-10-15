"""
CPU do RDS (AWS/RDS CPUUtilization, dim DBInstanceIdentifier=order-service-postgres)
por cenario x runtime x rodada, restrita a MESMA janela de carga sustentada ja
usada para o container Fargate (exclui rampas, prewarm, boot, TRUNCATE/repopulate).

Premissa derrubada de 08-known-problems.md ("CPU do RDS nao recuperada por rodada"):
o RDS e instancia unica, a metrica nao precisa de dimensao por rodada -- basta a
janela. E as janelas ja existem:

  F1  (re-coleta 31/08)     meta.json start_utc exato; hold=[start+7+120, +1200]    p60
  F3  (re-coleta 02-05/09)  meta.json, fases com start/end exatos (peak + baseline
                            e recovery como referencia a 48 iter/s)                  p60
  F2-S (10/08)              RunTask do CloudTrail (fase5_f2s_recursos_NOTAS.md s.1),
                            hold=[RT+60+30, RT+60+810], buckets inteiros + guarda de
                            arranque (identico a fase5_recursos_f2s.py)              p300
  F2  (jul/2026)            RunTask de runtasks_july.json atribuido por mtime
                            (identico a fase5_recursos_fase_isolada.py),
                            hold=[RT+PRE_K6+690, +1800]                              p300 se
                            ainda retido; senao p3600 (so se >=50% do bucket e hold,
                            marcado qualidade=p3600_contaminado)
  F3-jul (coleta original)  mesma reconstrucao, peak=[RT+PRE_K6+420, +600]; so p300
                            (suplementar -- o F3 oficial e a re-coleta)

Retencao verificada em 10/09/2026: p60 ok para 31/08 em diante; p300 ok para 10/08 e
13/07 (expira ~14/09!); 06-07/07 so p3600.

Saidas (NAO sobrescreve CSV oficial):
  analysis/fase5/fase5_rds_cpu_por_rodada.csv
  analysis/fase5/fase5_rds_cpu_por_rodada_raw.json   (datapoints brutos -- p300 de julho expira)
"""
import glob, json, os, datetime as dt
import numpy as np
import pandas as pd
import boto3

SESSION = boto3.Session(profile_name="pessoal", region_name="us-east-1")
CW = SESSION.client("cloudwatch")

DB_ID = "order-service-postgres"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "analysis/fase5/fase5_rds_cpu_por_rodada.csv")
OUT_RAW = os.path.join(REPO, "analysis/fase5/fase5_rds_cpu_por_rodada_raw.json")
RUNTASK_CACHE = os.environ.get("RUNTASK_CACHE", os.path.join(REPO, "analysis/fase5/runtasks_july.json"))

UTC = dt.timezone.utc
S = lambda x: dt.timedelta(seconds=x)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
parse = lambda s: dt.datetime.fromisoformat(s[:19]).replace(tzinfo=UTC)

raw = {}


def fetch(metric, start, end, period):
    r = CW.get_metric_statistics(
        Namespace="AWS/RDS", MetricName=metric,
        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": DB_ID}],
        StartTime=start, EndTime=end, Period=period, Statistics=["Average", "Maximum"])
    return sorted(r["Datapoints"], key=lambda d: d["Timestamp"])


def inside(points, ws, we, period):
    """Buckets INTEIRAMENTE contidos em [ws, we]."""
    return [p for p in points if p["Timestamp"] >= ws and p["Timestamp"] + S(period) <= we]


def drop_boot(points, run_task, period):
    """Guarda anti-arranque (so RunTask-ancorados): descarta buckets que tocam [RT-30, RT+180]."""
    if run_task is None:
        return points
    g0, g1 = run_task - S(30), run_task + S(180)
    return [p for p in points if not (p["Timestamp"] < g1 and p["Timestamp"] + S(period) > g0)]


def row(cen, rt, rnd, fase, ws, we, period, fonte, run_task=None, pre_k6_shift=None, extra=None):
    key = f"{cen}/{rt}/r{rnd}/{fase}/p{period}"
    cpu_all = fetch("CPUUtilization", ws - S(900), we + S(900), period)
    con_all = fetch("DatabaseConnections", ws - S(900), we + S(900), period)
    cpu = drop_boot(inside(cpu_all, ws, we, period), run_task, period)
    con = drop_boot(inside(con_all, ws, we, period), run_task, period)
    estavel = ""
    if pre_k6_shift is not None:  # robustez a incerteza de PRE_K6 (+-40s)
        sel = {p["Timestamp"] for p in cpu}
        estavel = all({p["Timestamp"] for p in drop_boot(inside(cpu_all, ws + S(d), we + S(d), period),
                                                          run_task, period)} == sel
                      for d in (-pre_k6_shift, pre_k6_shift))
    raw[key] = [{"t": iso(p["Timestamp"]), "avg": p["Average"], "max": p["Maximum"]} for p in cpu_all]
    if not cpu:
        return None
    r = {
        "cenario": cen, "runtime": rt, "round": rnd, "fase": fase,
        "rds_cpu_mean_pct": float(np.mean([p["Average"] for p in cpu])),
        "rds_cpu_max_pct": float(np.max([p["Maximum"] for p in cpu])),
        "rds_conn_mean": float(np.mean([p["Average"] for p in con])) if con else np.nan,
        "n_datapoints": len(cpu), "period_sec": period,
        "win_start_utc": iso(ws), "win_end_utc": iso(we),
        "run_task_utc": iso(run_task) if run_task else "",
        "fonte_janela": fonte, "estavel_pre_k6": estavel, "qualidade": "ok" if period <= 300 else "",
    }
    r.update(extra or {})
    return r


def hourly_row(cen, rt, rnd, fase, ws, we, run_task, fonte):
    """Fallback p3600: bucket horario de maior sobreposicao com a janela, so se >=50% dele e janela."""
    pts = fetch("CPUUtilization", ws - S(3600), we + S(3600), 3600)
    con = fetch("DatabaseConnections", ws - S(3600), we + S(3600), 3600)
    raw[f"{cen}/{rt}/r{rnd}/{fase}/p3600"] = [{"t": iso(p["Timestamp"]), "avg": p["Average"], "max": p["Maximum"]} for p in pts]
    best, ov = None, 0
    for p in pts:
        o = (min(p["Timestamp"] + S(3600), we) - max(p["Timestamp"], ws)).total_seconds()
        if o > ov:
            best, ov = p, o
    if best is None or ov / 3600 < 0.5:
        return None
    c = next((x for x in con if x["Timestamp"] == best["Timestamp"]), None)
    return {
        "cenario": cen, "runtime": rt, "round": rnd, "fase": fase,
        "rds_cpu_mean_pct": best["Average"], "rds_cpu_max_pct": best["Maximum"],
        "rds_conn_mean": c["Average"] if c else np.nan,
        "n_datapoints": 1, "period_sec": 3600,
        "win_start_utc": iso(ws), "win_end_utc": iso(we), "run_task_utc": iso(run_task),
        "fonte_janela": fonte, "estavel_pre_k6": "",
        "qualidade": f"p3600_contaminado (hold={ov/3600:.0%} do bucket)",
    }


def main():
    rows = []

    # ---------------- F1 / F3: re-coletas com meta.json (p60) ----------------
    metas = []
    for mp in glob.glob(os.path.join(REPO, "analysis/fargate/fase3-f1-rerun/*-meta.json")) + \
              glob.glob(os.path.join(REPO, "analysis/fargate/fase3-f3-rerun/*-meta.json")):
        d = json.load(open(mp))
        d["_start"] = parse(d.get("load_start_utc") or d["start_utc"])
        d["_end"] = parse(d.get("load_end_utc") or d["end_utc"])
        metas.append(d)
    metas.sort(key=lambda d: d["_start"])
    prev_end = None
    for d in metas:
        rt, rnd = d["runtime"], d["round"]
        rest = (d["_start"] - prev_end).total_seconds() if prev_end else np.nan
        prev_end = d["_end"]
        extra = {"descanso_antes_s": rest}
        if d["scenario"].startswith("f1"):
            ws = parse(d["start_utc"]) + S(7 + 120)
            r = row("f1", rt, rnd, "hold", ws, ws + S(1200), 60, "meta.json", extra=extra)
            if r: rows.append(r)
        else:
            for ph in d["phases"]:
                if ph["name"] in ("peak", "baseline", "recovery"):
                    r = row("f3", rt, rnd, ph["name"], parse(ph["start_utc"]), parse(ph["end_utc"]), 60,
                            "meta.json", extra=extra)
                    if r: rows.append(r)

    # ---------------- F2-S: RunTask ja reconstruido (NOTAS s.1), p300 ----------------
    f2s = {
        "springboot": ["10:11:26", "10:27:22", "10:42:35", "10:57:56", "11:13:20"],
        "quarkus-jvm": ["12:29:18", "12:44:20", "12:59:36", "13:14:44", "13:30:29"],
        "quarkus-native": ["14:45:42", "15:00:49", "15:16:03", "15:31:06", "15:46:12"],
    }
    for rt, times in f2s.items():
        for rnd, hms in enumerate(times, 1):
            t = parse(f"2026-08-10T{hms}")
            ws = t + S(60 + 30)
            r = row("f2s", rt, rnd, "hold", ws, ws + S(780), 300, "CloudTrail RunTask (NOTAS F2-S)",
                    run_task=t, pre_k6_shift=40)
            if r: rows.append(r)

    # ---------------- F2 / F3-jul: RunTask de julho atribuido por mtime ----------------
    PRE_K6 = {"springboot": 105, "quarkus-jvm": 55, "quarkus-native": 50}
    TEST_DUR = {"f2": 2672, "f3": 1502}
    OFFSET = {"f2": 690, "f3": 420}
    DUR = {"f2": 1800, "f3": 600}
    ev = sorted((parse(x["t"]), x["fam"]) for x in json.load(open(RUNTASK_CACHE)))
    for scen in ("f2", "f3"):
        for rt in PRE_K6:
            for rnd in range(1, 6):
                sp = os.path.join(REPO, f"analysis/fargate/fase3/{scen}-{rt}-r{rnd}-summary.json")
                if not os.path.exists(sp):
                    continue
                mt = dt.datetime.fromtimestamp(os.path.getmtime(sp), UTC)
                target = mt - S(TEST_DUR[scen] + 300)
                cands = sorted((abs((t - target).total_seconds()), t) for t, f in ev if f == rt)
                if not cands or cands[0][0] > 1200 or (len(cands) > 1 and cands[1][0] < 600):
                    print(f"  [!] {scen}/{rt}/r{rnd}: RunTask ambiguo/ausente")
                    continue
                t = cands[0][1]
                ws = t + S(PRE_K6[rt] + OFFSET[scen])
                we = ws + S(DUR[scen])
                cen = "f2" if scen == "f2" else "f3_jul"
                fase = "hold" if scen == "f2" else "peak"
                fonte = "runtasks_july.json + mtime"
                r = row(cen, rt, rnd, fase, ws, we, 300, fonte, run_task=t, pre_k6_shift=40)
                if r is None and scen == "f2":
                    r = hourly_row(cen, rt, rnd, fase, ws, we, t, fonte)
                if r:
                    rows.append(r)
                else:
                    print(f"  [-] {cen}/{rt}/r{rnd}: sem dado retido utilizavel (RunTask {iso(t)})")

    df = pd.DataFrame(rows)
    cols = ["cenario", "runtime", "round", "fase", "rds_cpu_mean_pct", "rds_cpu_max_pct", "rds_conn_mean",
            "n_datapoints", "period_sec", "qualidade", "win_start_utc", "win_end_utc", "run_task_utc",
            "fonte_janela", "estavel_pre_k6", "descanso_antes_s"]
    df = df.sort_values(["cenario", "fase", "runtime", "round"])[cols]
    df.to_csv(OUT, index=False)
    json.dump(raw, open(OUT_RAW, "w"), indent=1)
    print(f"[ok] {OUT} ({len(df)} linhas)\n[ok] {OUT_RAW}")

    pd.set_option("display.width", 200)
    print(df[cols[:10]].to_string(index=False))

    # ---------------- por runtime dentro do cenario ----------------
    try:
        from scipy.stats import kruskal
    except ImportError:
        kruskal = None
    good = df[df.qualidade == "ok"]
    print("\n=== CPU media do RDS (%) por cenario/fase x runtime (so qualidade=ok) ===")
    for (c, f), g in good.groupby(["cenario", "fase"], sort=False):
        line = f"{c:7} {f:9}"
        groups = []
        for rt in ("springboot", "quarkus-jvm", "quarkus-native"):
            x = g[g.runtime == rt].rds_cpu_mean_pct
            groups.append(x.values)
            line += f" | {rt:14} {x.mean():5.1f} ±{x.std():4.1f} (n={len(x)}, pico {g[g.runtime == rt].rds_cpu_max_pct.max():5.1f})" if len(x) else f" | {rt:14}   --"
        if kruskal and all(len(v) >= 2 for v in groups):
            line += f" | KW p={kruskal(*groups).pvalue:.3f}"
        print(line)


if __name__ == "__main__":
    main()
