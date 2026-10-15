#!/usr/bin/env python3
"""Diagnostico: lista TODOS os cold starts (linha REPORT com Init Duration) de
cada log group, com timestamp, para inspecionar se o fingerprint matching do
quarkus-jvm (targets arredondados a 1ms) esta pegando invocacoes de sessoes
erradas (L2/L3 de outras datas) em vez das 10 do L1 de 03/07/2026.
"""
import json
import re
from datetime import datetime, timezone

import boto3

AWS_PROFILE = "pessoal"
AWS_REGION = "us-east-1"
LOG_GROUPS = {
    "springboot": "/aws/lambda/order-processor-springboot",
    "quarkus-jvm": "/aws/lambda/order-processor-quarkus-jvm",
    "quarkus-native": "/aws/lambda/order-processor-quarkus-native",
}

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
client = session.client("logs")

for runtime, lg in LOG_GROUPS.items():
    print(f"\n{'='*70}\n{runtime}\n{'='*70}")
    events = []
    paginator = client.get_paginator("filter_log_events")
    for page in paginator.paginate(logGroupName=lg, filterPattern='"Init Duration"'):
        events.extend(page.get("events", []))
    parsed = []
    for e in events:
        msg = e["message"]
        mi = re.search(r"Init Duration:\s*([\d.]+)\s*ms", msg)
        md = re.search(r"(?<!Init )(?<!Billed )Duration:\s*([\d.]+)\s*ms", msg)
        mr = re.search(r"RequestId:\s*([a-f0-9-]+)", msg)
        ts = datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc)
        parsed.append((ts, float(mi.group(1)) if mi else None,
                       float(md.group(1)) if md else None,
                       mr.group(1) if mr else None))
    parsed.sort()
    # agrupa por dia
    from collections import Counter
    days = Counter(ts.date().isoformat() for ts, *_ in parsed)
    print("cold starts por dia:", dict(days))
    print(f"\n{'timestamp_utc':>27} | {'init_ms':>9} | {'dur_ms':>9} | request_id")
    for ts, init, dur, rid in parsed:
        di = f"{init:9.2f}" if init is not None else f"{'None':>9}"
        dd = f"{dur:9.2f}" if dur is not None else f"{'None':>9}"
        print(f"{ts.isoformat():>27} | {di} | {dd} | {rid}")
