#!/usr/bin/env python3
"""Extrai o campo `Duration` (execucao pos-init) das linhas REPORT do CloudWatch
para as MESMAS 32 invocacoes de L1 ja identificadas na investigacao anterior
(l1_dup_investigation.py) -- so que aqui a selecao e feita por JANELA TEMPORAL
da sessao, nao por fingerprint numerico.

Motivo: o fingerprint contra os init_duration_ms salvos em l1_init_durations.json
funciona para springboot/native (valores com 2 casas decimais, distintos), mas
para quarkus-jvm os alvos foram arredondados a 1ms inteiro e o log group tem
centenas de cold starts de L2/L3 (07-05, 07-06, 07-16) que colidem dentro da
tolerancia. A selecao por janela e inequivoca: cada sessao L1 e um bloco de
~11 invocacoes espacadas 15 min, isolado no tempo.

Janelas confirmadas por inspecao (l1_window_probe.py), em UTC:
  springboot      2026-07-02 19:43 .. 22:13   -> 11 invocacoes
  quarkus-native  2026-07-03 13:26 .. 15:56   -> 11 invocacoes
  quarkus-jvm     2026-07-03 16:58 .. 19:28   -> 11 invocacoes (10 validas + 1 outlier)

A 11a invocacao do quarkus-jvm (a primeira da sessao, 16:58:49Z, init 1492.52ms)
e o outlier excluido da analise principal -- e a unica cujo init_duration NAO
esta na lista dos 10 valores salvos em l1_init_durations.json.
"""
import csv
import json
import re
from datetime import datetime, timezone

import boto3
import numpy as np

AWS_PROFILE = "pessoal"
AWS_REGION = "us-east-1"
BASE = "/home/bernardo/Programming/ecommerce-tcc/analysis/lambda/l1"

LOG_GROUPS = {
    "springboot": "/aws/lambda/order-processor-springboot",
    "quarkus-jvm": "/aws/lambda/order-processor-quarkus-jvm",
    "quarkus-native": "/aws/lambda/order-processor-quarkus-native",
}

# (inicio, fim) UTC de cada sessao L1
WINDOWS = {
    "springboot":     ("2026-07-02T19:40:00Z", "2026-07-02T22:20:00Z"),
    "quarkus-native": ("2026-07-03T13:20:00Z", "2026-07-03T16:00:00Z"),
    "quarkus-jvm":    ("2026-07-03T16:50:00Z", "2026-07-03T19:35:00Z"),
}

with open(f"{BASE}/l1_init_durations.json") as f:
    TARGETS = json.load(f)


def parse_report_line(message, timestamp_ms):
    result = {"timestamp_ms": timestamp_ms}
    m = re.search(r"RequestId:\s*([a-f0-9-]+)", message)
    if m:
        result["request_id"] = m.group(1)
    patterns = {
        "duration_ms": r"(?<!Init )(?<!Billed )Duration:\s*([\d.]+)\s*ms",
        "billed_duration_ms": r"Billed Duration:\s*([\d.]+)\s*ms",
        "max_memory_used_mb": r"Max Memory Used:\s*(\d+)\s*MB",
        "init_duration_ms": r"Init Duration:\s*([\d.]+)\s*ms",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, message)
        if m:
            result[key] = float(m.group(1))
    return result


def to_epoch_ms(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
client = session.client("logs")

rows = []
summary = {}
for runtime, lg in LOG_GROUPS.items():
    start_iso, end_iso = WINDOWS[runtime]
    start_ms, end_ms = to_epoch_ms(start_iso), to_epoch_ms(end_iso)
    print(f"\n{'='*80}\n{runtime}  ({lg})\n  janela: {start_iso} .. {end_iso}\n{'='*80}")

    events = []
    paginator = client.get_paginator("filter_log_events")
    for page in paginator.paginate(
        logGroupName=lg,
        startTime=start_ms,
        endTime=end_ms,
        filterPattern='"REPORT RequestId"',
    ):
        events.extend(page.get("events", []))

    parsed = [parse_report_line(e["message"], e["timestamp"]) for e in events]
    parsed = [p for p in parsed if "init_duration_ms" in p and "duration_ms" in p]
    parsed.sort(key=lambda p: p["timestamp_ms"])

    jvm_targets = set(TARGETS[runtime]["init_duration_ms"])
    print(f"invocacoes REPORT (cold start) na janela: {len(parsed)}")
    print(f"{'#':>2} | {'timestamp_utc':>25} | {'init_ms':>9} | {'DURATION':>9} | "
          f"{'billed':>8} | {'mem':>4} | outlier? | request_id")

    durations_valid = []
    for i, p in enumerate(parsed, 1):
        ts = datetime.fromtimestamp(p["timestamp_ms"] / 1000, tz=timezone.utc)
        # outlier do quarkus-jvm: init_duration nao consta na lista dos 10 salvos
        is_outlier = False
        if runtime == "quarkus-jvm":
            near = any(abs(p["init_duration_ms"] - t) <= 0.5 for t in jvm_targets)
            is_outlier = not near
        if not is_outlier:
            durations_valid.append(p["duration_ms"])
        print(f"{i:>2} | {ts.isoformat():>25} | {p['init_duration_ms']:9.2f} | "
              f"{p['duration_ms']:9.2f} | {p.get('billed_duration_ms', float('nan')):8.1f} | "
              f"{p.get('max_memory_used_mb', float('nan')):4.0f} | "
              f"{'  OUTLIER' if is_outlier else '        '} | {p.get('request_id')}")
        rows.append({
            "runtime": runtime,
            "request_id": p.get("request_id"),
            "timestamp_utc": ts.isoformat(),
            "init_duration_ms": p["init_duration_ms"],
            "duration_ms": p["duration_ms"],
            "billed_duration_ms": p.get("billed_duration_ms"),
            "max_memory_used_mb": p.get("max_memory_used_mb"),
            "excluded_outlier": is_outlier,
        })

    arr = np.array(durations_valid, dtype=float)
    summary[runtime] = {
        "n_valid": int(len(arr)),
        "duration_mean_ms": round(float(np.mean(arr)), 2),
        "duration_std_ms": round(float(np.std(arr, ddof=1)), 2),
        "duration_median_ms": round(float(np.median(arr)), 2),
        "duration_min_ms": round(float(np.min(arr)), 2),
        "duration_max_ms": round(float(np.max(arr)), 2),
        "init_duration_mean_ms": TARGETS[runtime]["mean_ms"],
        "init_plus_duration_ms": round(TARGETS[runtime]["mean_ms"] + float(np.mean(arr)), 2),
    }
    s = summary[runtime]
    print(f"\n  Duration (pos-init) media  : {s['duration_mean_ms']:.1f} ms  "
          f"(std {s['duration_std_ms']:.1f}, mediana {s['duration_median_ms']:.1f}, "
          f"min {s['duration_min_ms']:.1f}, max {s['duration_max_ms']:.1f}, n={s['n_valid']})")
    print(f"  Init Duration media (JSON) : {s['init_duration_mean_ms']:.1f} ms")
    print(f"  Init + Duration            : {s['init_plus_duration_ms']:.1f} ms")

with open(f"{BASE}/l1_duration_postinit.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
with open(f"{BASE}/l1_duration_postinit_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n\nescrito: {BASE}/l1_duration_postinit.csv  ({len(rows)} linhas)")
print(f"escrito: {BASE}/l1_duration_postinit_summary.json")
print("\nRESUMO FINAL (Duration = execucao pos-init, linha REPORT do CloudWatch)")
for rt, s in summary.items():
    print(f"  {rt:15} n={s['n_valid']:2}  Duration = {s['duration_mean_ms']:8.1f} +/- {s['duration_std_ms']:.1f} ms"
          f"   |  Init {s['init_duration_mean_ms']:.1f} + Dur = {s['init_plus_duration_ms']:.1f} ms")
