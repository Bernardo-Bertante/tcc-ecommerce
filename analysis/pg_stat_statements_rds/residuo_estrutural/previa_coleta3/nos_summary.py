#!/usr/bin/env python3
"""Previa sobre dados JA coletados (coleta3): blocos/linha por NO de plano do get_summary,
por condicao. Exploratorio, fora do desenho oficial."""
import gzip, json, sys, statistics as st, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from extrai_planos import le_planos
base = Path(__file__).resolve().parents[2] / "coleta3"
jan = json.loads((base/"dados/janelas.json").read_text())
arq = sorted((base/"planos/logs_brutos").glob("*.gz"))
def walk(n, out):
    out.append(n)
    for c in n.get("Plans", []) or []: walk(c, out)
rows=[]
for ep,dur,pl in le_planos(arq):
    rot=next((k for k,(a,b) in jan.items() if a<=ep<=b),None)
    if not rot or "Plan" not in pl: continue
    q=" ".join((pl.get("Query Text") or "").split())
    if "FROM orders" not in q or "created_at >=" not in q: continue
    ns=[]; walk(pl["Plan"],ns)
    for n in ns:
        if n.get("Relation Name")=="orders" and "Scan" in n["Node Type"]:
            rows.append((rot,n["Node Type"],n.get("Actual Rows",0)*n.get("Actual Loops",1),
                         n.get("Shared Hit Blocks",0),n.get("Heap Fetches"),n.get("Rows Removed by Filter"),
                         n.get("Actual Total Time"),q[:40]))
g=collections.defaultdict(list)
for r in rows: g[(r[0],r[1])].append(r)
print(f"{'rodada':22} {'no':16} {'n':>4} {'linhas_med':>10} {'hit_med':>8} {'hit/1k_lin':>10} {'ms/1k_lin':>9} {'heapF/lin':>9}")
for k in sorted(g):
    v=[r for r in g[k] if r[2]>2000]
    if not v: continue
    print(f"{k[0]:22} {k[1]:16} {len(v):4} {st.median(r[2] for r in v):10.0f} {st.median(r[3] for r in v):8.0f} "
          f"{st.median(r[3]/r[2]*1000 for r in v):10.1f} {st.median(r[6]/r[2]*1000 for r in v):9.3f} "
          f"{(st.median((r[4] or 0)/r[2] for r in v) if v[0][4] is not None else float('nan')):9.3f}")
