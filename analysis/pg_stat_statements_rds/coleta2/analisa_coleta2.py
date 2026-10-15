#!/usr/bin/env python3
"""Coleta 2 (exploratoria): agrega pg_stat_statements por rodada e por operacao.

Nao escreve conclusao interpretativa. Uso: python3 coleta2/analisa_coleta2.py
"""
import csv, glob, json, re, sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from compara import classifica  # mesmo classificador da coleta 1

rodadas = []
for d in sorted(glob.glob(str(AQUI / "dados" / "r*"))):
    d = Path(d)
    pos, cond = d.name[1:].split("-", 1)
    arq = d / "pg_stat_statements.csv"
    linhas = list(csv.DictReader(arq.open())) if arq.stat().st_size else []
    k6 = json.load(open(d / "summary.json"))["metrics"]
    ag = defaultdict(lambda: defaultdict(float))
    for r in linhas:
        op = classifica(r["query"])
        for k in ("calls", "total_exec_time_ms", "total_plan_time_ms", "plans",
                  "shared_blks_hit", "shared_blks_read", "rows"):
            v = float(r[k] or 0)
            ag[op][k] += v
            ag["_TOTAL"][k] += v
    rodadas.append(dict(pos=int(pos), cond=cond, ag=ag, n=len(linhas),
                        falha=k6["http_req_failed"]["value"], iters=k6["iterations"]["count"]))

saida = AQUI / "resultados"; saida.mkdir(exist_ok=True)
with open(saida / "por_rodada_por_operacao.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["posicao", "condicao", "operacao", "calls", "exec_ms", "plan_ms", "plans",
                "exec_mais_plan_ms", "blks_hit", "blks_read", "rows"])
    for r in rodadas:
        for op, a in sorted(r["ag"].items()):
            w.writerow([r["pos"], r["cond"], op, int(a["calls"]), round(a["total_exec_time_ms"], 1),
                        round(a["total_plan_time_ms"], 1), int(a["plans"]),
                        round(a["total_exec_time_ms"] + a["total_plan_time_ms"], 1),
                        int(a["shared_blks_hit"]), int(a["shared_blks_read"]), int(a["rows"])])

print(f"{'rod':<4}{'condicao':<18}{'falha%':>7}{'calls':>9}{'exec ms':>10}{'plan ms':>9}{'plans':>8}"
      f"{'exec+plan':>11}{'summary ex':>11}{'summ plan':>10}{'blocos':>10}")
for r in rodadas:
    if not r["n"]:
        print(f"{r['pos']:<4}{r['cond']:<18}{100*r['falha']:>7.3f}   (dump de pg_stat_statements perdido)"); continue
    t, s = r["ag"]["_TOTAL"], r["ag"]["get_summary"]
    print(f"{r['pos']:<4}{r['cond']:<18}{100*r['falha']:>7.3f}{int(t['calls']):>9}{t['total_exec_time_ms']:>10.0f}"
          f"{t['total_plan_time_ms']:>9.0f}{int(t['plans']):>8}{t['total_exec_time_ms']+t['total_plan_time_ms']:>11.0f}"
          f"{s['total_exec_time_ms']:>11.0f}{s['total_plan_time_ms']:>10.0f}{int(t['shared_blks_hit']):>10}")
