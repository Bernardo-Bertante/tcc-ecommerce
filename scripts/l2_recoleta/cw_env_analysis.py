#!/usr/bin/env python3
"""Analisa, para uma rodada de L2, quantos ambientes de execucao (log
streams) do Lambda processaram as invocacoes daquela rodada, e quantas
invocacoes cada um acumulou -- para responder se algum ambiente cruzou os
limiares de compilacao JIT do HotSpot (Tier 1 ~1.000, Tier 2 ~10.000
invocacoes) dentro da janela do cenario.

Consulta o CloudWatch Logs Insights via boto3 (mesma biblioteca ja usada em
analysis/fase5_analise_estatistica.py para ECS/ContainerInsights). Reconcilia
o total de invocacoes encontrado no CloudWatch contra o total de requisicoes
reportado pelo k6 (summary.json / http_reqs.count) antes de aceitar o
resultado -- releitura com backoff se a contagem estiver incompleta
(propagacao do CloudWatch Logs, o mesmo problema que ja causou duplicata de
log na coleta original do H1b). Se apos varias tentativas a contagem
continuar incompleta, para com erro claro (nao e mais so propagacao).

Uso: python3 cw_env_analysis.py --log-group ... --start ISO8601 --end ISO8601
     --versao springboot --rodada 3 --expected-count 20366
     --out-csv analysis/fase5/fase5_l2_ambientes_execucao.csv [--track-jit]
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import boto3

CSV_FIELDS = [
    "timestamp_geracao", "versao", "rodada", "log_group",
    "janela_inicio", "janela_fim",
    "invocacoes_k6_esperadas", "invocacoes_cloudwatch_total", "reconciliado",
    "num_ambientes", "min_invocacoes_ambiente", "mediana_invocacoes_ambiente",
    "max_invocacoes_ambiente", "ambientes_estabilizam_cedo",
    "ts_cruzou_tier1_1000inv", "ts_cruzou_tier2_10000inv", "tentativas_query",
]

RECONCILE_THRESHOLD = 0.98
RETRY_BACKOFFS_SEC = [60, 120, 240, 240, 240, 240]


def field(row, name):
    for kv in row:
        if kv["field"] == name:
            return kv["value"]
    return None


def parse_cw_timestamp(value):
    """CloudWatch Logs Insights devolve timestamps (bin(), @timestamp) sem
    sufixo 'Z' e com espaco em vez de 'T' (ex.: "2026-07-16 09:47:00.000"),
    sempre em UTC. datetime.fromisoformat() sozinho produziria um datetime
    NAIVE, que .timestamp() interpretaria no fuso LOCAL da maquina -- bug
    real ja pego em teste (deslocaria a janela em -03:00 nesta maquina)."""
    v = value.strip().replace("Z", "").replace(" ", "T")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def run_insights_query(client, log_group, start_epoch, end_epoch, query, timeout_s=180):
    resp = client.start_query(
        logGroupName=log_group, startTime=start_epoch, endTime=end_epoch,
        queryString=query, limit=10000,
    )
    query_id = resp["queryId"]
    waited = 0
    while waited < timeout_s:
        result = client.get_query_results(queryId=query_id)
        status = result["status"]
        if status == "Complete":
            return result["results"]
        if status in ("Failed", "Cancelled", "Timeout"):
            raise RuntimeError(f"Logs Insights query terminou com status={status}: {query}")
        time.sleep(3)
        waited += 3
    raise TimeoutError(f"Logs Insights query nao completou em {timeout_s}s: {query}")


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return 0
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-group", required=True)
    ap.add_argument("--start", required=True, help="ISO8601 UTC (inicio da rodada)")
    ap.add_argument("--end", required=True, help="ISO8601 UTC (fim da rodada)")
    ap.add_argument("--versao", required=True)
    ap.add_argument("--rodada", required=True, type=int)
    ap.add_argument("--expected-count", required=True, type=int)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "pessoal"))
    ap.add_argument("--max-retries", type=int, default=6)
    ap.add_argument("--initial-wait", type=int, default=90,
                     help="segundos de espera de propagacao do CloudWatch Logs antes da 1a consulta")
    ap.add_argument("--track-jit", action="store_true",
                     help="calcular timestamp de cruzamento dos limiares Tier1/Tier2 (so springboot/quarkus-jvm)")
    args = ap.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    logs_client = session.client("logs")

    start_dt = parse_cw_timestamp(args.start)
    end_dt = parse_cw_timestamp(args.end)
    # padding: um pouco antes do inicio nominal e bastante depois do fim,
    # para nao perder REPORT lines de invocacoes que comecaram dentro da
    # janela mas so terminam (e so entao geram a linha REPORT) alguns
    # segundos/minutos depois do ultimo request do k6.
    start_epoch = int(start_dt.timestamp()) - 5
    end_epoch = int(end_dt.timestamp()) + 120

    print(f"[cw_env_analysis] {args.versao} rodada {args.rodada}: aguardando {args.initial_wait}s de "
          f"propagacao do CloudWatch antes da 1a consulta...", flush=True)
    time.sleep(args.initial_wait)

    by_stream_query = 'filter @type = "REPORT" | stats count(*) as invocations by @logStream'

    attempt = 0
    total = 0
    rows_by_stream = []
    while True:
        attempt += 1
        rows_by_stream = run_insights_query(logs_client, args.log_group, start_epoch, end_epoch, by_stream_query)
        total = sum(int(field(r, "invocations")) for r in rows_by_stream)
        pct = (total / args.expected_count) if args.expected_count else 1.0
        print(f"[cw_env_analysis] {args.versao} rodada {args.rodada}: tentativa {attempt} -- "
              f"{total}/{args.expected_count} invocacoes reconciliadas ({pct:.1%})", flush=True)
        if pct >= RECONCILE_THRESHOLD:
            break
        if attempt > args.max_retries:
            break
        wait = RETRY_BACKOFFS_SEC[min(attempt - 1, len(RETRY_BACKOFFS_SEC) - 1)]
        print(f"[cw_env_analysis] contagem incompleta -- provavel atraso de propagacao do CloudWatch Logs, "
              f"tentando de novo em {wait}s...", flush=True)
        time.sleep(wait)

    reconciled = bool(args.expected_count) and (total / args.expected_count) >= RECONCILE_THRESHOLD
    if not reconciled:
        print(
            f"[cw_env_analysis] ERRO NAO TRANSITORIO: apos {attempt} tentativas ao longo de "
            f"~{sum(RETRY_BACKOFFS_SEC[:attempt-1])}s de espera adicional, o CloudWatch ainda mostra "
            f"{total}/{args.expected_count} invocacoes ({(total/args.expected_count if args.expected_count else 0):.1%}) "
            f"para {args.versao} rodada {args.rodada} (log group={args.log_group}, "
            f"janela epoch={start_epoch}-{end_epoch}). Isso nao parece mais ser so atraso de propagacao -- "
            f"revise manualmente (log group errado? throttle real de invocacoes? retencao insuficiente?) "
            f"antes de retomar a recoleta.",
            file=sys.stderr, flush=True,
        )
        sys.exit(2)

    counts = sorted(int(field(r, "invocations")) for r in rows_by_stream)
    n_envs = len(counts)
    min_inv = counts[0] if counts else 0
    max_inv = counts[-1] if counts else 0
    med_inv = median(counts)

    # Serie temporal por ambiente em bins de 1min -- evita o limite de 10.000
    # linhas do Logs Insights (uma rodada tem ~20k invocacoes, nao caberia
    # como eventos individuais numa unica query) e da granularidade
    # suficiente (1min) para (a) checar se o numero de ambientes distintos
    # estabiliza cedo e (b) achar o minuto aproximado em que o ambiente mais
    # ativo cruzou os limiares de JIT.
    binned_query = 'filter @type = "REPORT" | stats count(*) as invocations by @logStream, bin(1m) as minuto'
    binned_rows = run_insights_query(logs_client, args.log_group, start_epoch, end_epoch, binned_query)

    per_stream_bins = defaultdict(dict)
    distinct_streams_per_bin = defaultdict(set)
    for r in binned_rows:
        stream = field(r, "@logStream")
        minuto_str = field(r, "minuto")
        cnt = int(field(r, "invocations"))
        minuto_dt = parse_cw_timestamp(minuto_str) if minuto_str else None
        per_stream_bins[stream][minuto_dt] = cnt
        distinct_streams_per_bin[minuto_dt].add(stream)

    top_stream, top_total = None, -1
    for stream, bins in per_stream_bins.items():
        s = sum(bins.values())
        if s > top_total:
            top_total, top_stream = s, stream

    ts_tier1 = ""
    ts_tier2 = ""
    if args.track_jit and top_stream is not None:
        cumulative = 0
        for minute in sorted(per_stream_bins[top_stream].keys()):
            cumulative += per_stream_bins[top_stream][minute]
            if not ts_tier1 and cumulative >= 1000:
                ts_tier1 = minute.isoformat()
            if not ts_tier2 and cumulative >= 10000:
                ts_tier2 = minute.isoformat()
                break

    # Heuristica de estabilizacao precoce: compara os ambientes distintos
    # vistos nos primeiros 3min contra o total da rodada, e checa se algum
    # ambiente NOVO ainda aparece depois do minuto 6 (sinal de "scaling
    # loop" continuo em vez de reaproveitamento).
    all_minutes = sorted(distinct_streams_per_bin.keys())
    total_distinct = len(per_stream_bins)
    stabilizes_early = False
    if all_minutes and total_distinct > 0:
        t0 = all_minutes[0]
        seen_early = set()
        seen_after_6min = set()
        for m in all_minutes:
            offset = (m - t0).total_seconds()
            if offset <= 180:
                seen_early |= distinct_streams_per_bin[m]
            if offset > 360:
                seen_after_6min |= distinct_streams_per_bin[m]
        new_after_6min = seen_after_6min - seen_early
        stabilizes_early = (len(seen_early) / total_distinct >= 0.9) and (len(new_after_6min) == 0)

    row = {
        "timestamp_geracao": datetime.now(timezone.utc).isoformat(),
        "versao": args.versao,
        "rodada": args.rodada,
        "log_group": args.log_group,
        "janela_inicio": args.start,
        "janela_fim": args.end,
        "invocacoes_k6_esperadas": args.expected_count,
        "invocacoes_cloudwatch_total": total,
        "reconciliado": reconciled,
        "num_ambientes": n_envs,
        "min_invocacoes_ambiente": min_inv,
        "mediana_invocacoes_ambiente": med_inv,
        "max_invocacoes_ambiente": max_inv,
        "ambientes_estabilizam_cedo": stabilizes_early,
        "ts_cruzou_tier1_1000inv": ts_tier1,
        "ts_cruzou_tier2_10000inv": ts_tier2,
        "tentativas_query": attempt,
    }

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    write_header = not os.path.exists(args.out_csv)
    with open(args.out_csv, "a", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
