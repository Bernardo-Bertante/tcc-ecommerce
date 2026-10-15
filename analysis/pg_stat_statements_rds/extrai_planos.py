#!/usr/bin/env python3
"""Baixa os logs do RDS exploratorio e extrai os planos JSON do auto_explain.

Investigacao EXPLORATORIA (analysis/pg_stat_statements_rds/) — nao e coleta oficial do TCC.

O log do RDS usa log_line_prefix '%t:%r:%u@%d:[%p]:'. Uma entrada do auto_explain comeca com
uma linha de cabecalho ('... LOG:  duration: X ms  plan:') e continua nas linhas seguintes,
indentadas com TAB, com o plano em JSON. Cada plano traz 'Query Identifier', que e o mesmo
queryid do pg_stat_statements — e assim que plano e agregado sao ligados, sem casar texto.

Uso: extrai_planos.py <dir_saida> <janelas.json>
  janelas.json: {"springboot": [ini_epoch, fim_epoch], "quarkus-jvm": [...]}
"""
import gzip
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

import boto3

INSTANCE = "repro-f3-postgres"
PROFILE = "pessoal"
REGION = "us-east-1"

# 2026-09-23 00:10:48 UTC:<IP_RESIDENCIAL>(35202):orderuser@orderdb:[1440]:LOG:  duration: 73.454 ms  plan:
CAB = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC:(?P<cli>[^:]*):(?P<user>[^:]*):\[(?P<pid>\d+)\]:"
    r"LOG:\s+duration: (?P<dur>[\d.]+) ms\s+plan:\s*$"
)


def baixa_logs(rds, destino: Path, desde_epoch: float):
    """Baixa todos os arquivos de log escritos a partir de desde_epoch."""
    destino.mkdir(parents=True, exist_ok=True)
    arquivos = []
    paginator = rds.get_paginator("describe_db_log_files")
    for page in paginator.paginate(DBInstanceIdentifier=INSTANCE):
        for f in page["DescribeDBLogFiles"]:
            if f["LastWritten"] / 1000.0 >= desde_epoch - 7200:
                arquivos.append(f["LogFileName"])
    for nome in sorted(arquivos):
        alvo = destino / (nome.replace("/", "_") + ".gz")
        if alvo.exists():
            continue
        partes, marker = [], "0"
        while True:
            r = rds.download_db_log_file_portion(
                DBInstanceIdentifier=INSTANCE, LogFileName=nome, Marker=marker, NumberOfLines=0
            )
            partes.append(r.get("LogFileData") or "")
            if not r.get("AdditionalDataPending"):
                break
            novo = r.get("Marker")
            if not novo or novo == marker:
                break
            marker = novo
        with gzip.open(alvo, "wt", encoding="utf-8", errors="replace") as fh:
            fh.write("".join(partes))
        print(f"  baixado {nome} -> {alvo.name} ({alvo.stat().st_size} bytes gz)")
    return sorted(destino.glob("*.gz"))


def le_planos(arquivos):
    """Devolve (epoch, duracao_ms, plano_dict) para cada entrada do auto_explain."""
    for arq in arquivos:
        cab, buf = None, []
        with gzip.open(arq, "rt", encoding="utf-8", errors="replace") as fh:
            for linha in fh:
                linha = linha.rstrip("\n")
                if linha.startswith("\t") and cab is not None:
                    buf.append(linha[1:])
                    continue
                if cab is not None:
                    yield from _fecha(cab, buf)
                    cab, buf = None, []
                m = CAB.match(linha)
                if m:
                    cab, buf = m, []
        if cab is not None:
            yield from _fecha(cab, buf)


def _fecha(m, buf):
    if not buf:
        return
    try:
        plano = json.loads("\n".join(buf))
    except json.JSONDecodeError:
        return
    ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    yield ts.timestamp(), float(m.group("dur")), plano


def resume_no(no, prof=0, acc=None):
    """Achata a arvore do plano em uma lista de nos, para comparar scans."""
    if acc is None:
        acc = []
    acc.append({
        "prof": prof,
        "node": no.get("Node Type"),
        "rel": no.get("Relation Name"),
        "index": no.get("Index Name"),
        "cond": no.get("Index Cond") or no.get("Recheck Cond") or no.get("Filter"),
        "plan_rows": no.get("Plan Rows"),
        "actual_rows": no.get("Actual Rows"),
        "loops": no.get("Actual Loops"),
        "ms": no.get("Actual Total Time"),
        "shared_hit": no.get("Shared Hit Blocks"),
        "shared_read": no.get("Shared Read Blocks"),
        "heap_fetches": no.get("Heap Fetches"),
        "rows_removed_filter": no.get("Rows Removed by Filter"),
    })
    for f in no.get("Plans", []) or []:
        resume_no(f, prof + 1, acc)
    return acc


def main():
    saida = Path(sys.argv[1])
    janelas = json.loads(Path(sys.argv[2]).read_text())
    saida.mkdir(parents=True, exist_ok=True)

    sess = boto3.Session(profile_name=PROFILE, region_name=REGION)
    rds = sess.client("rds")
    ini_geral = min(v[0] for v in janelas.values())
    print("baixando logs do RDS...")
    arquivos = baixa_logs(rds, saida / "logs_brutos", ini_geral)

    por_janela = {k: {} for k in janelas}
    total, fora = 0, 0
    for epoch, dur, plano in le_planos(arquivos):
        total += 1
        rot = next((k for k, (a, b) in janelas.items() if a <= epoch <= b), None)
        if rot is None:
            fora += 1
            continue
        qid = str(plano.get("Query Identifier"))
        d = por_janela[rot].setdefault(qid, {
            "queryid": qid,
            "query_text": plano.get("Query Text"),
            "amostras": 0,
            "duracoes_ms": [],
            "exemplo_plano": plano,
            "exemplo_nos": resume_no(plano["Plan"]) if "Plan" in plano else [],
        })
        d["amostras"] += 1
        d["duracoes_ms"].append(dur)
        # guarda como exemplo o plano de duracao mediana-ish (o primeiro serve; troca se este for menor)
    print(f"planos lidos: {total} (fora das janelas: {fora})")

    for rot, mapa in por_janela.items():
        for d in mapa.values():
            ds = sorted(d["duracoes_ms"])
            n = len(ds)
            d["dur_p50_ms"] = ds[n // 2]
            d["dur_media_ms"] = sum(ds) / n
            d["dur_max_ms"] = ds[-1]
            del d["duracoes_ms"]
        alvo = saida / f"planos_{rot}.json"
        alvo.write_text(json.dumps(sorted(mapa.values(), key=lambda x: -x["amostras"]), indent=2, ensure_ascii=False))
        print(f"{rot}: {len(mapa)} queryids distintos -> {alvo.name}")


if __name__ == "__main__":
    main()
