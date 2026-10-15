#!/usr/bin/env python3
"""exp-lazy extraction: dumps every CloudWatch event of the 3 exp-lazy log groups (since RUN_START_MS) to
raw/logs_<fn>.jsonl.gz, then builds per-invocation (invocations.csv) and per-point (points.csv) tables.
Exits 0 only when every valid cold sample of samples.jsonl has its REPORT in CloudWatch."""
import csv
import gzip
import json
import os
import re
import subprocess
import sys
import time

WORK = os.environ["WORK"]
RUN_START_MS = int(os.environ["RUN_START_MS"])
FUNCS = ["exp-lazy-qj-v0", "exp-lazy-qj-v1", "exp-lazy-qj-v2"]
VAR = {"exp-lazy-qj-v0": "V0", "exp-lazy-qj-v1": "V1", "exp-lazy-qj-v2": "V2"}

REPORT_RE = re.compile(
    r"REPORT RequestId: (\S+)\s+Duration: ([\d.]+) ms\s+Billed Duration: (\d+) ms\s+Memory Size: (\d+) MB"
    r"\s+Max Memory Used: (\d+) MB(?:\s+Init Duration: ([\d.]+) ms)?")
START_RE = re.compile(r"^START RequestId: (\S+)")
INIT_START_RE = re.compile(r"INIT_START Runtime Version: (\S+)\s+Runtime Version ARN: (\S+)")


def fetch(fn):
    events, token = [], None
    end_ms = int(time.time() * 1000) + 60000
    while True:
        args = ["aws", "logs", "filter-log-events", "--log-group-name", f"/aws/lambda/{fn}",
                "--start-time", str(RUN_START_MS), "--end-time", str(end_ms), "--output", "json"]
        if token:
            args += ["--next-token", token]
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[:400])
        d = json.loads(p.stdout)
        events += d.get("events", [])
        token = d.get("nextToken")
        if not token:
            break
    events.sort(key=lambda e: (e["logStreamName"], e["timestamp"], e.get("eventId", "")))
    return events


def main():
    samples = [json.loads(l) for l in open(os.path.join(WORK, "samples.jsonl"))]
    need = {s["request_id"] for s in samples if s.get("request_id")}
    for attempt in range(10):
        all_events = {fn: fetch(fn) for fn in FUNCS}
        found = set()
        for evs in all_events.values():
            for e in evs:
                m = REPORT_RE.search(e["message"])
                if m:
                    found.add(m.group(1))
        missing = need - found
        print(f"extract attempt {attempt + 1}: events={sum(len(v) for v in all_events.values())} "
              f"reports_needed={len(need)} missing={len(missing)}", flush=True)
        if not missing:
            break
        time.sleep(30)
    os.makedirs(os.path.join(WORK, "raw"), exist_ok=True)
    for fn, evs in all_events.items():
        with gzip.open(os.path.join(WORK, "raw", f"logs_{fn}.jsonl.gz"), "wt") as f:
            for e in evs:
                f.write(json.dumps(e) + "\n")

    inv_rows, pt_rows = [], []
    access_denied = 0
    for fn, evs in all_events.items():
        streams = {}
        for e in evs:
            streams.setdefault(e["logStreamName"], []).append(e)
        for stream, sevs in streams.items():
            runtime_version = runtime_arn = None
            init_start_ts = None
            starts = {}
            inv_index = 0
            for e in sevs:
                msg = e["message"]
                if "AccessDenied" in msg:
                    access_denied += 1
                mi = INIT_START_RE.search(msg)
                if mi:
                    runtime_version, runtime_arn = mi.group(1), mi.group(2)
                    init_start_ts = e["timestamp"]
                    continue
                ms = START_RE.search(msg)
                if ms:
                    starts[ms.group(1)] = e["timestamp"]
                    continue
                m = REPORT_RE.search(msg)
                if m:
                    inv_index += 1
                    rid = m.group(1)
                    init_ms = float(m.group(6)) if m.group(6) else None
                    row = {"variant": VAR[fn], "function": fn, "log_stream": stream, "request_id": rid,
                           "inv_in_env": inv_index, "duration_ms": float(m.group(2)),
                           "billed_ms": int(m.group(3)), "max_mem_mb": int(m.group(5)), "init_ms": init_ms,
                           "runtime_version": runtime_version, "runtime_arn": runtime_arn,
                           "init_start_ts": init_start_ts, "start_ts": starts.get(rid), "report_ts": e["timestamp"]}
                    if init_ms is not None and init_start_ts is not None and starts.get(rid) is not None:
                        row["gap_init_end_to_start_ms"] = round(starts[rid] - (init_start_ts + init_ms), 1)
                    inv_rows.append(row)
                    continue
                if "EXP_LAZY " in msg:
                    try:
                        d = json.loads(msg[msg.index("EXP_LAZY ") + 9:].strip())
                    except ValueError:
                        continue
                    d["variant"] = VAR[fn]
                    d["log_stream"] = stream
                    d["cw_ts"] = e["timestamp"]
                    pt_rows.append(d)

    with open(os.path.join(WORK, "invocations.csv"), "w", newline="") as f:
        cols = ["variant", "function", "log_stream", "request_id", "inv_in_env", "init_ms", "duration_ms",
                "billed_ms", "max_mem_mb", "runtime_version", "runtime_arn", "init_start_ts", "start_ts",
                "report_ts", "gap_init_end_to_start_ms"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(inv_rows)
    pcols = ["variant", "log_stream", "pt", "inv", "rid", "tn", "wall", "cls", "clsTot", "jitMs", "gcMs", "gcN",
             "pcpuNs", "tcpuNs", "thr", "statUser", "statSys", "statIdle", "statSteal", "statTotal", "x",
             "jvmStartMs", "uptimeMs", "cpus", "maxHeap", "javaVersion", "vm", "memEnv", "execEnv", "prep", "jto",
             "args", "cw_ts"]
    with open(os.path.join(WORK, "points.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pcols, extrasaction="ignore")
        w.writeheader()
        w.writerows(pt_rows)
    with open(os.path.join(WORK, "extract_summary.json"), "w") as f:
        json.dump({"reports_needed": len(need), "missing": sorted(missing), "invocations": len(inv_rows),
                   "points": len(pt_rows), "access_denied_lines": access_denied,
                   "sdk_fail_points": sum(1 for p in pt_rows if p.get("pt") == "sdk_fail"),
                   "prep_fail_points": sum(1 for p in pt_rows if p.get("pt") == "prep_fail")}, f, indent=1)
    print(open(os.path.join(WORK, "extract_summary.json")).read(), flush=True)
    sys.exit(0 if not missing else 2)


if __name__ == "__main__":
    main()
