#!/usr/bin/env python3
"""exp-lazy driver: forced cold starts, interleaved and shuffled in blocks (V0/V1/V2), concurrency 1.

For each sample: change COLD_TOKEN -> wait LastUpdateStatus=Successful -> cold invoke (REPORT via --log-type Tail)
-> confirm "Init Duration" (otherwise retry with a new token) -> 1 warm invoke in the same environment.
Writes samples.jsonl (1 line per invocation) and syncs to S3 after each sample. No human decisions.
"""
import base64
import json
import os
import random
import re
import subprocess
import sys
import time

WORK = os.environ["WORK"]
BUCKET = os.environ["BUCKET"]
RUN_ID = os.environ["RUN_ID"]
BLOCKS = int(os.environ["BLOCKS"])
SEED = int(os.environ.get("SEED", "20260929"))
MAX_ATTEMPTS = 3
PAUSE_S = 5
WARM_GAP_S = 2

FUNCS = {
    "V0": "exp-lazy-qj-v0",
    "V1": "exp-lazy-qj-v1",
    "V2": "exp-lazy-qj-v2",
}
BASE_ENV = {
    "PROCESSED_ORDERS_TABLE": "exp-lazy-processed-orders",
    "STOCK_RESERVATIONS_TABLE": "exp-lazy-stock-reservations",
}
EXTRA_ENV = {"V0": {}, "V1": {}, "V2": {"EXP_LAZY_PREP": "1"}}

REPORT_RE = re.compile(
    r"REPORT RequestId: (\S+)\s+Duration: ([\d.]+) ms\s+Billed Duration: (\d+) ms\s+Memory Size: (\d+) MB"
    r"\s+Max Memory Used: (\d+) MB(?:\s+Init Duration: ([\d.]+) ms)?")
INIT_START_RE = re.compile(r"INIT_START Runtime Version: (\S+)\s+Runtime Version ARN: (\S+)")


def log(msg):
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {msg}"
    print(line, flush=True)


def status(msg):
    with open(os.path.join(WORK, "STATUS"), "w") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} RUN_ID={RUN_ID} {msg}\n")
    s3cp(os.path.join(WORK, "STATUS"), "STATUS")
    aws(["s3", "cp", "--only-show-errors", os.path.join(WORK, "STATUS"), f"s3://{BUCKET}/STATUS"], check=False)


def aws(args, env_extra=None, check=True):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(["aws"] + args, capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        raise RuntimeError(f"aws {' '.join(args[:3])} failed rc={p.returncode}: {p.stderr.strip()[:500]}")
    return p


def s3cp(local, key):
    aws(["s3", "cp", "--only-show-errors", local, f"s3://{BUCKET}/{RUN_ID}/{key}"], check=False)


def fn_event(payload):
    body = json.dumps(payload, separators=(",", ":"))
    return {
        "version": "2.0", "routeKey": "$default", "rawPath": "/", "rawQueryString": "",
        "headers": {"content-type": "application/json", "user-agent": "exp-lazy-driver"},
        "requestContext": {"accountId": "anonymous", "http": {"method": "POST", "path": "/", "protocol": "HTTP/1.1",
                                                                "sourceIp": "127.0.0.1", "userAgent": "exp-lazy-driver"},
                           "requestId": "exp-lazy", "routeKey": "$default", "stage": "$default"},
        "body": body, "isBase64Encoded": False,
    }


def set_token(variant, token):
    env = dict(BASE_ENV)
    env.update(EXTRA_ENV[variant])
    env["COLD_TOKEN"] = token
    aws(["lambda", "update-function-configuration", "--function-name", FUNCS[variant],
         "--environment", json.dumps({"Variables": env}), "--output", "json"])
    t0 = time.time()
    while True:
        cfg = json.loads(aws(["lambda", "get-function-configuration", "--function-name", FUNCS[variant],
                              "--output", "json"]).stdout)
        st = cfg.get("LastUpdateStatus")
        if st == "Successful" and cfg.get("State") == "Active" and \
                cfg.get("Environment", {}).get("Variables", {}).get("COLD_TOKEN") == token:
            return cfg, time.time() - t0
        if st == "Failed":
            raise RuntimeError(f"update failed {variant}: {cfg.get('LastUpdateStatusReason')}")
        if time.time() - t0 > 180:
            raise RuntimeError(f"update timeout {variant}")
        time.sleep(1)


def invoke(variant, event_path, out_path):
    t0 = time.time()
    p = aws(["lambda", "invoke", "--function-name", FUNCS[variant], "--log-type", "Tail",
             "--cli-binary-format", "raw-in-base64-out", "--payload", f"fileb://{event_path}",
             "--cli-read-timeout", "120", "--output", "json", out_path],
            env_extra={"AWS_MAX_ATTEMPTS": "1", "AWS_RETRY_MODE": "standard"}, check=False)
    t1 = time.time()
    rec = {"client_start": t0, "client_end": t1, "client_ms": round((t1 - t0) * 1000, 1), "cli_rc": p.returncode}
    if p.returncode != 0:
        rec["cli_err"] = p.stderr.strip()[:500]
        return rec
    meta = json.loads(p.stdout)
    rec["status_code"] = meta.get("StatusCode")
    rec["function_error"] = meta.get("FunctionError")
    tail = base64.b64decode(meta.get("LogResult", "")).decode("utf-8", "replace")
    m = REPORT_RE.search(tail)
    if m:
        rec.update({"request_id": m.group(1), "duration_ms": float(m.group(2)), "billed_ms": int(m.group(3)),
                    "memory_mb": int(m.group(4)), "max_mem_mb": int(m.group(5)),
                    "init_ms": float(m.group(6)) if m.group(6) else None})
    mi = INIT_START_RE.search(tail)
    if mi:
        rec["runtime_version_tail"] = mi.group(1)
        rec["runtime_arn_tail"] = mi.group(2)
    rec["access_denied_in_tail"] = "AccessDenied" in tail
    try:
        with open(out_path) as f:
            rec["response"] = f.read()[:400]
    except OSError:
        pass
    return rec


def main():
    payloads = json.load(open(os.path.join(WORK, "l1_payloads.json")))
    rng = random.Random(SEED)
    schedule = []
    for b in range(BLOCKS):
        order = ["V0", "V1", "V2"]
        rng.shuffle(order)
        for pos, v in enumerate(order):
            schedule.append((b, pos, v))
    with open(os.path.join(WORK, "schedule.json"), "w") as f:
        json.dump({"seed": SEED, "blocks": BLOCKS, "schedule": schedule}, f)
    s3cp(os.path.join(WORK, "schedule.json"), "schedule.json")

    out = open(os.path.join(WORK, "samples.jsonl"), "a")
    total = len(schedule)
    for i, (b, pos, v) in enumerate(schedule):
        payload_idx = b % len(payloads)
        ev_path = os.path.join(WORK, f"event_{payload_idx}.json")
        if not os.path.exists(ev_path):
            with open(ev_path, "w") as f:
                json.dump(fn_event(payloads[payload_idx]), f, separators=(",", ":"))
        status(f"RUNNING sample {i + 1}/{total} block={b} variant={v}")
        cold_ok = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            token = f"{RUN_ID}-b{b}-{v}-a{attempt}"
            for k in range(4):
                try:
                    cfg, wait_s = set_token(v, token)
                    break
                except RuntimeError as e:
                    log(f"set_token retry {k + 1}: {e}")
                    if k == 3:
                        raise
                    time.sleep(10)
            rec = invoke(v, ev_path, os.path.join(WORK, "resp.json"))
            rec.update({"run_id": RUN_ID, "idx": i, "block": b, "pos": pos, "variant": v, "function": FUNCS[v],
                        "attempt": attempt, "cold_token": token, "payload_idx": payload_idx, "kind": "cold",
                        "update_wait_s": round(wait_s, 2), "code_sha256": cfg.get("CodeSha256"),
                        "handler": cfg.get("Handler"), "revision": cfg.get("RevisionId"),
                        "runtime_arn_cfg": (cfg.get("RuntimeVersionConfig") or {}).get("RuntimeVersionArn")})
            rec["valid_cold"] = bool(rec.get("init_ms")) and rec.get("status_code") == 200 \
                and not rec.get("function_error")
            out.write(json.dumps(rec) + "\n")
            out.flush()
            log(f"{i + 1}/{total} b={b} {v} a={attempt} init={rec.get('init_ms')} dur={rec.get('duration_ms')} "
                f"err={rec.get('function_error')} valid={rec['valid_cold']}")
            if rec["valid_cold"]:
                cold_ok = True
                time.sleep(WARM_GAP_S)
                w = invoke(v, ev_path, os.path.join(WORK, "resp.json"))
                w.update({"run_id": RUN_ID, "idx": i, "block": b, "pos": pos, "variant": v, "function": FUNCS[v],
                          "attempt": attempt, "cold_token": token, "payload_idx": payload_idx, "kind": "warm"})
                out.write(json.dumps(w) + "\n")
                out.flush()
                break
            time.sleep(PAUSE_S)
        if not cold_ok:
            log(f"sample {i + 1} NOT cold after {MAX_ATTEMPTS} attempts (kept as invalid)")
        s3cp(os.path.join(WORK, "samples.jsonl"), "raw/samples.jsonl")
        time.sleep(PAUSE_S)
    out.close()
    status(f"SAMPLING_DONE {total} samples")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"driver error: {e!r}")
        sys.exit(1)
