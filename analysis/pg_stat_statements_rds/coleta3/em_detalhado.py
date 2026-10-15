#!/usr/bin/env python3
"""Enhanced Monitoring detalhado por janela: todos os campos de CPU, rede e CPU por processo.

A pergunta oficial e sobre CPU do RDS; pg_stat_statements mede tempo de parede da execucao.
Este script mede CPU consumida: campos user/system/irq/... e a lista de processos (processList),
somando o cpuUsedPc dos backends 'postgres: orderuser orderdb ...' (os que atendem a app).
"""
import json, statistics as st, glob
from collections import defaultdict
from pathlib import Path
import boto3
AQUI = Path(__file__).resolve().parent
S = boto3.Session(profile_name="pessoal", region_name="us-east-1")
logs = S.client("logs")
rid = S.client("rds").describe_db_instances(DBInstanceIdentifier="repro-f3-postgres")["DBInstances"][0]["DbiResourceId"]

janelas = []
for d in sorted(glob.glob(str(AQUI.parent / "dados" / "f1-*"))):
    m = json.load(open(Path(d) / "meta.json")); janelas.append(("C1 " + m["runtime"], m["epoch_inicio"], m["epoch_fim"]))
for d in sorted(glob.glob(str(AQUI / "dados" / "r*"))):
    m = json.load(open(Path(d) / "meta.json")); janelas.append((f"C3 r{m['posicao']} {m['runtime']}", m["epoch_inicio"], m["epoch_fim"]))

def eventos(a, b):
    tok = None
    while True:
        kw = dict(logGroupName="RDSOSMetrics", logStreamNames=[rid], startTime=int(a*1000), endTime=int(b*1000))
        if tok: kw["nextToken"] = tok
        r = logs.filter_log_events(**kw)
        for e in r["events"]: yield json.loads(e["message"])
        tok = r.get("nextToken")
        if not tok: break

res = []
for rot, a, b in janelas:
    cpu = defaultdict(list); proc = defaultdict(list); rede = defaultdict(list); nb = []
    for j in eventos(a, b):
        for k, v in j["cpuUtilization"].items(): cpu[k].append(v)
        for n in j.get("network", []):
            rede["rx"].append(n.get("rx", 0)); rede["tx"].append(n.get("tx", 0))
        s_app = s_outros = 0.0; n_app = 0
        for p in j.get("processList", []):
            nome = p.get("name", "")
            if "orderuser orderdb" in nome or ("postgres:" in nome and "orderuser" in nome):
                s_app += p.get("cpuUsedPc", 0); n_app += 1
            else:
                s_outros += p.get("cpuUsedPc", 0)
        proc["app"].append(s_app); proc["outros"].append(s_outros); nb.append(n_app)
    m = lambda x: st.mean(x) if x else float("nan")
    lin = dict(janela=rot, n=len(nb), **{f"cpu_{k}": m(v) for k, v in cpu.items()},
               proc_backends_app=m(proc["app"]), proc_outros=m(proc["outros"]),
               n_backends_app=m(nb), rede_rx=m(rede["rx"]), rede_tx=m(rede["tx"]))
    res.append(lin)
json.dump(res, open(AQUI / "resultados" / "enhanced_monitoring_detalhado.json", "w"), indent=2)
cols = ["cpu_total", "cpu_user", "cpu_system", "cpu_irq", "cpu_nice", "cpu_guest", "cpu_steal", "cpu_wait",
        "proc_backends_app", "proc_outros", "n_backends_app", "rede_rx", "rede_tx"]
print(f"{'janela':<26}" + "".join(f"{c.replace('cpu_','').replace('proc_',''):>11}" for c in cols))
for l in res:
    print(f"{l['janela']:<26}" + "".join(f"{l.get(c, float('nan')):>11.2f}" for c in cols))
