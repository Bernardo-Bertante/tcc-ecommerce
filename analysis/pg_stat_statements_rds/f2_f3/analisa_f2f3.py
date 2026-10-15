#!/usr/bin/env python3
"""Analise da coleta F2/F3 (exploratoria). Uso: python3 analisa_f2f3.py [f2|f3 ...]

Para cada fase gera em resultados/<fase>/:
  metricas_por_rodada.csv   CPU do RDS (EM), CPU dos backends, active_time, exec+plan (pgss), rede, steal
  gap_banco.csv             tabela SB / SB sem validacao / QJ + razoes + fracao do gap (media e faixa das 8 combinacoes)
  latencia_por_rodada.csv   media/mediana/p90/p95/p99 (phase=load) por rodada
  latencia_por_condicao.csv mesmas estatisticas com as 2 replicas agrupadas + fracao do gap + faixa
  latencia_por_endpoint.csv por condicao x operation
  comparacao_oficial.csv    razao SB/QJ da reproducao x fase5_estatistica_descritiva_novo.csv
  serie_por_minuto.csv      por rodada e minuto: CPU total RDS, backends, task (Container Insights), p95/p99, req/s
Nao escreve conclusao interpretativa.
"""
import csv, glob, gzip, itertools, json, sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import numpy as np
import boto3

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from compara import classifica  # mesmo classificador das coletas 1-3

S = boto3.Session(profile_name="pessoal", region_name="us-east-1")
logs, cw = S.client("logs"), S.client("cloudwatch")
RID = "db-3RAGZYSCAEFJGZZUFJGPCW643U"            # DbiResourceId de pgss-f2f3-postgres
CLUSTER = "pgss-f2f3-cluster"
CONDS = ["springboot", "springboot-noval", "quarkus-jvm"]
ROT = {"springboot": "SB", "springboot-noval": "SB sem validação", "quarkus-jvm": "QJ"}
OFICIAL = AQUI.parent.parent / "fase5" / "fase5_estatistica_descritiva_novo.csv"
PCT = [("media", None), ("mediana", 50), ("p90", 90), ("p95", 95), ("p99", 99)]


def rodadas(fase):
    out = []
    for d in sorted(glob.glob(str(AQUI / "dados" / fase / "r*"))):
        d = Path(d); m = json.load(open(d / "meta.json"))
        out.append(dict(dir=d, pos=m["posicao"], cond=m["runtime"], a=m["epoch_inicio"], b=m["epoch_fim"]))
    return sorted(out, key=lambda r: r["pos"])


def em_eventos(a, b):
    tok = None
    while True:
        kw = dict(logGroupName="RDSOSMetrics", logStreamNames=[RID], startTime=int(a * 1000), endTime=int(b * 1000))
        if tok: kw["nextToken"] = tok
        r = logs.filter_log_events(**kw)
        for e in r["events"]: yield json.loads(e["message"])
        tok = r.get("nextToken")
        if not tok: break


def task_cpu_por_minuto(cond, a, b):
    """Container Insights: CpuUtilized (unidades de CPU, 1024 = 1 vCPU) por minuto da familia."""
    fam = {"springboot": "pgss-f2f3-springboot", "springboot-noval": "pgss-f2f3-springboot-noval",
           "quarkus-jvm": "pgss-f2f3-quarkus-jvm"}[cond]
    r = cw.get_metric_data(MetricDataQueries=[{"Id": "c", "MetricStat": {"Metric": {
        "Namespace": "ECS/ContainerInsights", "MetricName": "CpuUtilized",
        "Dimensions": [{"Name": "ClusterName", "Value": CLUSTER}, {"Name": "TaskDefinitionFamily", "Value": fam}]},
        "Period": 60, "Stat": "Average"}}], StartTime=int(a) - 60, EndTime=int(b) + 60)
    res = r["MetricDataResults"][0]
    return {int(t.timestamp()) // 60: v for t, v in zip(res["Timestamps"], res["Values"])}


def pgss(d):
    tot = defaultdict(float); por_op = defaultdict(lambda: defaultdict(float))
    for r in csv.DictReader(open(d / "pg_stat_statements.csv")):
        op = classifica(r["query"])
        for k in ("calls", "total_exec_time_ms", "total_plan_time_ms", "shared_blks_hit"):
            v = float(r[k] or 0); tot[k] += v; por_op[op][k] += v
    return tot, por_op


def db_delta(d):
    cols = ("epoch numbackends xact_commit xact_rollback blks_read blks_hit tup_returned tup_fetched tup_inserted "
            "tup_updated tup_deleted session_time active_time idle_in_tx_time sessions sa sf sk").split()
    a, b = [dict(zip(cols, map(float, l.split("\t")))) for l in open(d / "pg_stat_database.tsv").read().splitlines() if l.strip()]
    dt = b["epoch"] - a["epoch"]
    return dict(active_ms_s=(b["active_time"] - a["active_time"]) / dt, xact_commit=b["xact_commit"] - a["xact_commit"])


def latencias(d, fases=("load",)):
    """(duracao_ms, operation, epoch_ms). fases=("load",) = definicao da coleta 3 ({phase:load});
    fases=None = todas as requisicoes, a definicao dos *-latency.json oficiais (n = http_reqs)."""
    dur, op, ts = [], [], []
    with gzip.open(d / "requests.csv.gz", "rt") as fh:
        for r in csv.DictReader(fh):
            if fases is not None and r["phase"] not in fases: continue
            dur.append(float(r["duracao_ms"])); op.append(r["operation"]); ts.append(int(r["epoch_ms"]))
    return np.array(dur), np.array(op), np.array(ts)


def estat(x):
    return {n: (float(np.mean(x)) if p is None else float(np.percentile(x, p))) for n, p in PCT} | {"n": int(len(x))}


def fracao(sb, nv, qj):
    return (sb - nv) / (sb - qj) if sb != qj else float("nan")


def faixa_fracoes(vals):
    """vals[cond] = [replica1, replica2] -> fracoes das 8 combinacoes."""
    return [fracao(s, n, q) for s, n, q in itertools.product(vals["springboot"], vals["springboot-noval"], vals["quarkus-jvm"])]


def escreve(path, linhas):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)


def analisa(fase):
    R = rodadas(fase); out = AQUI / "resultados" / fase
    print(f"\n{'=' * 30} {fase.upper()} ({len(R)} rodadas) {'=' * 30}")
    met, lat_rod, serie = [], [], []
    lat_pool = defaultdict(list); lat_todas = defaultdict(list); lat_op = defaultdict(lambda: defaultdict(list))
    for r in R:
        d = r["dir"]
        cpu, back, steal, rx, tx = [], [], [], [], []
        porm = defaultdict(lambda: defaultdict(list))
        for j in em_eventos(r["a"], r["b"]):
            c = j["cpuUtilization"]
            ba = sum(p.get("cpuUsedPc", 0) for p in j.get("processList", []) if "orderuser orderdb" in p.get("name", ""))
            cpu.append(c["total"]); steal.append(c["steal"]); back.append(ba)
            for n in j.get("network", []): rx.append(n.get("rx", 0)); tx.append(n.get("tx", 0))
            m = int((datetime.fromisoformat(j["timestamp"].replace("Z", "+00:00")).timestamp() - r["a"]) // 60)
            porm[m]["cpu"].append(c["total"]); porm[m]["back"].append(ba)
        tcpu = task_cpu_por_minuto(r["cond"], r["a"], r["b"])
        tot, _ = pgss(d); db = db_delta(d)
        dur, op, ts = latencias(d)
        lat_todas[r["cond"]].append(latencias(d, None)[0])
        st = estat(dur)
        lat_rod.append(dict(fase=fase, pos=r["pos"], cond=r["cond"], **{k: round(v, 3) for k, v in st.items()}))
        lat_pool[r["cond"]].append(dur)
        for o in np.unique(op): lat_op[r["cond"]][o].append(dur[op == o])
        mins = ((ts / 1000 - r["a"]) // 60).astype(int)
        for m in sorted(set(porm) | set(np.unique(mins))):
            x = dur[mins == m]
            serie.append(dict(fase=fase, pos=r["pos"], cond=r["cond"], minuto=m,
                              cpu_rds=round(float(np.mean(porm[m]["cpu"])), 2) if porm[m]["cpu"] else "",
                              cpu_backends=round(float(np.mean(porm[m]["back"])), 2) if porm[m]["back"] else "",
                              cpu_task_unid=round(tcpu.get(int(r["a"] // 60) + m, float("nan")), 1),
                              req_s=round(len(x) / 60, 1), p95=round(float(np.percentile(x, 95)), 1) if len(x) else "",
                              p99=round(float(np.percentile(x, 99)), 1) if len(x) else "",
                              summary_p95=round(float(np.percentile(x[op[mins == m] == "get_summary"], 95)), 1) if (op[mins == m] == "get_summary").any() else ""))
        met.append(dict(fase=fase, pos=r["pos"], cond=r["cond"], cpu_rds=float(np.mean(cpu)), cpu_backends=float(np.mean(back)),
                        active_ms_s=db["active_ms_s"], exec_plan_ms=tot["total_exec_time_ms"] + tot["total_plan_time_ms"],
                        calls=tot["calls"], xact_commit=db["xact_commit"], steal=float(np.mean(steal)),
                        cpu_task_media_unid=float(np.nanmean(list(tcpu.values()))) if tcpu else float("nan"),
                        cpu_task_max_min_unid=float(np.nanmax(list(tcpu.values()))) if tcpu else float("nan"),
                        rede_rx=float(np.mean(rx)), rede_tx=float(np.mean(tx)), n_req_load=st["n"]))
    escreve(out / "metricas_por_rodada.csv", [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()} for m in met])
    escreve(out / "latencia_por_rodada.csv", lat_rod)
    escreve(out / "serie_por_minuto.csv", serie)

    print(f"\nPOR RODADA{'':<14}{'CPU RDS':>8}{'backends':>9}{'active':>8}{'exec+plan':>11}{'calls':>9}{'steal':>6}{'task med':>9}{'task max':>9}"
          f"{'lat med':>8}{'p95':>8}{'p99':>9}")
    for m, l in zip(met, lat_rod):
        print(f"r{m['pos']} {m['cond']:<20}{m['cpu_rds']:>8.2f}{m['cpu_backends']:>9.2f}{m['active_ms_s']:>8.1f}{m['exec_plan_ms']:>11.0f}"
              f"{m['calls']:>9.0f}{m['steal']:>6.2f}{m['cpu_task_media_unid']:>9.0f}{m['cpu_task_max_min_unid']:>9.0f}"
              f"{l['media']:>8.2f}{l['p95']:>8.1f}{l['p99']:>9.1f}")

    # tabela de banco no formato da coleta 3
    gap = []
    print(f"\nBANCO (média das 2 réplicas){'':<6}{'SB':>10}{'SB s/val':>10}{'QJ':>10}{'SB/QJ':>8}{'s/val/QJ':>9}{'fração':>8}   faixa 8 combinações")
    for k, nome in [("cpu_rds", "CPU total do RDS (%)"), ("cpu_backends", "CPU dos backends (%)"),
                    ("active_ms_s", "active_time (ms/s)"), ("exec_plan_ms", "exec+plan pgss (ms)")]:
        vals = {c: [m[k] for m in met if m["cond"] == c] for c in CONDS}
        md = {c: float(np.mean(v)) for c, v in vals.items()}
        fr = fracao(md["springboot"], md["springboot-noval"], md["quarkus-jvm"]); fx = faixa_fracoes(vals)
        gap.append(dict(medida=nome, sb=md["springboot"], sb_noval=md["springboot-noval"], qj=md["quarkus-jvm"],
                        sb_qj=md["springboot"] / md["quarkus-jvm"], noval_qj=md["springboot-noval"] / md["quarkus-jvm"],
                        fracao=fr, fracao_min=min(fx), fracao_max=max(fx),
                        sb_r=vals["springboot"], noval_r=vals["springboot-noval"], qj_r=vals["quarkus-jvm"]))
        print(f"{nome:<34}{md['springboot']:>10.2f}{md['springboot-noval']:>10.2f}{md['quarkus-jvm']:>10.2f}"
              f"{md['springboot'] / md['quarkus-jvm']:>8.3f}{md['springboot-noval'] / md['quarkus-jvm']:>9.3f}{100 * fr:>7.0f}%"
              f"   {100 * min(fx):.0f}%–{100 * max(fx):.0f}%   réplicas SB {['%.2f' % v for v in vals['springboot']]} "
              f"s/val {['%.2f' % v for v in vals['springboot-noval']]} QJ {['%.2f' % v for v in vals['quarkus-jvm']]}")
    escreve(out / "gap_banco.csv", [{k: (json.dumps([round(x, 3) for x in v]) if isinstance(v, list) else round(v, 4) if isinstance(v, float) else v)
                                     for k, v in g.items()} for g in gap])

    # latencia agrupada por condicao
    pool = {c: estat(np.concatenate(lat_pool[c])) for c in CONDS}
    lc = []
    print(f"\nLATÊNCIA phase=load, réplicas agrupadas (ms){'':<0}{'SB':>9}{'SB s/val':>10}{'QJ':>9}{'SB/QJ':>8}{'s/val/QJ':>9}{'fração':>8}   faixa 8 combinações")
    for n, _ in PCT:
        vals = {c: [l[n] for l in lat_rod if l["cond"] == c] for c in CONDS}
        fx = faixa_fracoes(vals); sb, nv, qj = pool["springboot"][n], pool["springboot-noval"][n], pool["quarkus-jvm"][n]
        lc.append(dict(estatistica=n, sb=sb, sb_noval=nv, qj=qj, sb_qj=sb / qj, noval_qj=nv / qj, fracao=fracao(sb, nv, qj),
                       fracao_min=min(fx), fracao_max=max(fx), sb_r=vals["springboot"], noval_r=vals["springboot-noval"], qj_r=vals["quarkus-jvm"]))
        print(f"{n:<45}{sb:>9.2f}{nv:>10.2f}{qj:>9.2f}{sb / qj:>8.3f}{nv / qj:>9.3f}{100 * fracao(sb, nv, qj):>7.0f}%   "
              f"{100 * min(fx):.0f}%–{100 * max(fx):.0f}%   SB {['%.1f' % v for v in vals['springboot']]} s/val {['%.1f' % v for v in vals['springboot-noval']]} QJ {['%.1f' % v for v in vals['quarkus-jvm']]}")
    escreve(out / "latencia_por_condicao.csv", [{k: (json.dumps([round(x, 3) for x in v]) if isinstance(v, list) else round(v, 4) if isinstance(v, float) else v)
                                                 for k, v in l.items()} for l in lc])

    # por endpoint
    le = []
    ops = sorted({o for c in CONDS for o in lat_op[c]})
    print(f"\nPOR ENDPOINT (réplicas agrupadas){'':<4}" + "".join(f"{ROT[c] + ' p50/p95/p99':>34}" for c in CONDS))
    for o in ops:
        linha = f"{o:<37}"
        for c in CONDS:
            x = np.concatenate(lat_op[c][o]) if lat_op[c][o] else np.array([])
            if not len(x): linha += f"{'-':>34}"; continue
            e = estat(x); le.append(dict(fase=fase, cond=c, operation=o, **{k: round(v, 3) for k, v in e.items()}))
            linha += f"{e['mediana']:>12.1f}{e['p95']:>11.1f}{e['p99']:>11.1f}"
        print(linha)
    escreve(out / "latencia_por_endpoint.csv", le)

    # comparacao com o oficial
    of = {r["runtime"]: r for r in csv.DictReader(open(OFICIAL)) if r["cenario"] == fase}
    # mesma definicao do oficial: todas as requisicoes (setup, warmup, auxiliary, load)
    todas = {c: estat(np.concatenate(lat_todas[c])) for c in CONDS}
    comp = []
    print(f"\nSB/QJ: reprodução × oficial ({OFICIAL.name}, cenário {fase})")
    for n, col in [("media", "mean"), ("mediana", "median"), ("p90", "p90"), ("p95", "p95"), ("p99", "p99")]:
        o_sb, o_qj = float(of["springboot"][col]), float(of["quarkus-jvm"][col])
        rs, rq = todas["springboot"][n], todas["quarkus-jvm"][n]
        comp.append(dict(estatistica=n, rep_sb=rs, rep_qj=rq, rep_razao=rs / rq,
                         rep_razao_load=pool["springboot"][n] / pool["quarkus-jvm"][n], of_sb=o_sb, of_qj=o_qj, of_razao=o_sb / o_qj,
                         rep_n_sb=todas["springboot"]["n"], of_n_sb=int(of["springboot"]["n"])))
        print(f"  {n:<8} reprodução (todas) SB {rs:>8.2f} QJ {rq:>8.2f} razão {rs / rq:>6.2f} [phase=load {pool['springboot'][n] / pool['quarkus-jvm'][n]:>5.2f}]"
              f"   |  oficial SB {o_sb:>8.2f} QJ {o_qj:>8.2f} razão {o_sb / o_qj:>6.2f}")
    escreve(out / "comparacao_oficial.csv", [{k: round(v, 4) if isinstance(v, float) else v for k, v in c.items()} for c in comp])


if __name__ == "__main__":
    for f in (sys.argv[1:] or ["f2", "f3"]):
        analisa(f)
