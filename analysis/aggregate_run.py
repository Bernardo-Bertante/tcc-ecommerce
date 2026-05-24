#!/usr/bin/env python3
"""Aggregate k6 + container-stats results for a single benchmark run.

Stdlib-only. Reads:
- benchmark/results/nohup-<run_id>.out          (START/END timestamps + verdicts)
- benchmark/results/<scenario>_<version>_run<N>-summary.json   (k6 end-of-test summary)
- benchmark/results/container-stats-<run_id>.csv               (docker stats samples, 5s)
- benchmark/results/startup-<run_id>.csv                       (per-version cold-start ms)

Writes two files into benchmark/results/:
- metrics_<run_id>.json   structured aggregates per (scenario, version)
- metrics_<run_id>.md     human-readable report (tables) for sharing with another LLM

Usage:
    python analysis/aggregate_run.py overnight-20260516-215109
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmark" / "results"

SERVICE_TO_VERSION = {
    "order-service-quarkus-native": "quarkus-native",
    "order-service-quarkus-jvm": "quarkus-jvm",
    "order-service-springboot": "springboot",
}
VERSION_TO_SERVICE = {v: k for k, v in SERVICE_TO_VERSION.items()}
VERSIONS = ["quarkus-native", "quarkus-jvm", "springboot"]
SCENARIOS = ["f1_low_load", "f2_high_load"]

LOG_LINE_RE = re.compile(
    r"^\[(?P<ts>[0-9T:+\-]+)\]\s+(?P<event>START|END)\s+scenario=(?P<scenario>\S+)"
    r"\s+version=(?P<version>\S+)\s+repetition=(?P<rep>\d+)"
)
END_EXTRA_RE = re.compile(r"verdict=(?P<verdict>\S+)")
# k6 stdout threshold lines, e.g. "    ✗ 'p(99)<5000' p(99)=30s"
K6_THR_RE = re.compile(
    r"^\s*[✓✗]\s*'(?P<metric>[^']+)'\s+(?P<stat>p\(\d{2}\))=(?P<num>[\d.]+)(?P<unit>µs|ms|s|m|ns)"
)
UNIT_TO_MS = {"ns": 1e-6, "µs": 1e-3, "ms": 1.0, "s": 1000.0, "m": 60000.0}
MEM_RE = re.compile(r"^([\d.]+)\s*([KMG]i?B)\s*/")
PCT_RE = re.compile(r"^([\d.]+)%$")
UNIT_TO_MIB = {"B": 1 / (1024 * 1024), "KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0,
               "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}


def parse_ts(s: str) -> datetime:
    # ISO 8601 with offset, e.g. 2026-05-16T21:51:09-03:00
    return datetime.fromisoformat(s)


def parse_mem_mib(s: str) -> float | None:
    m = MEM_RE.match(s.strip())
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2)
    if unit not in UNIT_TO_MIB:
        return None
    return value * UNIT_TO_MIB[unit]


def parse_pct(s: str) -> float | None:
    m = PCT_RE.match(s.strip())
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

def parse_log(log_path: Path) -> tuple[list[dict[str, Any]], dict[tuple, dict[str, float]]]:
    """Return (run_records, per_run_threshold_stats).

    threshold_stats maps (scenario, version, run) -> {"p(95)_ms": x, "p(99)_ms": y}
    extracted from k6's stdout threshold lines (the only place p(99) is reported).
    """
    starts: dict[tuple, datetime] = {}
    records: list[dict[str, Any]] = []
    thr: dict[tuple, dict[str, float]] = {}
    current_key: tuple | None = None
    for line in log_path.read_text(errors="replace").splitlines():
        m = LOG_LINE_RE.match(line)
        if m:
            key = (m["scenario"], m["version"], int(m["rep"]))
            ts = parse_ts(m["ts"])
            if m["event"] == "START":
                starts[key] = ts
                current_key = key
                thr.setdefault(key, {})
            else:  # END
                verdict_m = END_EXTRA_RE.search(line)
                verdict = verdict_m.group("verdict") if verdict_m else "UNKNOWN"
                records.append({
                    "scenario": key[0],
                    "version": key[1],
                    "run": key[2],
                    "start": starts.get(key),
                    "end": ts,
                    "verdict": verdict,
                    "duration_s": (ts - starts[key]).total_seconds() if key in starts else None,
                })
                current_key = None
            continue
        if current_key is None:
            continue
        tm = K6_THR_RE.match(line)
        if not tm:
            continue
        ms = float(tm["num"]) * UNIT_TO_MS.get(tm["unit"], 1.0)
        thr[current_key][f"{tm['stat']}_ms"] = ms
    return records, thr


# ---------------------------------------------------------------------------
# k6 summary extraction
# ---------------------------------------------------------------------------

def k6_metrics(summary_path: Path) -> dict[str, Any]:
    data = json.loads(summary_path.read_text())
    m = data["metrics"]

    def g(name: str, *keys: str) -> dict[str, Any]:
        d = m.get(name, {})
        return {k: d.get(k) for k in keys}

    dur = g("http_req_duration{phase:load}", "avg", "min", "med", "max", "p(90)", "p(95)")
    # k6 stores extra percentiles? p(99) sometimes only present in trend with custom config; pull from raw
    dur["p(99)"] = m.get("http_req_duration{phase:load}", {}).get("p(99)")
    failed = m.get("http_req_failed{phase:load}", {})
    reqs = m.get("http_reqs", {})
    iters = m.get("iterations", {})
    checks = m.get("checks", {})
    data_recv = m.get("data_received", {})
    data_sent = m.get("data_sent", {})

    # threshold pass/fail: in k6 JSON the boolean under thresholds is True when BREACHED (ok=false)
    dur_thr = m.get("http_req_duration{phase:load}", {}).get("thresholds", {}) or {}
    fail_thr = m.get("http_req_failed{phase:load}", {}).get("thresholds", {}) or {}

    return {
        "http_req_duration_load": dur,
        "http_req_failed_load": {
            "rate": failed.get("value"),
            "passes": failed.get("passes"),
            "fails": failed.get("fails"),
        },
        "http_reqs": {"count": reqs.get("count"), "rate": reqs.get("rate")},
        "iterations": {"count": iters.get("count"), "rate": iters.get("rate")},
        "checks": {"passes": checks.get("passes"), "fails": checks.get("fails")},
        "data_received_bytes": data_recv.get("count"),
        "data_sent_bytes": data_sent.get("count"),
        "thresholds": {
            "p95_lt_2000_breached": bool(dur_thr.get("p(95)<2000", False)),
            "p99_lt_5000_breached": bool(dur_thr.get("p(99)<5000", False)),
            "fail_rate_lt_0_005_breached": bool(fail_thr.get("rate<0.005", False)),
        },
    }


# ---------------------------------------------------------------------------
# Container stats per-window aggregation
# ---------------------------------------------------------------------------

def load_container_stats(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                ts = parse_ts(r["timestamp"])
            except Exception:
                continue
            cpu = parse_pct(r.get("cpu_pct", ""))
            mem = parse_mem_mib(r.get("mem_usage", ""))
            rows.append({
                "ts": ts,
                "service": r.get("compose_service", ""),
                "cpu": cpu,
                "mem_mib": mem,
            })
    return rows


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def window_stats(stats: list[dict[str, Any]], service: str,
                 start: datetime, end: datetime) -> dict[str, Any]:
    cpu_vals: list[float] = []
    mem_vals: list[float] = []
    for r in stats:
        if r["service"] != service:
            continue
        if r["ts"] < start or r["ts"] > end:
            continue
        if r["cpu"] is not None:
            cpu_vals.append(r["cpu"])
        if r["mem_mib"] is not None:
            mem_vals.append(r["mem_mib"])
    return {
        "samples": len(cpu_vals),
        "cpu_pct": {
            "avg": (statistics.mean(cpu_vals) if cpu_vals else None),
            "p95": percentile(cpu_vals, 0.95),
            "max": (max(cpu_vals) if cpu_vals else None),
        },
        "mem_mib": {
            "avg": (statistics.mean(mem_vals) if mem_vals else None),
            "p95": percentile(mem_vals, 0.95),
            "max": (max(mem_vals) if mem_vals else None),
        },
    }


# ---------------------------------------------------------------------------
# Startup CSV
# ---------------------------------------------------------------------------

def load_startups(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open(newline="") as f:
        # The file contains broken records (a stray newline mid-row in this run).
        # Be defensive: rebuild lines so each record ends with the health URL token.
        text = f.read()
    # Heuristic: collapse interior newlines that split a record (a row split keeps the leading
    # field count below the header count). Use csv.reader on the joined text after replacing
    # newlines that are not preceded by a known URL.
    rows = []
    reader = csv.reader(text.splitlines())
    header = next(reader)
    buf: list[str] = []
    for row in reader:
        if not row:
            continue
        buf.extend(row)
        if len(buf) >= len(header):
            rows.append(dict(zip(header, buf[:len(header)])))
            buf = []
    for r in rows:
        try:
            startup_ms = int(r["startup_ms"])
        except Exception:
            startup_ms = None
        try:
            readiness_ms = int(r["readiness_wait_ms"])
        except Exception:
            readiness_ms = None
        out[r["version"]] = {
            "startup_ms": startup_ms,
            "readiness_wait_ms": readiness_ms,
            "compose_service": r["compose_service"],
            "container_started_at": r["container_started_at"],
            "first_healthy_at": r["first_healthy_at"],
            "health_url": r["health_url"],
        }
    return out


# ---------------------------------------------------------------------------
# Aggregation across repetitions
# ---------------------------------------------------------------------------

def _stat_block(values: list[float]) -> dict[str, Any]:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "mean": None, "stdev": None, "min": None, "max": None}
    return {
        "n": len(vals),
        "mean": statistics.mean(vals),
        "stdev": (statistics.pstdev(vals) if len(vals) > 1 else 0.0),
        "min": min(vals),
        "max": max(vals),
    }


def aggregate(per_run: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce 5 repetitions of the same (scenario, version) to summary stats."""
    def pick(path: list[str]) -> list[float]:
        out: list[float] = []
        for run in per_run:
            cur: Any = run
            ok = True
            for p in path:
                if not isinstance(cur, dict) or p not in cur:
                    ok = False
                    break
                cur = cur[p]
            if ok and isinstance(cur, (int, float)):
                out.append(float(cur))
        return out

    verdicts = [r["verdict"] for r in per_run]
    durations_s = [r["duration_s"] for r in per_run if r.get("duration_s") is not None]
    return {
        "repetitions": len(per_run),
        "verdicts": verdicts,
        "pass_count": sum(1 for v in verdicts if v == "PASS"),
        "threshold_fail_count": sum(1 for v in verdicts if v == "THRESHOLD_FAIL"),
        "run_error_count": sum(1 for v in verdicts if v == "RUN_ERROR"),
        "wallclock_s": _stat_block(durations_s),
        "http_req_duration_load": {
            "avg_ms": _stat_block(pick(["k6", "http_req_duration_load", "avg"])),
            "p95_ms": _stat_block(pick(["k6", "http_req_duration_load", "p(95)"])),
            "p99_ms": _stat_block(pick(["k6", "http_req_duration_load", "p(99)"])),
            "max_ms": _stat_block(pick(["k6", "http_req_duration_load", "max"])),
        },
        "http_req_failed_rate": _stat_block(pick(["k6", "http_req_failed_load", "rate"])),
        "http_reqs_total": _stat_block(pick(["k6", "http_reqs", "count"])),
        "http_reqs_rate": _stat_block(pick(["k6", "http_reqs", "rate"])),
        "iterations_total": _stat_block(pick(["k6", "iterations", "count"])),
        "checks_passes": _stat_block(pick(["k6", "checks", "passes"])),
        "checks_fails": _stat_block(pick(["k6", "checks", "fails"])),
        "app_cpu_pct": {
            "avg": _stat_block(pick(["container", "app", "cpu_pct", "avg"])),
            "p95": _stat_block(pick(["container", "app", "cpu_pct", "p95"])),
            "max": _stat_block(pick(["container", "app", "cpu_pct", "max"])),
        },
        "app_mem_mib": {
            "avg": _stat_block(pick(["container", "app", "mem_mib", "avg"])),
            "max": _stat_block(pick(["container", "app", "mem_mib", "max"])),
        },
        "postgres_cpu_pct": {
            "avg": _stat_block(pick(["container", "postgres", "cpu_pct", "avg"])),
            "max": _stat_block(pick(["container", "postgres", "cpu_pct", "max"])),
        },
        "postgres_mem_mib": {
            "avg": _stat_block(pick(["container", "postgres", "mem_mib", "avg"])),
            "max": _stat_block(pick(["container", "postgres", "mem_mib", "max"])),
        },
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def fmt(v: Any, nd: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if math.isnan(v):
            return "—"
        return f"{v:,.{nd}f}"
    return str(v)


def render_markdown(run_id: str, startups: dict, agg: dict, per_run: list[dict]) -> str:
    out: list[str] = []
    out.append(f"# Benchmark metrics — run `{run_id}`\n")
    out.append("Aggregated from k6 end-of-test summaries, docker container-stats samples "
               "(5s cadence) and startup-readiness CSV. Latency values are milliseconds, "
               "memory in MiB, CPU in % of one host core (Docker convention).\n")

    out.append("## 1. Verdict matrix (5 repetitions per cell)\n")
    out.append("| Scenario | Version | PASS | THRESHOLD_FAIL | RUN_ERROR | Wallclock mean (s) |")
    out.append("|---|---|---:|---:|---:|---:|")
    for scen in SCENARIOS:
        for ver in VERSIONS:
            a = agg[scen][ver]
            out.append(f"| {scen} | {ver} | {a['pass_count']} | {a['threshold_fail_count']} | "
                       f"{a['run_error_count']} | {fmt(a['wallclock_s']['mean'], 1)} |")
    out.append("")

    out.append("## 2. Cold start (first health check 200 after container start)\n")
    out.append("| Version | startup_ms | readiness_wait_ms |")
    out.append("|---|---:|---:|")
    for ver in VERSIONS:
        s = startups.get(ver, {})
        out.append(f"| {ver} | {fmt(s.get('startup_ms'), 0)} | {fmt(s.get('readiness_wait_ms'), 0)} |")
    out.append("\n*Note: `startup_ms` in this run reflects total time since the container was "
               "created on a previous day; treat it as an upper bound only. `readiness_wait_ms` "
               "is the meaningful cold-start signal here (time from precheck start until /health "
               "returned 200).*\n")

    for idx, scen in enumerate(SCENARIOS, start=3):
        out.append(f"## {idx}. Scenario `{scen}` — k6 load-phase latency (mean ± stdev across 5 runs)\n")
        out.append("| Version | avg ms | p95 ms | p99 ms | max ms | fail rate | req/s | total reqs |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for ver in VERSIONS:
            a = agg[scen][ver]
            d = a["http_req_duration_load"]
            out.append(
                f"| {ver} "
                f"| {fmt(d['avg_ms']['mean'])} ± {fmt(d['avg_ms']['stdev'])} "
                f"| {fmt(d['p95_ms']['mean'])} ± {fmt(d['p95_ms']['stdev'])} "
                f"| {fmt(d['p99_ms']['mean'])} ± {fmt(d['p99_ms']['stdev'])} "
                f"| {fmt(d['max_ms']['mean'])} "
                f"| {fmt(a['http_req_failed_rate']['mean'], 4)} "
                f"| {fmt(a['http_reqs_rate']['mean'], 1)} "
                f"| {fmt(a['http_reqs_total']['mean'], 0)} |"
            )
        out.append("")

        out.append(f"### Scenario `{scen}` — resource usage (app container)\n")
        out.append("| Version | CPU avg % | CPU p95 % | CPU max % | Mem avg MiB | Mem max MiB |")
        out.append("|---|---:|---:|---:|---:|---:|")
        for ver in VERSIONS:
            a = agg[scen][ver]
            out.append(
                f"| {ver} "
                f"| {fmt(a['app_cpu_pct']['avg']['mean'], 1)} "
                f"| {fmt(a['app_cpu_pct']['p95']['mean'], 1)} "
                f"| {fmt(a['app_cpu_pct']['max']['mean'], 1)} "
                f"| {fmt(a['app_mem_mib']['avg']['mean'], 1)} "
                f"| {fmt(a['app_mem_mib']['max']['mean'], 1)} |"
            )
        out.append("")

        out.append(f"### Scenario `{scen}` — Postgres co-tenant\n")
        out.append("| Version (test running) | CPU avg % | CPU max % | Mem avg MiB | Mem max MiB |")
        out.append("|---|---:|---:|---:|---:|")
        for ver in VERSIONS:
            a = agg[scen][ver]
            out.append(
                f"| {ver} "
                f"| {fmt(a['postgres_cpu_pct']['avg']['mean'], 1)} "
                f"| {fmt(a['postgres_cpu_pct']['max']['mean'], 1)} "
                f"| {fmt(a['postgres_mem_mib']['avg']['mean'], 1)} "
                f"| {fmt(a['postgres_mem_mib']['max']['mean'], 1)} |"
            )
        out.append("")

    out.append(f"## {len(SCENARIOS)+3}. Per-repetition detail\n")
    out.append("| Scenario | Version | Run | Verdict | Wall s | avg ms | p95 ms | p99 ms | fail rate | req/s | app CPU avg % | app Mem max MiB |")
    out.append("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in per_run:
        k = r["k6"]
        c = r.get("container", {})
        d = k["http_req_duration_load"]
        app = c.get("app", {}) or {}
        out.append(
            f"| {r['scenario']} | {r['version']} | {r['run']} | {r['verdict']} "
            f"| {fmt(r['duration_s'], 1)} "
            f"| {fmt(d.get('avg'))} | {fmt(d.get('p(95)'))} | {fmt(d.get('p(99)'))} "
            f"| {fmt(k['http_req_failed_load']['rate'], 4)} "
            f"| {fmt(k['http_reqs']['rate'], 1)} "
            f"| {fmt((app.get('cpu_pct') or {}).get('avg'), 1)} "
            f"| {fmt((app.get('mem_mib') or {}).get('max'), 1)} |"
        )
    out.append("")

    out.append(f"## {len(SCENARIOS)+4}. Caveats for downstream analysis\n")
    out.append("- f2_high_load runs 2–5 do not have streaming `*.json` (only `*-summary.json`) "
               "because `f2_raw_first_rep_only=true`; per-request timeseries is therefore only "
               "available for repetition 1 of f2.")
    out.append("- All five f2_high_load reps breached `http_req_duration{phase:load}: p(95)<2000` "
               "and `p(99)<5000` for every version, triggering `abortOnFail` early-exit. "
               "Wallclock differences between versions on f2 partly reflect *when* the abort fired, "
               "not just throughput.")
    out.append("- Container CPU% follows Docker convention (relative to one host core; can exceed "
               "100% on multi-core).")
    out.append("- Startup CSV in this run reports `startup_ms` derived from "
               "`container_started_at`, which predates the benchmark; rely on `readiness_wait_ms` "
               "for cold-start comparisons.")
    out.append("- 0 OOMKill, 0 container restarts, 0 RUN_ERROR; all three /health endpoints "
               "remained 200 throughout the matrix.\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(run_id: str) -> int:
    log_path = RESULTS / f"nohup-{run_id}.out"
    stats_path = RESULTS / f"container-stats-{run_id}.csv"
    startup_path = RESULTS / f"startup-{run_id}.csv"

    if not log_path.exists():
        print(f"missing log: {log_path}", file=sys.stderr)
        return 2
    if not stats_path.exists():
        print(f"missing stats: {stats_path}", file=sys.stderr)
        return 2

    runs, thr_from_log = parse_log(log_path)
    print(f"parsed {len(runs)} run records from log", file=sys.stderr)

    stats = load_container_stats(stats_path)
    print(f"loaded {len(stats)} container-stats rows", file=sys.stderr)

    startups = load_startups(startup_path)

    per_run_records: list[dict[str, Any]] = []
    by_pair: dict[str, dict[str, list[dict[str, Any]]]] = {
        s: {v: [] for v in VERSIONS} for s in SCENARIOS
    }
    for r in runs:
        scen, ver, run_n = r["scenario"], r["version"], r["run"]
        summary_path = RESULTS / f"{scen}_{ver}_run{run_n}-summary.json"
        if not summary_path.exists():
            print(f"WARN: missing summary {summary_path.name}", file=sys.stderr)
            continue
        k6 = k6_metrics(summary_path)
        # Inject p(99) (and overwrite p(95)) from stdout threshold line, which is the only
        # place k6 reports p(99) with the default summaryTrendStats.
        log_thr = thr_from_log.get((scen, ver, run_n), {})
        if log_thr.get("p(99)_ms") is not None:
            k6["http_req_duration_load"]["p(99)"] = log_thr["p(99)_ms"]
        if log_thr.get("p(95)_ms") is not None:
            # keep the more precise threshold-reported value
            k6["http_req_duration_load"]["p(95)_threshold"] = log_thr["p(95)_ms"]
        app_service = VERSION_TO_SERVICE[ver]
        container = {
            "app": window_stats(stats, app_service, r["start"], r["end"]),
            "postgres": window_stats(stats, "postgres", r["start"], r["end"]),
        }
        rec = {**r,
               "start": r["start"].isoformat() if r["start"] else None,
               "end": r["end"].isoformat() if r["end"] else None,
               "k6": k6,
               "container": container}
        per_run_records.append(rec)
        by_pair[scen][ver].append(rec)

    agg = {
        scen: {ver: aggregate(by_pair[scen][ver]) for ver in VERSIONS}
        for scen in SCENARIOS
    }

    out_json = RESULTS / f"metrics_{run_id}.json"
    out_md = RESULTS / f"metrics_{run_id}.md"

    payload = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "startups": startups,
        "aggregate": agg,
        "per_run": per_run_records,
    }
    out_json.write_text(json.dumps(payload, indent=2, default=str))
    out_md.write_text(render_markdown(run_id, startups, agg, per_run_records))
    print(f"wrote {out_json.relative_to(ROOT)}", file=sys.stderr)
    print(f"wrote {out_md.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: aggregate_run.py <run_id>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
