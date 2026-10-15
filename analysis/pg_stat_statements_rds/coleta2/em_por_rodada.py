#!/usr/bin/env python3
"""Enhanced Monitoring (1 s) do RDS exploratorio por janela de carga: CPU, steal, load.
Cobre as duas coletas, para ver se o host mudou entre elas ou durante a coleta 2."""
import json, statistics as st, sys, glob
from pathlib import Path
import boto3
AQUI = Path(__file__).resolve().parent
logs = boto3.Session(profile_name="pessoal", region_name="us-east-1").client("logs")
rid = boto3.Session(profile_name="pessoal", region_name="us-east-1").client("rds").describe_db_instances(
    DBInstanceIdentifier="repro-f3-postgres")["DBInstances"][0]["DbiResourceId"]

janelas = []
for d in sorted(glob.glob(str(AQUI.parent / "dados" / "f1-*"))):
    m = json.load(open(Path(d) / "meta.json")); janelas.append(("C1 " + m["runtime"], m["epoch_inicio"], m["epoch_fim"]))
for d in sorted(glob.glob(str(AQUI / "dados" / "r*"))):
    m = json.load(open(Path(d) / "meta.json")); janelas.append((f"C2 r{m['posicao']} {m['runtime']}", m["epoch_inicio"], m["epoch_fim"]))

linhas = []
print(f"{'janela':<26}{'n':>6}{'cpu tot%':>9}{'cpu p95':>8}{'user%':>7}{'system%':>8}{'steal%':>7}{'steal p95':>10}{'wait%':>6}{'load1':>6}")
for rot, a, b in janelas:
    pts, tok = [], None
    while True:
        kw = dict(logGroupName="RDSOSMetrics", logStreamNames=[rid], startTime=int(a*1000), endTime=int(b*1000))
        if tok: kw["nextToken"] = tok
        r = logs.filter_log_events(**kw)
        for e in r["events"]:
            j = json.loads(e["message"]); c = j["cpuUtilization"]
            pts.append((c["total"], c["user"], c["system"], c["steal"], c["wait"], j["loadAverageMinute"]["one"]))
        tok = r.get("nextToken")
        if not tok: break
    if not pts: print(f"{rot:<26} sem dados"); continue
    col = list(zip(*pts)); q = lambda x: sorted(x)[int(.95*len(x))]
    lin = dict(janela=rot, n=len(pts), cpu=st.mean(col[0]), cpu_p95=q(col[0]), user=st.mean(col[1]),
               system=st.mean(col[2]), steal=st.mean(col[3]), steal_p95=q(col[3]), wait=st.mean(col[4]), load1=st.mean(col[5]))
    linhas.append(lin)
    print(f"{rot:<26}{lin['n']:>6}{lin['cpu']:>9.1f}{lin['cpu_p95']:>8.1f}{lin['user']:>7.1f}{lin['system']:>8.1f}"
          f"{lin['steal']:>7.2f}{lin['steal_p95']:>10.2f}{lin['wait']:>6.2f}{lin['load1']:>6.2f}")
(AQUI / "resultados").mkdir(exist_ok=True)
json.dump(linhas, open(AQUI / "resultados" / "enhanced_monitoring_por_janela.json", "w"), indent=2)
