"""C1 (TieredStopAtLevel=1, default Lambda java21) vs C2 (sem teto): latência k6 por invocação, CPU e níveis do JIT."""
import collections, csv, glob, os, re, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get("RESULTS_DIR", os.path.join(HERE, "results"))
WARM = int(os.environ.get("WARM", 5500))   # janela principal: seq > WARM
BIN = 500                                  # curva de aquecimento


def cpustat(path):
    try:
        return {k: int(v) for k, v in (l.split() for l in open(path))}
    except FileNotFoundError:
        return {}


def pct(xs, p):
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def levels(path):
    c = collections.Counter()
    for l in open(path):
        p = l.split()
        if len(p) >= 4 and p[0].isdigit() and p[1].isdigit():
            c[int(p[1])] += 1
    return c


def ci(path):
    d = {}
    for l in open(path):
        k, _, v = l.strip().partition("=")
        d[k] = v
    return d


rows, curves = [], {}
for f in sorted(glob.glob(os.path.join(RES, "*.k6.csv"))):
    tag = os.path.basename(f)[:-7]
    m = re.match(r"(?:r(\d+)|smoke)-(sb|qj)-(c1|c2)$", tag)
    meta = open(f"{RES}/{tag}.meta").read()
    if not m or (m[1] and "load_end" not in meta):
        continue
    reqs, fail = [], 0
    with open(f) as fh:
        for r in csv.DictReader(fh):
            if r["metric_name"] == "http_req_duration":
                reqs.append(float(r["metric_value"]))  # 1 VU: ordem do arquivo = ordem de invocação
            elif r["metric_name"] == "checks" and float(r["metric_value"]) == 0:
                fail += 1
    warm = sorted(reqs[WARM:])
    b, a = cpustat(f"{RES}/{tag}.cpustat.before"), cpustat(f"{RES}/{tag}.cpustat.after")
    lv = levels(f"{RES}/{tag}.codelist")
    c = ci(f"{RES}/{tag}.ci")
    flag = re.search(r"TieredStopAtLevel\s*=\s*(\d+)", open(f"{RES}/{tag}.flags").read())
    curves[tag] = [st.median(reqs[i:i + BIN]) for i in range(0, len(reqs) - BIN + 1, BIN)]
    rows.append(dict(
        tag=tag, run=int(m[1] or 0), ver=m[2], cond=m[3], stop_level=int(flag[1]) if flag else -1,
        n=len(reqs), fail=fail, n_warm=len(warm),
        median=st.median(warm) if warm else float("nan"), p90=pct(warm, 90) if warm else float("nan"),
        p99=pct(warm, 99) if warm else float("nan"), mean=st.fmean(warm) if warm else float("nan"),
        med_1_1000=st.median(reqs[:1000]), med_1000_5500=st.median(reqs[1000:WARM]) if len(reqs) > 1000 else float("nan"),
        cpu_ms_per_req=(a.get("usage_usec", 0) - b.get("usage_usec", 0)) / 1000 / max(1, len(reqs)),
        c2_methods=lv.get(4, 0), c1_methods=lv.get(1, 0) + lv.get(2, 0) + lv.get(3, 0),
        jit_s=int(c.get("java.ci.totalTime", 0)) / 1e9, compiles=int(c.get("sun.ci.totalCompiles", 0)),
        cold_s=float(meta.split("cold_s=")[1].split()[0]),
    ))

hdr = ["run", "ver", "cond", "stop_level", "n", "fail", "n_warm", "median", "p90", "p99", "mean",
       "med_1_1000", "med_1000_5500", "cpu_ms_per_req", "c2_methods", "c1_methods", "jit_s", "compiles", "cold_s"]
w = csv.writer(sys.stdout, delimiter="\t")
w.writerow(hdr)
for r in sorted(rows, key=lambda r: (r["ver"], r["cond"], r["run"])):
    w.writerow([f"{r[h]:.3f}" if isinstance(r[h], float) else r[h] for h in hdr])
with open(os.path.join(HERE, "por_execucao.csv"), "w", newline="") as fh:
    cw = csv.DictWriter(fh, fieldnames=["tag"] + hdr); cw.writeheader()
    for r in rows: cw.writerow({k: r[k] for k in ["tag"] + hdr})

print("\n# médias das 3 rodadas (janela seq > %d)" % WARM)
K = ("median", "p90", "p99", "mean", "med_1_1000", "med_1000_5500", "cpu_ms_per_req", "c2_methods", "jit_s")
agg = {}
for ver in ("sb", "qj"):
    for cond in ("c1", "c2"):
        sel = [r for r in rows if r["ver"] == ver and r["cond"] == cond]
        if sel:
            agg[ver, cond] = {k: st.fmean(r[k] for r in sel) for k in K}
            print(f"{ver} {cond} n={len(sel)} " + " ".join(f"{k}={agg[ver, cond][k]:.2f}" for k in K))

print("\n# C2 vs C1 por versão")
for ver in ("sb", "qj"):
    if (ver, "c1") in agg and (ver, "c2") in agg:
        x, y = agg[ver, "c1"], agg[ver, "c2"]
        print(f"{ver}: " + "  ".join(f"{k} {x[k]:.2f}->{y[k]:.2f} ({100 * (y[k] / x[k] - 1):+.1f}%)"
                                     for k in ("median", "p90", "cpu_ms_per_req", "med_1_1000", "med_1000_5500")))

print("\n# gap QJ vs SB por condição (média das medianas; e por rodada)")
for cond in ("c1", "c2"):
    if ("sb", cond) in agg and ("qj", cond) in agg:
        s, q = agg["sb", cond], agg["qj", cond]
        per = []
        for run in sorted({r["run"] for r in rows}):
            rs = [r for r in rows if r["run"] == run and r["cond"] == cond]
            d = {r["ver"]: r for r in rs}
            if "sb" in d and "qj" in d:
                per.append(f"r{run} {100 * (d['qj']['median'] / d['sb']['median'] - 1):+.1f}% ({d['qj']['median'] - d['sb']['median']:+.2f} ms)")
        print(f"{cond}: mediana {q['median']:.2f} vs {s['median']:.2f} = {100 * (q['median'] / s['median'] - 1):+.1f}% "
              f"({q['median'] - s['median']:+.2f} ms) | p90 {100 * (q['p90'] / s['p90'] - 1):+.1f}% "
              f"| cpu {100 * (q['cpu_ms_per_req'] / s['cpu_ms_per_req'] - 1):+.1f}% | " + "; ".join(per))

with open(os.path.join(HERE, "curva_aquecimento.csv"), "w", newline="") as fh:
    cw = csv.writer(fh)
    n = max(map(len, curves.values()))
    cw.writerow(["seq_ini"] + sorted(curves))
    for i in range(n):
        cw.writerow([i * BIN] + [f"{curves[t][i]:.3f}" if i < len(curves[t]) else "" for t in sorted(curves)])
print("\n# curva (mediana por bloco de %d invocações), média por versão×condição" % BIN)
for ver in ("sb", "qj"):
    for cond in ("c1", "c2"):
        cs = [curves[r["tag"]] for r in rows if r["ver"] == ver and r["cond"] == cond]
        if cs:
            m = min(map(len, cs))
            print(f"{ver} {cond}: " + " ".join(f"{st.fmean(c[i] for c in cs):.1f}" for i in range(m)))
