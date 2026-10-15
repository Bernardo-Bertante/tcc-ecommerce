#!/usr/bin/env python3
"""Compara pg_stat_statements de Spring Boot x Quarkus JVM na mesma carga (F1, 48 req/s).

Investigacao EXPLORATORIA (analysis/pg_stat_statements_rds/) — nao e coleta oficial do TCC.
Nao escreve conclusao interpretativa: so classifica, agrega e tabula.

Uso: compara.py <dir_com_f1-springboot_e_f1-quarkus-jvm> <dir_saida>
"""
import csv
import json
import re
import sys
from pathlib import Path

VERSOES = ["springboot", "quarkus-jvm"]

# Classificacao por texto normalizado da consulta -> operacao do mix de endpoints.
# A ordem importa: a primeira regra que casar vence.
REGRAS = [
    ("infra_pool_validacao",    r"^\s*SELECT\s+\$\d+\s*$"),
    ("infra_rds_monitoramento", r"pg_available_extensions|pg_catalog\.pg_depend|pg_catalog\.pg_collation|pg_catalog\.pg_extension|RELPAGES|current_catalog"),
    ("infra_sessao",            r"^\s*(SHOW|SET|BEGIN|COMMIT|ROLLBACK|DISCARD)\b"),
    ("infra_sessao",            r"pg_catalog\.pg_type|pg_settings|pg_stat_statements_reset"),

    ("get_summary",             r"created_at\s*>=\s*\$\d+\s+AND\s+created_at\s*<\s*\$\d+"),

    # tem de vir antes de get_orders_by_customer: o UPDATE do SB cita customer_id no SET
    ("update_status",           r"^\s*UPDATE\s+orders\b"),

    # order_items buscado por LISTA de order_id: no SB sao 7 statements (IN com aridades
    # diferentes), no QJ e um so (= ANY($1)). Ambos servem a pagina do cliente.
    ("get_orders_by_customer",  r"FROM\s+order_items\b.*order_id\s*(IN\s*\(\s*\$\d+\s*,|=\s*ANY)"),
    ("get_orders_by_customer",  r"customer_id\s*=\s*\$\d+"),

    # os dois gravam historico no fluxo de criacao E no de update; o SB usa dois statements
    # distintos (4 e 5 colunas), o QJ um so. Categoria propria para nao atribuir errado.
    ("insert_status_history",   r"^\s*INSERT\s+INTO\s+order_status_history\b"),

    ("create_order",            r"^\s*INSERT\s+INTO\s+orders\b"),
    ("create_order",            r"^\s*INSERT\s+INTO\s+order_items\b"),

    ("get_order",               r"FROM\s+orders\b[^;]*\bid\s*=\s*\$\d+"),
    ("get_order",               r"FROM\s+order_items\b[^;]*order_id\s*=\s*\$\d+"),
]

NUM = ["calls", "rows", "total_exec_time_ms", "mean_exec_time_ms", "shared_blks_hit",
       "shared_blks_read", "shared_blks_dirtied", "shared_blks_written", "plans",
       "total_plan_time_ms", "wal_records", "wal_fpi", "temp_blks_read", "temp_blks_written"]


def classifica(q):
    texto = re.sub(r"\s+", " ", q or "").strip()
    for op, padrao in REGRAS:
        if re.search(padrao, texto, re.IGNORECASE):
            return op
    return "nao_classificado"


def carrega(base, versao):
    arq = Path(base) / f"f1-{versao}" / "pg_stat_statements.csv"
    linhas = []
    for r in csv.DictReader(arq.open()):
        for k in NUM:
            try:
                r[k] = float(r.get(k) or 0)
            except ValueError:
                r[k] = 0.0
        r["operacao"] = classifica(r["query"])
        r["versao"] = versao
        linhas.append(r)
    return linhas


def agrega_por_operacao(linhas):
    out = {}
    for r in linhas:
        a = out.setdefault(r["operacao"], dict(calls=0.0, total_ms=0.0, rows=0.0,
                                               blks_hit=0.0, blks_read=0.0, wal_records=0.0,
                                               n_queries=0))
        a["calls"] += r["calls"]
        a["total_ms"] += r["total_exec_time_ms"]
        a["rows"] += r["rows"]
        a["blks_hit"] += r["shared_blks_hit"]
        a["blks_read"] += r["shared_blks_read"]
        a["wal_records"] += r["wal_records"]
        a["n_queries"] += 1
    for a in out.values():
        a["mean_ms"] = a["total_ms"] / a["calls"] if a["calls"] else 0.0
        a["blks_por_call"] = (a["blks_hit"] + a["blks_read"]) / a["calls"] if a["calls"] else 0.0
    return out


def main():
    base, saida = Path(sys.argv[1]), Path(sys.argv[2])
    saida.mkdir(parents=True, exist_ok=True)
    dados = {v: carrega(base, v) for v in VERSOES}

    # 1) dump unificado, com a classificacao, para conferencia manual
    with (saida / "consultas_classificadas.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["versao", "operacao", "queryid", "calls", "total_exec_time_ms",
                    "mean_exec_time_ms", "rows", "shared_blks_hit", "shared_blks_read",
                    "wal_records", "query"])
        for v in VERSOES:
            for r in sorted(dados[v], key=lambda x: -x["total_exec_time_ms"]):
                w.writerow([v, r["operacao"], r["queryid"], int(r["calls"]),
                            round(r["total_exec_time_ms"], 3), round(r["mean_exec_time_ms"], 4),
                            int(r["rows"]), int(r["shared_blks_hit"]), int(r["shared_blks_read"]),
                            int(r["wal_records"]), re.sub(r"\s+", " ", r["query"]).strip()])

    # 2) agregado por operacao, lado a lado
    ag = {v: agrega_por_operacao(dados[v]) for v in VERSOES}
    ops = sorted(set(ag["springboot"]) | set(ag["quarkus-jvm"]))
    with (saida / "comparacao_por_operacao.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["operacao",
                    "sb_calls", "qj_calls", "razao_calls",
                    "sb_total_ms", "qj_total_ms", "razao_total_ms",
                    "sb_mean_ms", "qj_mean_ms", "razao_mean_ms",
                    "sb_blks_por_call", "qj_blks_por_call",
                    "sb_rows", "qj_rows", "sb_wal_records", "qj_wal_records",
                    "sb_n_queries_distintas", "qj_n_queries_distintas"])
        vazio = dict(calls=0.0, total_ms=0.0, mean_ms=0.0, rows=0.0, blks_hit=0.0, blks_read=0.0,
                     blks_por_call=0.0, wal_records=0.0, n_queries=0)
        for op in ops:
            s, q = ag["springboot"].get(op, vazio), ag["quarkus-jvm"].get(op, vazio)
            raz = lambda a, b: round(a / b, 3) if b else None
            w.writerow([op,
                        int(s["calls"]), int(q["calls"]), raz(s["calls"], q["calls"]),
                        round(s["total_ms"], 1), round(q["total_ms"], 1), raz(s["total_ms"], q["total_ms"]),
                        round(s["mean_ms"], 4), round(q["mean_ms"], 4), raz(s["mean_ms"], q["mean_ms"]),
                        round(s["blks_por_call"], 2), round(q["blks_por_call"], 2),
                        int(s["rows"]), int(q["rows"]),
                        int(s["wal_records"]), int(q["wal_records"]),
                        s["n_queries"], q["n_queries"]])

    # 3) totais
    tot = {}
    for v in VERSOES:
        tot[v] = dict(
            calls=sum(r["calls"] for r in dados[v]),
            total_ms=sum(r["total_exec_time_ms"] for r in dados[v]),
            blks=sum(r["shared_blks_hit"] + r["shared_blks_read"] for r in dados[v]),
            n_queries=len(dados[v]),
        )
    (saida / "totais.json").write_text(json.dumps(tot, indent=2))

    # impressao
    print(f"{'operacao':<24} {'SB calls':>10} {'QJ calls':>10} {'SB tot ms':>11} {'QJ tot ms':>11} "
          f"{'SB med':>9} {'QJ med':>9}  razao_tot")
    for op in ops:
        s, q = ag["springboot"].get(op, vazio), ag["quarkus-jvm"].get(op, vazio)
        rt = f"{s['total_ms']/q['total_ms']:.2f}x" if q["total_ms"] else "-"
        print(f"{op:<24} {int(s['calls']):>10} {int(q['calls']):>10} {s['total_ms']:>11.1f} "
              f"{q['total_ms']:>11.1f} {s['mean_ms']:>9.4f} {q['mean_ms']:>9.4f}  {rt:>9}")
    print()
    for v in VERSOES:
        t = tot[v]
        print(f"{v:<14} total: {int(t['calls'])} chamadas, {t['total_ms']:.0f} ms de execucao, "
              f"{int(t['blks'])} blocos, {t['n_queries']} consultas distintas")
    nc = [r for v in VERSOES for r in dados[v] if r["operacao"] == "nao_classificado"]
    if nc:
        print(f"\nATENCAO: {len(nc)} consultas nao classificadas:")
        for r in nc:
            print(f"  [{r['versao']}] {int(r['calls'])} calls | {re.sub(r'  +',' ',r['query'])[:130]}")


if __name__ == "__main__":
    main()
