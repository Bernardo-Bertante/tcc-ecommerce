#!/usr/bin/env python3
"""Latencia da aplicacao (k6) por condicao na coleta 3. Exploratorio; sem coleta nova.

Fonte: summary.json (--summary-export) de cada rodada, submetrica http_req_duration{phase:load}
(exclui as 120 requisicoes de seed do setup). O summary-export so traz avg/min/med/max/p90/p95:
NAO ha p99 nem recorte por endpoint em nenhuma fonte desta coleta (sem --out json no orquestrador).
"""
import csv, glob, json
from pathlib import Path
AQUI = Path(__file__).resolve().parent
M = "http_req_duration{phase:load}"
ST = [("avg", "media"), ("med", "mediana"), ("p(90)", "p90"), ("p(95)", "p95"), ("max", "max")]
rod = []
for d in sorted(glob.glob(str(AQUI / "dados" / "r*"))):
    pos, cond = Path(d).name[1:].split("-", 1)
    s = json.load(open(Path(d) / "summary.json"))["metrics"]
    rod.append(dict(pos=int(pos), cond=cond, n=s["http_reqs"]["count"], **{n: s[M][k] for k, n in ST}))
with open(AQUI / "resultados" / "latencia_k6_por_rodada.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rod[0])); w.writeheader(); w.writerows(rod)
print("POR RODADA (ms)")
print(f"{'rodada':<22}" + "".join(f"{n:>9}" for _, n in ST))
for r in rod: print(f"r{r['pos']} {r['cond']:<19}" + "".join(f"{r[n]:>9.2f}" for _, n in ST))
med = {c: {n: sum(r[n] for r in rod if r["cond"] == c) / 2 for _, n in ST} for c in ["springboot", "springboot-noval", "quarkus-jvm"]}
print("\nMEDIA DAS 2 REPLICAS (ms) e fracao do gap SB-QJ removida sem validacao")
print(f"{'estatistica':<12}{'SB':>9}{'SB s/val':>10}{'QJ':>9}{'SB/QJ':>8}{'s/val/QJ':>9}{'gap removido':>14}")
out = []
for _, n in ST:
    sb, nv, qj = med["springboot"][n], med["springboot-noval"][n], med["quarkus-jvm"][n]
    fr = (sb - nv) / (sb - qj) if sb != qj else float("nan")
    out.append(dict(estatistica=n, sb=sb, sb_noval=nv, qj=qj, sb_qj=sb/qj, noval_qj=nv/qj, fracao_gap_removida=fr))
    print(f"{n:<12}{sb:>9.2f}{nv:>10.2f}{qj:>9.2f}{sb/qj:>8.3f}{nv/qj:>9.3f}{100*fr:>13.0f}%")
with open(AQUI / "resultados" / "latencia_k6_por_condicao.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
