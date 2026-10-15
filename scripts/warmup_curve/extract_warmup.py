#!/usr/bin/env python3
"""Seção 6.5 do TCC -- curva de aquecimento por ambiente de execução (Lambda).

Para cada (runtime in {springboot, quarkus-jvm}, rodada in 1..5) reconstrói uma
linha do tempo CONTÍNUA de invocações cobrindo o cenário L2 seguido do L3 (mesmo
log group, L3 roda ~4s depois do fim de L2 e reaproveita os ambientes já quentes
de L2). Extrai TODAS as linhas REPORT via CloudWatch Logs Insights (consultas
binadas de 1 min para não bater o teto de 10.000 linhas/consulta), atribui a
cada invocação um número de sequência POR @logStream (= por ambiente de
execução), e agrega duration por faixa de sequência.

Não reexecuta nenhum teste. Não toca nos CSVs oficiais. Saída em
analysis/lambda/fase4/warmup_curve/.
"""
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3

REPO = os.path.expanduser("~/Programming/ecommerce-tcc")
FASE4 = os.path.join(REPO, "analysis/lambda/fase4")
OUTDIR = os.path.join(FASE4, "warmup_curve")
os.makedirs(OUTDIR, exist_ok=True)

LOG_GROUPS = {
    "springboot": "/aws/lambda/order-processor-springboot",
    "quarkus-jvm": "/aws/lambda/order-processor-quarkus-jvm",
}
RUNTIMES = ["springboot", "quarkus-jvm"]
ROUNDS = [1, 2, 3, 4, 5]

session = boto3.Session(profile_name="pessoal", region_name="us-east-1")
logs = session.client("logs")


def parse_cw_ts(value):
    v = value.strip().replace("Z", "").replace(" ", "T")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def field(row, name):
    for kv in row:
        if kv["field"] == name:
            return kv["value"]
    return None


def run_query(log_group, start_epoch, end_epoch, query, limit=10000, timeout_s=240):
    resp = logs.start_query(logGroupName=log_group, startTime=start_epoch,
                            endTime=end_epoch, queryString=query, limit=limit)
    qid = resp["queryId"]
    waited = 0
    while waited < timeout_s:
        r = logs.get_query_results(queryId=qid)
        if r["status"] == "Complete":
            return r["results"]
        if r["status"] in ("Failed", "Cancelled", "Timeout"):
            raise RuntimeError(f"{r['status']}: {query}")
        time.sleep(2)
        waited += 2
    raise TimeoutError(query)


def run_batch(log_group, chunks, query, limit=10000, timeout_s=300):
    """chunks: list of (start_epoch, end_epoch). Dispara todas as consultas e
    faz polling em paralelo. Retorna lista de listas de results, na ordem."""
    qids = []
    for (s, e) in chunks:
        while True:
            try:
                resp = logs.start_query(logGroupName=log_group, startTime=s,
                                        endTime=e, queryString=query, limit=limit)
                qids.append(resp["queryId"])
                break
            except logs.exceptions.LimitExceededException:
                time.sleep(3)
        time.sleep(0.15)
    out = [None] * len(qids)
    waited = 0
    while waited < timeout_s and any(o is None for o in out):
        for i, qid in enumerate(qids):
            if out[i] is not None:
                continue
            r = logs.get_query_results(queryId=qid)
            if r["status"] == "Complete":
                out[i] = r["results"]
            elif r["status"] in ("Failed", "Cancelled", "Timeout"):
                raise RuntimeError(f"{r['status']} chunk {i}")
        if any(o is None for o in out):
            time.sleep(3)
            waited += 3
    if any(o is None for o in out):
        raise TimeoutError("batch timeout")
    return out


# ---------------------------------------------------------------------------
# 1. Janelas
# ---------------------------------------------------------------------------
def load_windows():
    tj = json.load(open(os.path.join(FASE4, "timestamps.json")))
    l2_r45 = json.load(open(os.path.join(FASE4, "_r4_r5_reconstructed_windows.json")))
    windows = {}  # (runtime, round) -> dict(l2_start,l2_end,l3_start,l3_end, expected_l2, expected_l3)

    for rt in RUNTIMES:
        for r in ROUNDS:
            exp_l2 = json.load(open(os.path.join(FASE4, f"l2-{rt}-r{r}-summary.json")))["metrics"]["http_reqs"]["count"]
            exp_l3 = json.load(open(os.path.join(FASE4, f"l3-{rt}-r{r}-summary.json")))["metrics"]["http_reqs"]["count"]
            if r <= 3:
                l2 = tj[f"l2-{rt}-r{r}"]
                l3 = tj[f"l3-{rt}-r{r}"]
                l2s, l2e = parse_cw_ts(l2["start"]), parse_cw_ts(l2["end"])
                l3s, l3e = parse_cw_ts(l3["start"]), parse_cw_ts(l3["end"])
            else:
                l2 = l2_r45[f"l2-{rt}-r{r}"]
                l2s, l2e = parse_cw_ts(l2["start"]), parse_cw_ts(l2["end"])
                l3s, l3e = reconstruct_l3(rt, r, exp_l3, after=l2e)
            windows[(rt, r)] = dict(l2s=l2s, l2e=l2e, l3s=l3s, l3e=l3e,
                                    exp_l2=exp_l2, exp_l3=exp_l3)
    return windows


def reconstruct_l3(rt, r, expected, after):
    """mesma heurística de reconstruct_windows_r4_r5.py, mas ancorada no mtime
    do summary de L3 e restrita ao bloco de atividade que começa depois de L2."""
    summ = os.path.join(FASE4, f"l3-{rt}-r{r}-summary.json")
    mtime = datetime.fromtimestamp(os.path.getmtime(summ), tz=timezone.utc)
    search_start = min(after, mtime - timedelta(minutes=20))
    search_end = mtime + timedelta(minutes=10)
    rows = run_query(LOG_GROUPS[rt], int(search_start.timestamp()), int(search_end.timestamp()),
                     'filter @type = "REPORT" | stats count(*) as c by bin(1m) as tbin')
    bins = sorted((parse_cw_ts(field(x, "tbin")), int(field(x, "c"))) for x in rows)
    # primeiro minuto ativo (>50) em ou após `after` - 1min
    cutoff = after - timedelta(minutes=1)
    first = None
    for i, (m, c) in enumerate(bins):
        if m >= cutoff and c > 50:
            first = i
            break
    if first is None:
        raise RuntimeError(f"l3-{rt}-r{r}: sem atividade após L2")
    cum, end = 0, first
    for i in range(first, len(bins)):
        cum += bins[i][1]
        end = i
        if cum >= expected * 0.97:
            break
    return bins[first][0], bins[end][0] + timedelta(minutes=1)


# ---------------------------------------------------------------------------
# 2. Extração das linhas REPORT
# ---------------------------------------------------------------------------
REPORT_Q = (
    'filter @type = "REPORT" '
    '| fields @timestamp, @logStream, @requestId, @billedDuration, @duration, '
    '@initDuration, @memorySize, @maxMemoryUsed '
    '| sort @timestamp asc'
)


def extract_reports(rt, w):
    lg = LOG_GROUPS[rt]
    win_start = w["l2s"] - timedelta(seconds=5)
    win_end = w["l3e"] + timedelta(seconds=90)
    # chunks de 1 min
    chunks = []
    t = win_start.replace(second=0, microsecond=0)
    while t < win_end:
        nt = t + timedelta(minutes=1)
        chunks.append((int(t.timestamp()), int(nt.timestamp()) + 5))  # +5s overlap p/ não perder na borda
        t = nt
    results = []
    B = 12
    for i in range(0, len(chunks), B):
        results.extend(run_batch(lg, chunks[i:i + B], REPORT_Q))
    # dedup por requestId
    seen = {}
    for res in results:
        for row in res:
            rid = field(row, "@requestId")
            ts = field(row, "@timestamp")
            if rid is None or ts is None:
                continue
            if rid in seen:
                continue
            dur = field(row, "@duration")
            billed = field(row, "@billedDuration")
            initd = field(row, "@initDuration")
            seen[rid] = dict(
                request_id=rid,
                ts=parse_cw_ts(ts),
                log_stream=field(row, "@logStream"),
                duration_ms=float(dur) if dur not in (None, "") else None,
                billed_ms=float(billed) if billed not in (None, "") else None,
                init_ms=float(initd) if initd not in (None, "") else None,
                mem_size=field(row, "@memorySize"),
                max_mem_used=field(row, "@maxMemoryUsed"),
            )
    recs = sorted(seen.values(), key=lambda x: x["ts"])
    # rótulo de cenário
    for rec in recs:
        if w["l2s"] - timedelta(seconds=5) <= rec["ts"] <= w["l2e"] + timedelta(seconds=90):
            rec["scenario"] = "L2"
        elif w["l3s"] - timedelta(seconds=5) <= rec["ts"] <= w["l3e"] + timedelta(seconds=90):
            rec["scenario"] = "L3"
        else:
            rec["scenario"] = "gap"
    return recs


# ---------------------------------------------------------------------------
# 3. Sequência por ambiente + agregação
# ---------------------------------------------------------------------------
BANDS = [(1, 1), (2, 10), (11, 100), (101, 1000), (1001, 5000), (5001, 10**9)]
BAND_LABELS = ["1", "2-10", "11-100", "101-1000", "1001-5000", "5001+"]


def band_of(seq):
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= seq <= hi:
            return BAND_LABELS[i]
    return "?"


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    m = n // 2
    return xs[m] if n % 2 else (xs[m - 1] + xs[m]) / 2.0


def process():
    windows = load_windows()
    all_records = []          # long-form, todas as invocações
    band_rows = []            # faixa x runtime x rodada x cenário
    win_dump = {}

    for rt in RUNTIMES:
        for r in ROUNDS:
            w = windows[(rt, r)]
            win_dump[f"{rt}-r{r}"] = {
                "l2": [w["l2s"].isoformat(), w["l2e"].isoformat()],
                "l3": [w["l3s"].isoformat(), w["l3e"].isoformat()],
                "expected_l2": w["exp_l2"], "expected_l3": w["exp_l3"],
            }
            print(f"[{rt} r{r}] janela L2 {w['l2s'].time()}..{w['l2e'].time()} "
                  f"L3 {w['l3s'].time()}..{w['l3e'].time()}", flush=True)
            recs = extract_reports(rt, w)
            n_l2 = sum(1 for x in recs if x["scenario"] == "L2")
            n_l3 = sum(1 for x in recs if x["scenario"] == "L3")
            print(f"    REPORT: {len(recs)} total | L2={n_l2} (esp {w['exp_l2']}, "
                  f"{n_l2/w['exp_l2']:.1%}) | L3={n_l3} (esp {w['exp_l3']}, {n_l3/w['exp_l3']:.1%})",
                  flush=True)

            # sequência por ambiente (cumulativa L2->L3)
            per_stream = defaultdict(int)
            for rec in recs:
                per_stream[rec["log_stream"]] += 1
                seq = per_stream[rec["log_stream"]]
                rec["seq"] = seq
                rec["band"] = band_of(seq)
                rec["runtime"] = rt
                rec["round"] = r
                rec["env_total_in_window"] = None  # preenchido abaixo
            stream_totals = dict(per_stream)
            for rec in recs:
                rec["env_total_in_window"] = stream_totals[rec["log_stream"]]

            all_records.extend(recs)

            # agregação por faixa (por cenário e combinado)
            for scen in ("L2", "L3", "L2+L3"):
                subset = [x for x in recs if (x["scenario"] == scen if scen != "L2+L3"
                                              else x["scenario"] in ("L2", "L3"))]
                tot = len(subset)
                for lbl in BAND_LABELS:
                    d = [x["duration_ms"] for x in subset if x["band"] == lbl and x["duration_ms"] is not None]
                    band_rows.append(dict(
                        runtime=rt, round=r, scenario=scen, band=lbl,
                        n=len(d),
                        frac_of_scenario=(len(d) / tot) if tot else 0.0,
                        duration_mean=(sum(d) / len(d)) if d else None,
                        duration_median=median(d),
                        duration_p90=(sorted(d)[min(len(d) - 1, int(0.9 * len(d)))] if d else None),
                    ))

    json.dump(win_dump, open(os.path.join(OUTDIR, "windows_used.json"), "w"), indent=2)

    # ---- CSV long-form (todas invocações) ----
    import csv
    with open(os.path.join(OUTDIR, "invocations_long.csv"), "w", newline="") as fp:
        wr = csv.writer(fp)
        wr.writerow(["runtime", "round", "scenario", "ts", "log_stream", "seq",
                     "band", "env_total_in_window", "duration_ms", "billed_ms",
                     "init_ms", "mem_size", "max_mem_used"])
        for x in all_records:
            wr.writerow([x["runtime"], x["round"], x["scenario"], x["ts"].isoformat(),
                         x["log_stream"], x["seq"], x["band"], x["env_total_in_window"],
                         x["duration_ms"], x["billed_ms"], x["init_ms"],
                         x["mem_size"], x["max_mem_used"]])

    # ---- CSV por faixa (por rodada) ----
    with open(os.path.join(OUTDIR, "band_stats_by_round.csv"), "w", newline="") as fp:
        wr = csv.DictWriter(fp, fieldnames=["runtime", "round", "scenario", "band",
                                            "n", "frac_of_scenario", "duration_mean",
                                            "duration_median", "duration_p90"])
        wr.writeheader()
        for row in band_rows:
            wr.writerow(row)

    # ---- CSV por faixa (agregado sobre as 5 rodadas) ----
    agg = defaultdict(list)  # (runtime, scenario, band) -> list of duration_ms
    aggn = defaultdict(int)
    aggtot = defaultdict(int)
    for x in all_records:
        if x["duration_ms"] is None:
            continue
        for scen in ([x["scenario"], "L2+L3"] if x["scenario"] in ("L2", "L3") else []):
            agg[(x["runtime"], scen, x["band"])].append(x["duration_ms"])
    for x in all_records:
        for scen in ([x["scenario"], "L2+L3"] if x["scenario"] in ("L2", "L3") else []):
            aggtot[(x["runtime"], scen)] += 1
    with open(os.path.join(OUTDIR, "band_stats_aggregate.csv"), "w", newline="") as fp:
        wr = csv.writer(fp)
        wr.writerow(["runtime", "scenario", "band", "n", "frac_of_scenario",
                     "duration_mean", "duration_median", "duration_p90"])
        for rt in RUNTIMES:
            for scen in ("L2", "L3", "L2+L3"):
                for lbl in BAND_LABELS:
                    d = agg.get((rt, scen, lbl), [])
                    tot = aggtot.get((rt, scen), 0)
                    wr.writerow([rt, scen, lbl, len(d),
                                 f"{(len(d)/tot):.4f}" if tot else "0",
                                 f"{sum(d)/len(d):.2f}" if d else "",
                                 f"{median(d):.2f}" if d else "",
                                 f"{sorted(d)[min(len(d)-1,int(0.9*len(d)))]:.2f}" if d else ""])

    print("\nOK. Saída em", OUTDIR)
    return all_records, band_rows


if __name__ == "__main__":
    process()
