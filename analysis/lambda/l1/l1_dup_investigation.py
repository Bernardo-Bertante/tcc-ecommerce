#!/usr/bin/env python3
"""Investigacao pontual: confirmar se as 11 observacoes de L1 (springboot,
quarkus-native) sao 11 eventos fisicos distintos ou se ha duplicata real de
log, e confirmar a causa de exclusao da 11a invocacao do quarkus-jvm.

Reusa a mesma tecnica de fase5_analise_estatistica.py (fingerprint +
scipy.optimize.linear_sum_assignment) mas CAPTURA timestamp e request_id,
que o script original descarta (fetch_report_lines so guarda event["message"]).
"""
import json
import re
import numpy as np
import boto3
from scipy.optimize import linear_sum_assignment

AWS_PROFILE = "pessoal"
AWS_REGION = "us-east-1"

LOG_GROUPS = {
    "springboot": "/aws/lambda/order-processor-springboot",
    "quarkus-jvm": "/aws/lambda/order-processor-quarkus-jvm",
    "quarkus-native": "/aws/lambda/order-processor-quarkus-native",
}

with open("/home/bernardo/Programming/ecommerce-tcc/analysis/lambda/l1/l1_init_durations.json") as f:
    TARGETS = json.load(f)


def parse_report_line(message, timestamp_ms):
    result = {"timestamp_ms": timestamp_ms}
    m = re.search(r"RequestId:\s*([a-f0-9-]+)", message)
    if m:
        result["request_id"] = m.group(1)
    patterns = {
        "duration_ms": r"Duration:\s*([\d.]+)\s*ms",
        "billed_duration_ms": r"Billed Duration:\s*([\d.]+)\s*ms",
        "max_memory_used_mb": r"Max Memory Used:\s*(\d+)\s*MB",
        "init_duration_ms": r"Init Duration:\s*([\d.]+)\s*ms",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, message)
        if m:
            result[key] = float(m.group(1))
    return result


def fetch_report_events(log_group):
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    client = session.client("logs")
    events = []
    paginator = client.get_paginator("filter_log_events")
    for page in paginator.paginate(logGroupName=log_group, filterPattern='"Init Duration"'):
        for e in page.get("events", []):
            events.append(e)
    return events


def match_targets(targets, candidates, tolerance_ms=0.5):
    n = len(targets)
    matched = [None] * n
    diffs = [None] * n
    if not candidates:
        return matched, diffs
    cand_values = np.array([c["init_duration_ms"] for c in candidates])
    cost = np.abs(np.subtract.outer(np.array(targets), cand_values))
    row_ind, col_ind = linear_sum_assignment(cost)
    for r, c in zip(row_ind, col_ind):
        d = cost[r, c]
        if d <= tolerance_ms:
            matched[r] = candidates[c]
            diffs[r] = d
    return matched, diffs


for runtime, log_group in LOG_GROUPS.items():
    print(f"\n{'=' * 70}\n{runtime}  ({log_group})\n{'=' * 70}")
    raw_events = fetch_report_events(log_group)
    print(f"Total de linhas com 'Init Duration' no log group (L1+L2+L3 misturados): {len(raw_events)}")

    candidates = []
    for e in raw_events:
        p = parse_report_line(e["message"], e["timestamp"])
        if "init_duration_ms" in p:
            candidates.append(p)

    # duplicate check across ALL candidates found (not just matched) --
    # same request_id appearing twice, or timestamps within 2s of each other
    # with the same init_duration_ms (H1b-style duplicate signature).
    seen_req = {}
    dup_req = []
    for c in candidates:
        rid = c.get("request_id")
        if rid in seen_req:
            dup_req.append((seen_req[rid], c))
        else:
            seen_req[rid] = c
    if dup_req:
        print(f"  [ALERTA] {len(dup_req)} request_id duplicado(s) encontrado(s) no log group inteiro:")
        for a, b in dup_req:
            print(f"    {a} <-> {b}")
    else:
        print("  Nenhum request_id duplicado em todo o log group (L1+L2+L3).")

    targets = sorted(TARGETS[runtime]["init_duration_ms"])
    matched, diffs = match_targets(targets, candidates, tolerance_ms=0.5)
    n_matched = sum(1 for m in matched if m is not None)
    print(f"\nMatch fingerprint (tolerancia 0.5ms): {n_matched}/{len(targets)}")
    print(f"{'target_ms':>10} | {'matched_ms':>10} | {'diff_ms':>8} | {'timestamp_utc':>20} | request_id")
    prev_ts = None
    for t, m, d in zip(targets, matched, diffs):
        if m is None:
            print(f"{t:10.2f} | {'NO MATCH':>10} |")
            continue
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(m["timestamp_ms"] / 1000, tz=timezone.utc)
        gap = "" if prev_ts is None else f"  (+{(ts - prev_ts).total_seconds() / 60:.1f} min)"
        print(f"{t:10.2f} | {m['init_duration_ms']:10.2f} | {d:8.3f} | {ts.isoformat():>20} | {m.get('request_id')}{gap}")
        prev_ts = ts

    # check for any pair of MATCHED candidates sharing timestamp/request_id
    matched_only = [m for m in matched if m is not None]
    rids = [m.get("request_id") for m in matched_only]
    if len(rids) != len(set(rids)):
        print("  [ALERTA] dois alvos casados com o MESMO request_id -- duplicata real de match.")
    tss = sorted(m["timestamp_ms"] for m in matched_only)
    close_pairs = [(a, b) for a, b in zip(tss, tss[1:]) if (b - a) < 5000]
    if close_pairs:
        print(f"  [ALERTA] pares de timestamp casados com <5s de diferenca: {close_pairs}")
