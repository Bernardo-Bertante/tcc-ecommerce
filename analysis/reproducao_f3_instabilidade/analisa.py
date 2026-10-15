#!/usr/bin/env python3
"""Análise cruzada por minuto da reprodução exploratória do F3 (NÃO é resultado formal do TCC).

Uso:  RUN_ID=dia2 python3 analisa.py [rotulo ...]   (RUN_ID vazio/dia1 = runner_out/ do dia 1)
      Saídas com sufixo _<RUN_ID> (dia 1 sem sufixo).

1. Sincroniza runner_out/ do S3 (o runner envia cada rodada ao terminar).
2. Para cada rodada, monta uma tabela minuto a minuto (minuto 0 = início da carga) cruzando:
   latência k6 (requests.csv.gz) · log de GC (CloudWatch Logs da task) · Enhanced Monitoring do RDS
   (cpu, steal, wait, load) · Performance Insights (db.load por wait event) · CloudWatch AWS/RDS e
   ECS/ContainerInsights (1 min) · pool R2DBC (actuator) · pg_stat_activity · sonda TCP · VPC Flow
   Logs da ENI da task (bytes/pacotes com o RDS, flags TCP) · checkpoints/autovacuum no log do PG.
Saídas: minuto_a_minuto.csv, resumo_rodadas.csv, eventos_pg.csv, pi_wait_events.csv.
"""
import csv, datetime as dt, gzip, json, os, re, subprocess, sys, time
from collections import defaultdict

import boto3
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_ID = os.environ.get("RUN_ID", "dia1")
_pref = "runner_out" if RUN_ID == "dia1" else f"runner_out_{RUN_ID}"
SUF = "" if RUN_ID == "dia1" else f"_{RUN_ID}"
OUT = os.path.join(HERE, _pref)
S3 = f"s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/reproducao_f3_instabilidade/{_pref}/"
DBI = "db-6YS6HH4RVDLLF3GYEWRKEPPNEA"
RDS_ID = "repro-f3-postgres"
RDS_IP = "172.31.73.185"
ses = boto3.Session(profile_name="pessoal", region_name="us-east-1")
_cfg = __import__("botocore.config", fromlist=["Config"]).Config(retries={"max_attempts": 10, "mode": "adaptive"})
logs, cw, pi = ses.client("logs", config=_cfg), ses.client("cloudwatch", config=_cfg), ses.client("pi", config=_cfg)
LOAD_MIN = 25  # 5 + 2 + 10 + 2 + 5 + 1


def ts(s):
    m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?Z$", s)
    return dt.datetime.fromisoformat(m.group(1) + "+00:00").timestamp() + (float("0." + m.group(2)) if m.group(2) else 0)


def fetch_events(group, start, end, stream=None, pattern=None):
    kw = dict(logGroupName=group, startTime=int(start * 1000), endTime=int(end * 1000))
    if stream:
        kw["logStreamNames"] = [stream]
    if pattern:
        kw["filterPattern"] = pattern
    # CloudWatch Logs devolve ServiceUnavailable esporádico; insiste antes de derrubar a análise
    for tentativa in range(6):
        try:
            for page in logs.get_paginator("filter_log_events").paginate(**kw):
                yield from page["events"]
            return
        except Exception as exc:
            if tentativa == 5:
                raise
            print(f"  {group}: {type(exc).__name__} — nova tentativa em {10*(tentativa+1)}s", file=sys.stderr)
            time.sleep(10 * (tentativa + 1))


def minute_of(t, t0):
    return int((t - t0) // 60)


def p(a, q):
    return float(np.percentile(a, q)) if len(a) else np.nan


def analisa_rodada(tag):
    d = os.path.join(OUT, tag)
    meta = json.load(open(os.path.join(d, "meta.json")))
    timing = json.load(open(os.path.join(d, "timing.json")))
    task = json.load(open(os.path.join(d, "task_running.json")))["tasks"][0]
    tid = task["taskArn"].rsplit("/", 1)[-1]
    eni = next(x["value"] for x in task["attachments"][0]["details"] if x["name"] == "networkInterfaceId")
    rt = "springboot" if "repro-f3-springboot" in task["taskDefinitionArn"] else "quarkus-jvm"
    t0, t1 = ts(timing["load_start_utc"]), ts(timing["load_end_utc"])
    rows = defaultdict(dict)

    # --- latência k6 (só fase de carga) ---
    rq = pd.read_csv(os.path.join(d, "requests.csv.gz"))
    rq = rq[rq.phase.isin(["load", "auxiliary"])]
    rq["m"] = ((rq.epoch_s - t0) // 60).astype(int)
    for m, g in rq.groupby("m"):
        rows[m].update(n=len(g), p50=p(g.ms, 50), p95=p(g.ms, 95), p99=p(g.ms, 99), max=g.ms.max(),
                       pct_gt_1s=100 * (g.ms > 1000).mean(),
                       p95_get_summary=p(g[g.operation == "get_summary"].ms, 95))

    # --- GC (log da task no CloudWatch) ---
    stream = f"ecs/order-service-{rt}/{tid}"
    pause = re.compile(r"^\[([^\]]+)\].*\[gc\s*\] GC\(\d+\) Pause (\S+).* ([\d.]+)ms$")
    sp = re.compile(r"^\[([^\]]+)\].*\[safepoint\s*\].*Total: (\d+) ns")
    gc = defaultdict(list); sfp = defaultdict(list); full = defaultdict(int)
    # filtra no servidor: só linhas de pausa e de safepoint (o -Xlog:gc* gera ~10x mais linhas)
    for e in fetch_events(f"/ecs/repro-f3-{rt}", t0 - 60, t1 + 120, stream=stream, pattern="?Pause ?Safepoint"):
        msg = e["message"]
        mm = pause.match(msg)
        if mm:
            t = dt.datetime.strptime(mm.group(1), "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
            gc[minute_of(t, t0)].append(float(mm.group(3)))
            if mm.group(2) == "Full":
                full[minute_of(t, t0)] += 1
            continue
        ms = sp.match(msg)
        if ms:
            t = dt.datetime.strptime(ms.group(1), "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
            sfp[minute_of(t, t0)].append(int(ms.group(2)) / 1e6)
    for m in set(gc) | set(sfp):
        rows[m].update(gc_n=len(gc[m]), gc_total_ms=sum(gc[m]), gc_max_ms=max(gc[m], default=0),
                       gc_full=full[m], safepoint_max_ms=max(sfp[m], default=0))

    # --- Enhanced Monitoring (1 s) ---
    em = defaultdict(lambda: defaultdict(list))
    for e in fetch_events("RDSOSMetrics", t0, t1, stream=DBI):
        j = json.loads(e["message"])
        t = ts(j["timestamp"])
        c = j["cpuUtilization"]
        m = minute_of(t, t0)
        for k in ("total", "steal", "wait", "user", "system"):
            em[m][k].append(c[k])
        em[m]["load1"].append(j["loadAverageMinute"]["one"])
        for dk in j.get("diskIO", []):
            if "await" in dk:
                em[m]["disk_await"].append(dk["await"])
    for m, v in em.items():
        rows[m].update(rds_cpu_mean=np.mean(v["total"]), rds_cpu_max=max(v["total"]),
                       rds_steal_mean=np.mean(v["steal"]), rds_steal_max=max(v["steal"]),
                       rds_iowait_mean=np.mean(v["wait"]), rds_load1=np.mean(v["load1"]),
                       rds_disk_await_max=max(v["disk_await"], default=np.nan))

    # --- Performance Insights: db.load por wait event (60 s) ---
    pir = pi.get_resource_metrics(
        ServiceType="RDS", Identifier=DBI, PeriodInSeconds=60,
        StartTime=dt.datetime.fromtimestamp(t0 // 60 * 60, dt.timezone.utc),
        EndTime=dt.datetime.fromtimestamp(t1 // 60 * 60 + 60, dt.timezone.utc),
        MetricQueries=[{"Metric": "db.load.avg", "GroupBy": {"Group": "db.wait_event", "Limit": 10}}])
    pi_rows = []
    for ml in pir["MetricList"]:
        name = (ml["Key"].get("Dimensions") or {}).get("db.wait_event.name", "TOTAL")
        typ = (ml["Key"].get("Dimensions") or {}).get("db.wait_event.type", "")
        for dp in ml["DataPoints"]:
            if "Value" not in dp:
                continue
            m = minute_of(dp["Timestamp"].timestamp(), t0)
            pi_rows.append(dict(rodada=tag, minuto=m, wait_type=typ, wait_event=name, aas=dp["Value"]))
            if name == "TOTAL":
                rows[m]["pi_aas_total"] = dp["Value"]
            elif name == "CPU":
                rows[m]["pi_aas_cpu"] = dp["Value"]
    wt = defaultdict(float)
    for r in pi_rows:
        if r["wait_event"] not in ("TOTAL", "CPU"):
            wt[(r["minuto"])] += r["aas"]
    for m, v in wt.items():
        rows[m]["pi_aas_espera_nao_cpu"] = v

    # --- CloudWatch 1 min ---
    def cwq(ns, metric, dims, key, stat="Average"):
        r = cw.get_metric_statistics(Namespace=ns, MetricName=metric, Dimensions=dims, Period=60, Statistics=[stat],
                                     StartTime=dt.datetime.fromtimestamp(t0 - 60, dt.timezone.utc),
                                     EndTime=dt.datetime.fromtimestamp(t1 + 60, dt.timezone.utc))
        for dp in r["Datapoints"]:
            rows[minute_of(dp["Timestamp"].timestamp() + 30, t0)][key] = dp[stat]
    rdsd = [{"Name": "DBInstanceIdentifier", "Value": RDS_ID}]
    cwq("AWS/RDS", "CPUUtilization", rdsd, "cw_rds_cpu")
    cwq("AWS/RDS", "ReadLatency", rdsd, "cw_rds_read_lat_s")
    cwq("AWS/RDS", "WriteLatency", rdsd, "cw_rds_write_lat_s")
    cwq("AWS/RDS", "DiskQueueDepth", rdsd, "cw_rds_diskq")
    cwq("AWS/RDS", "CPUCreditBalance", rdsd, "cw_rds_credit")
    cwq("AWS/RDS", "CPUSurplusCreditBalance", rdsd, "cw_rds_surplus")
    cwq("ECS/ContainerInsights", "CpuUtilized",
        [{"Name": "ClusterName", "Value": "repro-f3-cluster"}, {"Name": "TaskDefinitionFamily", "Value": f"repro-f3-{rt}"}],
        "task_cpu_units")
    cwq("ECS/ContainerInsights", "MemoryUtilized",
        [{"Name": "ClusterName", "Value": "repro-f3-cluster"}, {"Name": "TaskDefinitionFamily", "Value": f"repro-f3-{rt}"}],
        "task_mem_mb")

    # --- métricas da app (5 s) ---
    am = defaultdict(lambda: defaultdict(list))
    for line in open(os.path.join(d, "app_metrics.tsv")):
        f = line.rstrip("\n").split("\t")
        if rt == "springboot" and len(f) == 3 and f[2] not in ("NA", ""):
            am[minute_of(float(f[0]), t0)][f[1]].append(float(f[2]))
        elif rt != "springboot" and len(f) == 2:
            k, _, v = f[1].rpartition(" ")
            try:
                am[minute_of(float(f[0]), t0)][k.split("{")[0]].append(float(v))
            except ValueError:
                pass
    for m, v in am.items():
        for k, xs in v.items():
            if k in ("r2dbc.pool.pending", "r2dbc.pool.acquired"):
                rows[m][k.replace(".", "_") + "_max"] = max(xs)
                rows[m][k.replace(".", "_") + "_mean"] = np.mean(xs)
            elif k in ("process.cpu.usage", "process_cpu_usage", "system.load.average.1m", "system_load_average_1m"):
                rows[m]["app_" + k.replace(".", "_")] = np.mean(xs)

    # --- pg_stat_activity (5 s): sessões ativas por espera ---
    pa = defaultdict(lambda: defaultdict(list))
    for line in open(os.path.join(d, "pg_activity.tsv")):
        f = line.rstrip("\n").split("\t")
        if len(f) != 5:
            continue
        t, typ, ev, st, n = float(f[0]), f[1], f[2], f[3], float(f[4])
        m = minute_of(t, t0)
        if typ == "n_live_tup" and ev == "orders":
            rows[m]["orders_rows"] = n
        elif st == "active":
            pa[m][(t, "espera" if typ not in ("CPU/none",) else "cpu")].append(n)
    for m, v in pa.items():
        per_t = defaultdict(lambda: {"espera": 0, "cpu": 0})
        for (t, k), ns in v.items():
            per_t[t][k] += sum(ns)
        rows[m]["pg_active_cpu_mean"] = np.mean([x["cpu"] for x in per_t.values()])
        rows[m]["pg_active_wait_mean"] = np.mean([x["espera"] for x in per_t.values()])

    # --- sonda TCP (1 s) ---
    tp = defaultdict(lambda: defaultdict(list))
    for line in open(os.path.join(d, "tcp_probe.tsv")):
        t, name, v = line.split("\t")
        if float(v) >= 0:
            tp[minute_of(float(t), t0)][name].append(float(v))
    for m, v in tp.items():
        for name, xs in v.items():
            rows[m][f"tcp_{name}_p50_ms"] = p(xs, 50)
            rows[m][f"tcp_{name}_max_ms"] = max(xs)

    # --- VPC Flow Logs na ENI da task: tráfego com o RDS ---
    fl = defaultdict(lambda: defaultdict(float))
    for e in fetch_events("/repro-f3/vpc-flow-logs", t0 - 120, t1 + 600, stream=f"{eni}-all"):
        f = e["message"].split()
        if len(f) < 18 or f[13] != "OK":
            continue
        src, dst, pk, by, start, flags = f[3], f[4], int(f[8]), int(f[9]), int(f[10]), int(f[17])
        if RDS_IP not in (src, dst):
            continue
        m = minute_of(start, t0)
        dirn = "para_rds" if dst == RDS_IP else "do_rds"
        fl[m][f"fl_{dirn}_bytes"] += by
        fl[m][f"fl_{dirn}_pkts"] += pk
        if flags & 4:
            fl[m]["fl_rst_flows"] += 1
        if flags & 2 and not flags & 16:
            fl[m]["fl_syn_only_flows"] += 1
    for m, v in fl.items():
        rows[m].update(v)

    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    df = df[(df.index >= -1) & (df.index <= LOAD_MIN)]
    df.insert(0, "minuto", df.index)
    df.insert(0, "rodada", tag)
    df["fase"] = pd.cut(df.minuto, [-2, 4.99, 6.99, 16.99, 18.99, 23.99, 99],
                        labels=["base48", "rampa", "pico240", "rampa", "rec48", "descida"], ordered=False)

    # --- eventos do Postgres (checkpoint/autovacuum/autoanalyze) na janela ---
    ev = []
    for e in fetch_events(f"/aws/rds/instance/{RDS_ID}/postgresql", t0 - 300, t1 + 60):
        msg = e["message"]
        if re.search(r"checkpoint|automatic (vacuum|analyze)|temporary file|deadlock|lock", msg):
            ev.append(dict(rodada=tag, minuto=round((e["timestamp"] / 1000 - t0) / 60, 2), msg=msg[:300]))
    return df, pi_rows, ev, dict(rodada=tag, task_id=tid, task_az=task.get("availabilityZone"), eni=eni,
                                 load_start=timing["load_start_utc"])


def main():
    subprocess.run(["aws", "s3", "sync", "--quiet", "--profile", "pessoal", S3, OUT], check=True)
    tags = sys.argv[1:] or sorted(x for x in os.listdir(OUT) if x.startswith("f3-") and os.path.exists(os.path.join(OUT, x, "DONE" if RUN_ID != "dia1" else "timing.json")))
    dfs, pis, evs, infos = [], [], [], []
    falhas = []
    for t in tags:
        print("analisando", t, file=sys.stderr)
        try:
            df, pr, ev, info = analisa_rodada(t)
        except Exception:
            import traceback; traceback.print_exc()
            falhas.append(t); continue
        dfs.append(df); pis += pr; evs += ev; infos.append(info)
    if falhas:
        print("RODADAS QUE FALHARAM NA ANALISE:", falhas, file=sys.stderr)
    mm = pd.concat(dfs)
    mm.to_csv(os.path.join(HERE, f"minuto_a_minuto{SUF}.csv"), index=False, float_format="%.4g")
    pd.DataFrame(pis).to_csv(os.path.join(HERE, f"pi_wait_events{SUF}.csv"), index=False, float_format="%.4g")
    pd.DataFrame(evs).to_csv(os.path.join(HERE, f"eventos_pg{SUF}.csv"), index=False)
    stp = os.path.join(OUT, "status.tsv")
    st = pd.read_csv(stp, sep="\t") if os.path.exists(stp) else pd.DataFrame({"rotulo": tags})
    st.merge(pd.DataFrame(infos), left_on="rotulo", right_on="rodada", how="left").to_csv(
        os.path.join(HERE, f"resumo_rodadas{SUF}.csv"), index=False)
    cols = [c for c in ["rodada", "minuto", "fase", "p95", "pct_gt_1s", "gc_total_ms", "gc_max_ms", "rds_cpu_mean",
                        "rds_steal_max", "pi_aas_total", "pi_aas_espera_nao_cpu", "r2dbc_pool_pending_max",
                        "task_cpu_units", "tcp_rds_max_ms", "orders_rows"] if c in mm.columns]
    with pd.option_context("display.width", 250, "display.max_rows", 400):
        print(mm[cols].to_string(index=False, float_format=lambda x: f"{x:.3g}"))


if __name__ == "__main__":
    main()
