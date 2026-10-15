#!/usr/bin/env python3
"""Le o NDJSON bruto do k6 (gz) em streaming e grava uma linha por requisicao:
epoch_ms, duracao_ms, phase, operation, status, expected_response.
Uso: extrai_requisicoes.py <raw.json.gz> <saida.csv.gz>   (roda no runner, apos cada rodada)"""
import csv, gzip, json, sys
from datetime import datetime


def epoch(s):
    """k6 grava RFC3339 com ate 9 casas e Z ou offset; o fromisoformat do Python 3.9 nao aceita isso."""
    t = s.replace("Z", "+00:00"); main, off = t[:-6], t[-6:]
    if "." in main:
        a, b = main.split("."); main = a + "." + (b[:6] + "000000")[:6]
    return datetime.fromisoformat(main + off).timestamp()


n = 0
with gzip.open(sys.argv[1], "rt") as fin, gzip.open(sys.argv[2], "wt", newline="") as fout:
    w = csv.writer(fout)
    w.writerow(["epoch_ms", "duracao_ms", "phase", "operation", "status", "expected_response"])
    for linha in fin:
        if '"http_req_duration"' not in linha or '"Point"' not in linha:
            continue
        o = json.loads(linha)
        if o.get("type") != "Point" or o.get("metric") != "http_req_duration":
            continue
        d = o["data"]; t = d.get("tags", {})
        w.writerow([int(epoch(d["time"]) * 1000), round(d["value"], 3), t.get("phase", ""), t.get("operation", ""),
                    t.get("status", ""), t.get("expected_response", "")])
        n += 1
print(n)
