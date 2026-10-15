#!/usr/bin/env python3
"""exp-lazy-sb automatic analysis (descriptive only; no confirmatory test). Python stdlib only.
Inputs (WORK): samples.jsonl, invocations.csv, points.csv, l1_duration_postinit.csv.
Outputs: summary.json, intervals.csv, phases.csv, RELATORIO_PRELIMINAR.md."""
import csv
import json
import os
import random
import statistics as st
from collections import defaultdict

WORK = os.environ["WORK"]
RUN_ID = os.environ.get("RUN_ID", "?")
VARS = ["V0", "V1", "V2"]


def desc(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {"n": 0}
    q = st.quantiles(xs, n=4, method="inclusive") if len(xs) > 1 else [xs[0]] * 3
    return {"n": len(xs), "median": round(st.median(xs), 2), "mean": round(st.fmean(xs), 2),
            "q1": round(q[0], 2), "q3": round(q[2], 2), "iqr": round(q[2] - q[0], 2),
            "min": round(xs[0], 2), "max": round(xs[-1], 2),
            "sd": round(st.stdev(xs), 2) if len(xs) > 1 else None}


def boot_median_diff(a, b, reps=5000, seed=1):
    """95% percentile bootstrap interval for median(a) - median(b). Descriptive only."""
    a, b = [x for x in a if x is not None], [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2:
        return None
    rng = random.Random(seed)
    ds = sorted(st.median(rng.choices(a, k=len(a))) - st.median(rng.choices(b, k=len(b))) for _ in range(reps))
    return [round(ds[int(0.025 * reps)], 1), round(ds[int(0.975 * reps) - 1], 1)]


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    samples = [json.loads(l) for l in open(os.path.join(WORK, "samples.jsonl"))]
    inv = {r["request_id"]: r for r in csv.DictReader(open(os.path.join(WORK, "invocations.csv")))}
    points = list(csv.DictReader(open(os.path.join(WORK, "points.csv"))))

    cold = [s for s in samples if s["kind"] == "cold" and s.get("valid_cold")]
    invalid = [s for s in samples if s["kind"] == "cold" and not s.get("valid_cold")]
    warm = {(s["variant"], s["idx"]): s for s in samples if s["kind"] == "warm"}
    rows = []
    for s in cold:
        cw = inv.get(s.get("request_id"), {})
        w = warm.get((s["variant"], s["idx"]), {})
        init = fnum(cw.get("init_ms")) if cw else s.get("init_ms")
        dur = fnum(cw.get("duration_ms")) if cw else s.get("duration_ms")
        rows.append({
            "variant": s["variant"], "block": s["block"], "pos": s["pos"], "idx": s["idx"],
            "payload_idx": s["payload_idx"], "request_id": s.get("request_id"), "log_stream": cw.get("log_stream"),
            "init_ms": init, "duration_ms": dur, "billed_ms": fnum(cw.get("billed_ms")) or s.get("billed_ms"),
            "init_plus_duration_ms": (init + dur) if init is not None and dur is not None else None,
            "max_mem_mb": fnum(cw.get("max_mem_mb")) or s.get("max_mem_mb"),
            "runtime_version": cw.get("runtime_version"), "runtime_arn": cw.get("runtime_arn"),
            "gap_init_end_to_start_ms": fnum(cw.get("gap_init_end_to_start_ms")),
            "start_ts": fnum(cw.get("start_ts")),
            "warm_duration_ms": w.get("duration_ms"), "warm_request_id": w.get("request_id"),
            "client_ms": s.get("client_ms"), "code_sha256": s.get("code_sha256"), "handler": s.get("handler"),
            "update_wait_s": s.get("update_wait_s"), "in_cloudwatch": bool(cw),
        })
    with open(os.path.join(WORK, "samples_final.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["variant"])
        w.writeheader()
        w.writerows(rows)

    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)
    metrics = ["init_ms", "duration_ms", "billed_ms", "init_plus_duration_ms", "warm_duration_ms", "max_mem_mb",
               "gap_init_end_to_start_ms", "client_ms"]
    summary = {"run_id": RUN_ID, "n_valid_cold": {v: len(by[v]) for v in VARS},
               "n_invalid_cold_attempts": {v: sum(1 for s in invalid if s["variant"] == v) for v in VARS},
               "stats": {v: {m: desc([r[m] for r in by[v]]) for m in metrics} for v in VARS},
               "runtime_versions": {v: sorted({str(r["runtime_version"]) for r in by[v]}) for v in VARS},
               "code_sha256": {v: sorted({str(r["code_sha256"]) for r in by[v]}) for v in VARS},
               "handlers": {v: sorted({str(r["handler"]) for r in by[v]}) for v in VARS}}

    # ---- L1 official (read from the canonical CSV, never typed in) ----
    l1 = [r for r in csv.DictReader(open(os.path.join(WORK, "l1_duration_postinit.csv")))
          if r["runtime"] == "springboot" and r["excluded_outlier"] == "False"]
    l1_init = [float(r["init_duration_ms"]) for r in l1]
    l1_dur = [float(r["duration_ms"]) for r in l1]
    summary["l1_official_sb"] = {"init_ms": desc(l1_init), "duration_ms": desc(l1_dur),
                                 "init_plus_duration_ms": desc([a + b for a, b in zip(l1_init, l1_dur)])}

    def cmp(a, b, metric):
        xa = [r[metric] for r in by[a]] if a in by else []
        xb = [r[metric] for r in by[b]] if b in by else []
        if not xa or not xb:
            return None
        ma, mb = st.median([x for x in xa if x is not None]), st.median([x for x in xb if x is not None])
        return {"median_a": round(ma, 1), "median_b": round(mb, 1), "diff": round(ma - mb, 1),
                "diff_pct": round(100 * (ma - mb) / mb, 1), "boot95": boot_median_diff(xa, xb)}

    summary["cmp"] = {
        "V1_vs_V0": {m: cmp("V1", "V0", m) for m in ["init_ms", "duration_ms", "init_plus_duration_ms",
                                                     "warm_duration_ms"]},
        "V2_vs_V1": {m: cmp("V2", "V1", m) for m in ["init_ms", "duration_ms", "init_plus_duration_ms",
                                                     "warm_duration_ms"]},
    }
    v0i = [r["init_ms"] for r in by["V0"]]
    v0d = [r["duration_ms"] for r in by["V0"]]
    ctrl = {}
    if v0i and v0d:
        for name, xs, ref in [("init_ms", v0i, l1_init), ("duration_ms", v0d, l1_dur)]:
            m, mr = st.median(xs), st.median(ref)
            ctrl[name] = {"v0_median": round(m, 1), "l1_median": round(mr, 1), "diff_pct": round(100 * (m - mr) / mr, 1),
                          "v0_median_inside_l1_range": min(ref) <= m <= max(ref),
                          "boot95_v0_minus_l1": boot_median_diff(xs, ref)}
        ctrl["rule"] = ("controle OK se |diff| das medianas de Duration <= 10% (regra pré-definida na A3, descritiva); "
                        "Init só reportado")
        ctrl["ok"] = abs(ctrl["duration_ms"]["diff_pct"]) <= 10
    v1v0 = summary["cmp"]["V1_vs_V0"].get("duration_ms")
    summary["instrumentation_flag"] = {
        "rule": "sinalizar se |diff| das medianas de Duration V1 x V0 > 5% (regra pré-definida na A3)",
        "diff_pct": v1v0["diff_pct"] if v1v0 else None,
        "flag": (abs(v1v0["diff_pct"]) > 5) if v1v0 else None}
    summary["control_V0_vs_L1"] = ctrl

    # ---- points: intervals between consecutive points (V1/V2) ----
    pts_by_stream = defaultdict(list)
    spring_pts = defaultdict(list)
    meta_by_stream = {}
    for p in points:
        if p["pt"] == "meta":
            meta_by_stream[p["log_stream"]] = p
            continue
        if p["pt"] in ("scf_received", "spring_started"):
            spring_pts[p["log_stream"]].append(p)
            continue
        if p["pt"] == "tmp" or not p.get("tn"):
            continue
        pts_by_stream[p["log_stream"]].append(p)
    valid_streams = {r["log_stream"]: r for r in rows if r["variant"] in ("V1", "V2") and r["log_stream"]}
    interval_vals = defaultdict(lambda: defaultdict(list))  # (variant, phase) -> key -> list of dicts
    phase_vals = defaultdict(lambda: defaultdict(list))
    tmp_lists = defaultdict(list)
    for p in points:
        if p["pt"] == "tmp" and p["log_stream"] in valid_streams:
            tmp_lists[p["variant"]].append(p.get("x", ""))
    for stream, r in valid_streams.items():
        ps = pts_by_stream.get(stream, [])
        v = r["variant"]
        for phase, sel in (("init", lambda p: p["inv"] == "0"), ("inv1", lambda p: p["inv"] == "1"),
                           ("inv2", lambda p: p["inv"] == "2")):
            seq = [p for p in ps if sel(p)]
            seq.sort(key=lambda p: int(p["tn"]))
            occ = defaultdict(int)
            labels = []
            for p in seq:
                occ[p["pt"]] += 1
                labels.append(p["pt"] if occ[p["pt"]] == 1 else f"{p['pt']}#{occ[p['pt']]}")
            for a, b, la, lb in zip(seq, seq[1:], labels, labels[1:]):
                dw = (int(b["tn"]) - int(a["tn"])) / 1e6
                d = {"ms": dw, "cls": int(b["cls"]) - int(a["cls"]), "jit": int(b["jitMs"]) - int(a["jitMs"]),
                     "gc": int(b["gcMs"]) - int(a["gcMs"]),
                     "tcpu_ms": (int(b["tcpuNs"]) - int(a["tcpuNs"])) / 1e6,
                     "pcpu_ms": (int(b["pcpuNs"]) - int(a["pcpuNs"])) / 1e6}
                interval_vals[(v, phase)][f"{la} -> {lb}"].append(d)
            if len(seq) >= 2:
                a, b = seq[0], seq[-1]
                dw = (int(b["tn"]) - int(a["tn"])) / 1e6
                dt = int(b["statTotal"]) - int(a["statTotal"])
                ph = {"wall_ms": dw, "cls": int(b["cls"]) - int(a["cls"]), "jit_ms": int(b["jitMs"]) - int(a["jitMs"]),
                      "gc_ms": int(b["gcMs"]) - int(a["gcMs"]),
                      "thread_cpu_ms": (int(b["tcpuNs"]) - int(a["tcpuNs"])) / 1e6,
                      "process_cpu_ms": (int(b["pcpuNs"]) - int(a["pcpuNs"])) / 1e6,
                      "busy_frac_procstat": ((int(b["statUser"]) + int(b["statSys"]) - int(a["statUser"])
                                              - int(a["statSys"])) / dt) if dt > 0 else None,
                      "steal_frac_procstat": ((int(b["statSteal"]) - int(a["statSteal"])) / dt) if dt > 0 else None,
                      "jiffies_total": dt}
                ph["process_cpu_per_wall"] = ph["process_cpu_ms"] / dw if dw > 0 else None
                ph["thread_cpu_per_wall"] = ph["thread_cpu_ms"] / dw if dw > 0 else None
                ph["from"], ph["to"] = labels[0], labels[-1]
                for k, val in ph.items():
                    phase_vals[(v, phase)][k].append(val)
                if phase == "inv1" and r.get("start_ts"):
                    phase_vals[(v, phase)]["start_to_w_in_ms"].append(int(a["wall"]) - r["start_ts"])
                    phase_vals[(v, phase)]["w_out_to_end_ms"].append(
                        r["start_ts"] + r["duration_ms"] - int(b["wall"]))
                    phase_vals[(v, phase)]["w_in_to_w_out_share_of_duration"].append(dw / r["duration_ms"])
        m = meta_by_stream.get(stream)
        if m:
            phase_vals[(v, "meta")]["jvm_uptime_at_clinit_ms"].append(float(m["uptimeMs"]))
            phase_vals[(v, "meta")]["cpus"].append(float(m["cpus"]))
            summary.setdefault("jvm_args", {}).setdefault(v, set()).add(m["args"])
            summary.setdefault("jto", {}).setdefault(v, set()).add(m["jto"])
            if r.get("start_ts") is not None:
                cw_init_start = fnum(inv.get(r["request_id"], {}).get("init_start_ts"))
                if cw_init_start:
                    phase_vals[(v, "meta")]["init_start_to_jvm_start_ms"].append(float(m["jvmStartMs"]) - cw_init_start)
    for k in ("jvm_args", "jto"):
        if k in summary:
            summary[k] = {v: sorted(x) for v, x in summary[k].items()}
    summary["tmp_listing_inv1"] = {v: sorted(set(x)) for v, x in tmp_lists.items()}

    with open(os.path.join(WORK, "intervals.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "phase", "interval", "n", "median_ms", "q1_ms", "q3_ms", "median_cls", "median_jit_ms",
                    "median_gc_ms", "median_thread_cpu_ms", "median_process_cpu_ms"])
        for (v, phase), d in sorted(interval_vals.items()):
            for key, lst in d.items():
                ms = desc([x["ms"] for x in lst])
                w.writerow([v, phase, key, ms["n"], ms["median"], ms["q1"], ms["q3"],
                            st.median([x["cls"] for x in lst]), st.median([x["jit"] for x in lst]),
                            st.median([x["gc"] for x in lst]), round(st.median([x["tcpu_ms"] for x in lst]), 1),
                            round(st.median([x["pcpu_ms"] for x in lst]), 1)])
    phases_out = {}
    with open(os.path.join(WORK, "phases.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "phase", "metric", "n", "median", "q1", "q3", "min", "max"])
        for (v, phase), d in sorted(phase_vals.items()):
            for k, lst in d.items():
                if k in ("from", "to"):
                    phases_out.setdefault(f"{v}/{phase}", {})[k] = sorted(set(lst))
                    continue
                ds = desc([x for x in lst if x is not None])
                phases_out.setdefault(f"{v}/{phase}", {})[k] = ds
                w.writerow([v, phase, k, ds.get("n"), ds.get("median"), ds.get("q1"), ds.get("q3"), ds.get("min"),
                            ds.get("max")])
    summary["phases"] = phases_out

    # ---- Spring log markers (wall ms): START -> "Received:" (inside generateMessage) -> h_in ----
    stream_rows = {r["log_stream"]: r for r in rows if r["log_stream"]}
    scf = defaultdict(lambda: defaultdict(list))
    for stream, r in stream_rows.items():
        v = r["variant"]
        sp = spring_pts.get(stream, [])
        rec = [p for p in sp if p["pt"] == "scf_received" and p["inv"] == "1" and p.get("wall")]
        st_ = [p for p in sp if p["pt"] == "spring_started"]
        if st_:
            x = dict(kv.split("=") for kv in st_[0]["x"].split())
            scf[v]["spring_started_s"].append(float(x["started_s"]))
            scf[v]["spring_process_running_s"].append(float(x["process_s"]))
        if rec and r.get("start_ts"):
            rw = float(rec[0]["wall"])
            scf[v]["start_to_received_ms"].append(rw - r["start_ts"])
            ps = {p["pt"]: p for p in pts_by_stream.get(stream, []) if p["inv"] == "1"}
            if "w_in" in ps and "h_in" in ps:
                scf[v]["w_in_to_received_ms"].append(rw - int(ps["w_in"]["wall"]))
                scf[v]["received_to_h_in_ms"].append(int(ps["h_in"]["wall"]) - rw)
    summary["spring_markers"] = {v: {k: desc(x) for k, x in d.items()} for v, d in scf.items()}

    # ---- same operations in both phases: V1 in the 1st invocation x V2 in init ----
    same_ops = [("svc_calc_done -> sdk_before_exec", "prep_json_in_done -> sdk_before_exec", "repositório -> 1º beforeExecution"),
                ("sdk_before_exec -> sdk_before_tx", "sdk_before_exec -> sdk_before_tx", "serialização, credenciais, assinatura"),
                ("sdk_before_tx -> sdk_after_tx", "sdk_before_tx -> sdk_after_tx", "1ª transmissão HTTP"),
                ("sdk_after_tx -> sdk_after_exec", "sdk_after_tx -> sdk_after_exec", "pós-transmissão"),
                ("h_in -> h_mapped", "prep_beans_done -> prep_json_in_done", "Jackson (mapper)")]
    so = []
    for k1, k2, label in same_ops:
        a = interval_vals.get(("V1", "inv1"), {}).get(k1, [])
        b = interval_vals.get(("V2", "init"), {}).get(k2, [])
        if a and b:
            ma, mb = st.median([x["ms"] for x in a]), st.median([x["ms"] for x in b])
            so.append({"op": label, "v1_invoke_key": k1, "v2_init_key": k2, "v1_invoke_ms": round(ma, 1),
                       "v2_init_ms": round(mb, 1), "ratio": round(ma / mb, 2) if mb else None,
                       "v1_thread_cpu_ms": round(st.median([x["tcpu_ms"] for x in a]), 1),
                       "v2_thread_cpu_ms": round(st.median([x["tcpu_ms"] for x in b]), 1),
                       "n": [len(a), len(b)]})
    summary["same_ops_v1_invoke_vs_v2_init"] = so
    with open(os.path.join(WORK, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    write_report(summary, interval_vals)


def fmt(d, k="median"):
    return "—" if not d or d.get("n", 0) == 0 else f"{d[k]:.1f}"


def write_report(s, interval_vals):
    L = []
    L.append(f"# Relatório preliminar automático — exp-lazy-sb, Spring Boot (EXPLORATÓRIO, fora do desenho oficial)\n")
    L.append(f"RUN_ID `{s['run_id']}`. Gerado pelo driver na EC2. Apenas descritivo. Nenhum intervalo aqui é "
             "confirmatório. Fonte de cada número: `samples_final.csv`, `invocations.csv`, `points.csv`, "
             "`intervals.csv`, `phases.csv`, `summary.json`; L1 oficial: `l1_duration_postinit.csv`.\n")
    L.append("## 1. Amostras\n")
    L.append(f"- Frias válidas: {s['n_valid_cold']}; tentativas não frias/erro: {s['n_invalid_cold_attempts']}")
    L.append(f"- Versões de runtime (INIT_START): {s['runtime_versions']}")
    L.append(f"- CodeSha256: {s['code_sha256']}")
    L.append(f"- Handler: {s['handlers']}\n")
    L.append("## 2. Por variante (ms; mediana [Q1–Q3] min–max, n)\n")
    L.append("| Variante | Init | Duration | Init + Duration | Duration 2ª chamada (quente) | Gap fim-init→START |")
    L.append("|---|---|---|---|---|---|")

    def cell(d):
        return "—" if not d or d.get("n", 0) == 0 else \
            f"{d['median']:.1f} [{d['q1']:.1f}–{d['q3']:.1f}] {d['min']:.1f}–{d['max']:.1f}, n={d['n']}"
    for v in VARS:
        x = s["stats"][v]
        L.append(f"| {v} | {cell(x['init_ms'])} | {cell(x['duration_ms'])} | {cell(x['init_plus_duration_ms'])} | "
                 f"{cell(x['warm_duration_ms'])} | {cell(x['gap_init_end_to_start_ms'])} |")
    l1 = s["l1_official_sb"]
    L.append(f"| L1 oficial SB | {cell(l1['init_ms'])} | {cell(l1['duration_ms'])} | "
             f"{cell(l1['init_plus_duration_ms'])} | — | — |\n")
    L.append("## 3. Controle (V0 × L1 oficial)\n")
    L.append("```\n" + json.dumps(s["control_V0_vs_L1"], indent=1, ensure_ascii=False) + "\n```\n")
    if s["control_V0_vs_L1"] and not s["control_V0_vs_L1"].get("ok"):
        L.append("**ATENÇÃO: pela regra pré-definida o controle DIVERGIU. Não interpretar V1/V2 sem análise.**\n")
    L.append("Instrumentação (V1 x V0): " + json.dumps(s.get("instrumentation_flag"), ensure_ascii=False) + "\n")
    L.append("## 3b. Marcas do Spring (ms, log)\n")
    L.append("```\n" + json.dumps(s.get("spring_markers"), indent=1) + "\n```\n")
    L.append("## 3c. Mesmas operações: V1 na 1ª chamada x V2 no init\n")
    L.append("```\n" + json.dumps(s.get("same_ops_v1_invoke_vs_v2_init"), indent=1, ensure_ascii=False) + "\n```\n")
    L.append("## 4. Comparações (diferença de medianas, IC bootstrap 95% descritivo)\n")
    L.append("```\n" + json.dumps(s["cmp"], indent=1) + "\n```\n")
    L.append("## 5. Fases (V1/V2): CPU, classes, JIT\n")
    L.append("```\n" + json.dumps(s["phases"], indent=1, default=str)[:20000] + "\n```\n")
    L.append("## 6. Intervalos da 1ª chamada (medianas, ms) — ver `intervals.csv`\n")
    for v in ("V1", "V2"):
        d = interval_vals.get((v, "inv1"), {})
        L.append(f"### {v} inv1\n")
        L.append("| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |")
        L.append("|---|---|---|---|---|---|")
        for key, lst in sorted(d.items(), key=lambda kv: -st.median([x["ms"] for x in kv[1]])):
            L.append(f"| {key} | {len(lst)} | {st.median([x['ms'] for x in lst]):.1f} | "
                     f"{st.median([x['cls'] for x in lst]):.0f} | {st.median([x['jit'] for x in lst]):.0f} | "
                     f"{st.median([x['tcpu_ms'] for x in lst]):.1f} |")
        L.append("")
    L.append(f"## 7. JVM\n\n- JAVA_TOOL_OPTIONS: {s.get('jto')}\n- args: {s.get('jvm_args')}\n"
             f"- /tmp na 1ª chamada: {s.get('tmp_listing_inv1')}\n")
    with open(os.path.join(WORK, "RELATORIO_PRELIMINAR.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
