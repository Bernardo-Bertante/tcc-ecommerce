#!/usr/bin/env python3
"""Itens 1 e 3: blocos por chamada/por linha por consulta e texto normalizado, SB sem validacao x QJ.
Exploratorio, fora do desenho oficial. Nao interpreta: so tabula.
Uso: 01_pgss.py [dados] [resultados]
"""
import csv, re, sys, collections, statistics as st
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compara import classifica

base = Path(sys.argv[1] if len(sys.argv) > 1 else "dados")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "resultados"); out.mkdir(exist_ok=True)
COND = {"springboot-noval": "SB-noval", "quarkus-jvm": "QJ"}
NUM = ["calls", "rows", "total_exec_time_ms", "shared_blks_hit", "shared_blks_read", "total_plan_time_ms", "plans"]

def norm(q): return re.sub(r"\s+", " ", q).strip()

rodadas = {}
for d in sorted(base.glob("r*-*")):
    cond = d.name.split("-", 1)[1]
    if cond not in COND or not (d / "pg_stat_statements.csv").exists(): continue
    rows = []
    for r in csv.DictReader((d / "pg_stat_statements.csv").open()):
        for k in NUM: r[k] = float(r[k] or 0)
        r["texto"] = norm(r["query"]); r["op"] = classifica(r["query"])
        if r["op"].startswith("infra_") and "validacao" not in r["op"]: continue
        rows.append(r)
    rodadas[d.name] = (COND[cond], rows)

# --- por consulta (texto) por rodada
with (out / "pgss_por_consulta_por_rodada.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["rodada", "cond", "op", "queryid", "calls", "rows", "rows_por_call", "hit", "read",
                "blocos_por_call", "blocos_por_linha", "exec_ms_por_call", "plan_ms_por_call", "plans_por_call", "texto"])
    for rod, (cond, rows) in rodadas.items():
        for r in sorted(rows, key=lambda x: (x["op"], x["texto"])):
            c = r["calls"] or 1; blk = r["shared_blks_hit"] + r["shared_blks_read"]
            w.writerow([rod, cond, r["op"], r["queryid"], int(r["calls"]), int(r["rows"]), f'{r["rows"]/c:.2f}',
                        int(r["shared_blks_hit"]), int(r["shared_blks_read"]), f"{blk/c:.2f}",
                        f'{blk/r["rows"]:.2f}' if r["rows"] else "", f'{r["total_exec_time_ms"]/c:.4f}',
                        f'{r["total_plan_time_ms"]/c:.4f}', f'{r["plans"]/c:.3f}', r["texto"][:400]])

# --- agregado por operacao e condicao (soma das replicas)
agg = collections.defaultdict(lambda: collections.defaultdict(float))
for rod, (cond, rows) in rodadas.items():
    for r in rows:
        a = agg[(r["op"], cond)]
        for k in NUM: a[k] += r[k]
        a["n_rod_q"] += 1
ops = sorted({k[0] for k in agg})
lines = [f"{'operacao':26} {'cond':9} {'calls':>9} {'rows/call':>9} {'blk/call':>9} {'blk/linha':>9} {'exec ms/call':>12} {'plan ms/call':>12}"]
for op in ops:
    for cond in ("SB-noval", "QJ"):
        a = agg.get((op, cond))
        if not a: continue
        c = a["calls"] or 1; blk = a["shared_blks_hit"] + a["shared_blks_read"]
        lines.append(f"{op:26} {cond:9} {int(a['calls']):9d} {a['rows']/c:9.2f} {blk/c:9.1f} "
                     f"{(blk/a['rows'] if a['rows'] else float('nan')):9.2f} {a['total_exec_time_ms']/c:12.4f} {a['total_plan_time_ms']/c:12.4f}")
    lines.append("")
(out / "pgss_por_operacao.txt").write_text("\n".join(lines)); print("\n".join(lines))

# --- texto normalizado: conjuntos por operacao, diferencas literais
md = ["# Texto das consultas por operacao (normalizado pelo pg_stat_statements)\n"]
for op in ops:
    if op.startswith("infra_"): continue
    ts = {c: collections.Counter() for c in ("SB-noval", "QJ")}
    for rod, (cond, rows) in rodadas.items():
        for r in rows:
            if r["op"] == op: ts[cond][r["texto"]] += int(r["calls"])
    sb, qj = set(ts["SB-noval"]), set(ts["QJ"])
    md.append(f"\n## {op}\n\n- textos distintos: SB-noval {len(sb)}, QJ {len(qj)}; identicos nos dois: {len(sb & qj)}\n")
    for cond in ("SB-noval", "QJ"):
        md.append(f"\n**{cond}** (chamadas somadas nas rodadas)\n")
        for t, n in ts[cond].most_common():
            md.append(f"- {n:>7} x  `{t[:600]}`{'  [IDENTICO no outro]' if t in (qj if cond=='SB-noval' else sb) else ''}")
(out / "textos_por_operacao.md").write_text("\n".join(md) + "\n")
