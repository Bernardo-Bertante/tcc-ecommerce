#!/usr/bin/env python3
"""Extração imediata de uma rodada (roda no runner logo após o k6).

Entradas: JSON bruto do k6 (gz), diretório da rodada (com summary.json), rótulo, rc do k6.
Saídas no diretório:
  latency.json      — mesma forma do oficial (lista de http_req_duration em ordem de emissão)
  timing.json       — janela de carga (1º/último Point com tag phase=load|auxiliary)
  requests.csv.gz   — por requisição: epoch_s, ms, operation, phase, status (análise por segundo)
Imprime em stdout UMA linha TSV para status.tsv (p95/p99/max imediatos).
"""
import csv, datetime as dt, gzip, json, math, os, re, sys

raw, d, tag, rc = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]


_TS = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)$")


def epoch(t):
    # RFC3339 do k6 (nanossegundos, 'Z' ou offset) — python 3.9 do runner não lê isso direto
    b, frac, tz = _TS.match(t).groups()
    base = dt.datetime.fromisoformat(b + ("+00:00" if tz == "Z" else tz))
    return base.timestamp() + (float("0." + frac) if frac else 0.0)


lat, load_t = [], []
with gzip.open(raw, "rt") as f, gzip.open(os.path.join(d, "requests.csv.gz"), "wt", newline="") as out:
    w = csv.writer(out)
    w.writerow(["epoch_s", "ms", "operation", "phase", "status"])
    for line in f:
        if '"http_req_duration"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") != "Point" or o.get("metric") != "http_req_duration":
            continue
        p = o["data"]
        tg = p.get("tags") or {}
        v = p["value"]
        lat.append(v)
        t = p.get("time")
        ph = tg.get("phase")
        if t:
            w.writerow([f"{epoch(t):.3f}", f"{v:.3f}", tg.get("operation", ""), ph or "", tg.get("status", "")])
            if ph in ("load", "auxiliary"):
                load_t.append(t)

json.dump(lat, open(os.path.join(d, "latency.json"), "w"))
load_t.sort()
timing = {"http_req_points": len(lat), "load_points": len(load_t),
          "load_start_utc": load_t[0] if load_t else None, "load_end_utc": load_t[-1] if load_t else None}
json.dump(timing, open(os.path.join(d, "timing.json"), "w"))


def pct(s, q):
    if not s:
        return float("nan")
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


s = sorted(lat)
m = json.load(open(os.path.join(d, "summary.json")))["metrics"] if os.path.exists(os.path.join(d, "summary.json")) else {}
it = m.get("iterations", {}).get("count", 0)
dr = m.get("dropped_iterations", {}).get("count", 0)
fr = m.get("http_req_failed", {}).get("value", m.get("http_req_failed", {}).get("rate", 0)) or 0
gt1 = 100.0 * sum(1 for x in s if x > 1000) / len(s) if s else float("nan")
task = {}
try:
    tj = json.load(open(os.path.join(d, "task_running.json")))["tasks"][0]
    task = {"id": tj["taskArn"].rsplit("/", 1)[-1], "az": tj.get("availabilityZone", "?")}
except Exception:
    pass
print("\t".join(map(str, [tag, timing["load_start_utc"], timing["load_end_utc"], it, dr, f"{fr:.5f}",
                          f"{pct(s, .5):.1f}", f"{pct(s, .95):.1f}", f"{pct(s, .99):.1f}", f"{(s[-1] if s else float('nan')):.1f}",
                          f"{gt1:.2f}", rc, task.get("id", "?"), task.get("az", "?")])))
