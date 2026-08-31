#!/usr/bin/env python3
"""timestamps.json so cobre L2 r1-r3. Para r4/r5, reconstroi a janela real
de cada rodada a partir do mtime do summary.json (aproximacao inicial) mais
uma consulta binada (1min) ao CloudWatch Logs Insights que confirma
empiricamente onde comeca/termina o burst de invocacoes -- nao confia cegamente
no mtime, so usa ele para definir uma janela de busca ampla o suficiente."""
import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3

FASE4_DIR = os.path.expanduser("~/Programming/ecommerce-tcc/analysis/lambda/fase4")
LOG_GROUPS = {
    "springboot": "/aws/lambda/order-processor-springboot",
    "quarkus-jvm": "/aws/lambda/order-processor-quarkus-jvm",
    "quarkus-native": "/aws/lambda/order-processor-quarkus-native",
}

session = boto3.Session(profile_name="pessoal", region_name="us-east-1")
logs_client = session.client("logs")


def run_query(log_group, start_epoch, end_epoch, query):
    resp = logs_client.start_query(logGroupName=log_group, startTime=start_epoch, endTime=end_epoch,
                                    queryString=query, limit=10000)
    qid = resp["queryId"]
    for _ in range(120):
        r = logs_client.get_query_results(queryId=qid)
        if r["status"] == "Complete":
            return r["results"]
        if r["status"] in ("Failed", "Cancelled", "Timeout"):
            raise RuntimeError(r["status"])
        time.sleep(2)
    raise TimeoutError()


def field(row, name):
    for kv in row:
        if kv["field"] == name:
            return kv["value"]
    return None


def parse_cw_timestamp(value):
    """CloudWatch Logs Insights devolve timestamps sem sufixo 'Z' e com
    espaco em vez de 'T' (ex.: "2026-07-16 09:47:00.000"), sempre em UTC.
    fromisoformat() sozinho produziria um datetime NAIVE, que .timestamp()
    interpretaria no fuso LOCAL da maquina -- bug real ja pego em teste
    (deslocaria a janela em -03:00 nesta maquina)."""
    v = value.strip().replace("Z", "").replace(" ", "T")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def find_window(version, round_num):
    summary_path = os.path.join(FASE4_DIR, f"l2-{version}-r{round_num}-summary.json")
    with open(summary_path) as fp:
        expected_count = int(json.load(fp)["metrics"]["http_reqs"]["count"])
    mtime = datetime.fromtimestamp(os.path.getmtime(summary_path), tz=timezone.utc)
    search_start = mtime - timedelta(minutes=25)
    search_end = mtime + timedelta(minutes=8)

    log_group = LOG_GROUPS[version]
    rows = run_query(
        log_group, int(search_start.timestamp()), int(search_end.timestamp()),
        'filter @type = "REPORT" | stats count(*) as invocations by bin(1m) as minuto',
    )
    bins = {}
    for r in rows:
        m = field(r, "minuto")
        c = int(field(r, "invocations"))
        bins[parse_cw_timestamp(m)] = c

    if not bins:
        return None

    ordered = sorted(bins.items())
    # L3 roda no mesmo log group logo antes/depois de L2, e o warmup de L3
    # (15req/s, ~900/min) e identico ao warmup de L2 -- um limiar de faixa
    # sozinho nao distingue os dois (confirmado empiricamente: sem mais
    # nada, o bloco "ativo" emendava o warmup de L3 no final do bloco de
    # L2). Em vez de tentar reconhecer a forma, acha o inicio do primeiro
    # bloco de atividade (>50/min apos silencio) e anda para frente
    # somando invocacoes ate bater o total esperado (http_reqs.count do
    # proprio summary.json) -- para exatamente onde L2 acaba,
    # independentemente do que vier depois.
    first_active_idx = None
    for i, (_, c) in enumerate(ordered):
        if c > 50:
            first_active_idx = i
            break
    if first_active_idx is None:
        return None

    cumulative = 0
    end_idx = first_active_idx
    for i in range(first_active_idx, len(ordered)):
        cumulative += ordered[i][1]
        end_idx = i
        if cumulative >= expected_count * 0.97:
            break

    win_start = ordered[first_active_idx][0]
    win_end = ordered[end_idx][0] + timedelta(minutes=1)
    n_bins = end_idx - first_active_idx + 1
    return win_start.isoformat(), win_end.isoformat(), mtime.isoformat(), n_bins, cumulative


def main():
    windows = {}
    for version in ["springboot", "quarkus-jvm", "quarkus-native"]:
        for round_num in [4, 5]:
            result = find_window(version, round_num)
            key = f"l2-{version}-r{round_num}"
            if result is None:
                print(f"[aviso] {key}: nao encontrei atividade na janela de busca (mtime-based)")
                continue
            start, end, mtime, n_active_bins, cumulative = result
            windows[key] = {"start": start, "end": end}
            print(f"{key}: mtime={mtime} -> janela real=[{start} .. {end}] ({n_active_bins} bins, {cumulative} invocacoes acumuladas)")

    out_path = os.path.join(FASE4_DIR, "_r4_r5_reconstructed_windows.json")
    with open(out_path, "w") as fp:
        json.dump(windows, fp, indent=2, sort_keys=True)
    print(f"\nSalvo em {out_path}")


if __name__ == "__main__":
    main()
