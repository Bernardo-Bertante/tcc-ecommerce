#!/usr/bin/env python3
"""Emite uma linha por plano capturado pelo auto_explain (nao agrega por queryid).

Permite comparar Spring Boot x Quarkus JVM ao MESMO tamanho de tabela, ja que o custo das
agregacoes de get_summary cresce com a tabela ao longo da rodada.
Investigacao EXPLORATORIA — nao e coleta oficial do TCC.
"""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extrai_planos import le_planos, resume_no

janelas = json.loads(Path("dados/janelas.json").read_text())
arquivos = sorted(Path("planos/logs_brutos").glob("*.gz"))

SCANS = ("Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan",
         "Parallel Seq Scan", "Parallel Index Scan", "Bitmap Index Scan")

with open("resultados/amostras_planos.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "epoch", "seg_desde_inicio", "queryid", "dur_ms", "scan_node",
                "scan_rel", "scan_index", "scan_actual_rows", "scan_ms", "scan_hit",
                "scan_read", "heap_fetches", "n_nos", "no_raiz", "query_text"])
    n = 0
    for epoch, dur, plano in le_planos(arquivos):
        rot = next((k for k, (a, b) in janelas.items() if a <= epoch <= b), None)
        if rot is None or "Plan" not in plano:
            continue
        nos = resume_no(plano["Plan"])
        scan = next((x for x in nos if x["node"] in SCANS), None)
        qt = " ".join((plano.get("Query Text") or "").split())
        w.writerow([rot, f"{epoch:.0f}", f"{epoch - janelas[rot][0]:.0f}",
                    plano.get("Query Identifier"), f"{dur:.3f}",
                    scan["node"] if scan else "", scan["rel"] if scan else "",
                    scan["index"] if scan else "", scan["actual_rows"] if scan else "",
                    scan["ms"] if scan else "", scan["shared_hit"] if scan else "",
                    scan["shared_read"] if scan else "",
                    scan["heap_fetches"] if scan else "",
                    len(nos), nos[0]["node"], qt[:300]])
        n += 1
print(f"{n} amostras -> resultados/amostras_planos.csv")
