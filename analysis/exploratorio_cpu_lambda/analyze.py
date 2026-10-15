"""Resumo por rodada: latência k6 por invocação em regime aquecido (seq > WARM), mais throttling do cgroup."""
import csv, glob, os, re, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get("RESULTS_DIR", os.path.join(HERE, "results"))
WARM = int(os.environ.get("WARM", 1000))


def cpustat(path):
    try:
        return {k: int(v) for k, v in (l.split() for l in open(path))}
    except FileNotFoundError:
        return {}


def pct(xs, p):
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


rows = []
for f in sorted(glob.glob(os.path.join(RES, "[rh]*.k6.csv"))):
    tag = os.path.basename(f)[:-7]
    m = re.match(r"[rh](\d+)-(sb|qj|qja|sbu)-(free|lim)$", tag)
    if not m or "load_end" not in open(f"{RES}/{tag}.meta").read():
        continue
    reqs, checks_fail = [], 0
    with open(f) as fh:
        for r in csv.DictReader(fh):
            if r["metric_name"] == "http_req_duration":
                reqs.append(float(r["metric_value"]))  # 1 VU: ordem do arquivo = ordem de invocação
            elif r["metric_name"] == "checks" and float(r["metric_value"]) == 0:
                checks_fail += 1
    warm = sorted(reqs[WARM:])
    b, a = cpustat(f"{RES}/{tag}.cpustat.before"), cpustat(f"{RES}/{tag}.cpustat.after")
    dper = a.get("nr_periods", 0) - b.get("nr_periods", 0)
    dthr = a.get("nr_throttled", 0) - b.get("nr_throttled", 0)
    dusage = (a.get("usage_usec", 0) - b.get("usage_usec", 0)) / 1000
    def snmp_tcp(path):
        try:
            lines = [l.split() for l in open(path) if l.startswith("Tcp:")]
            return dict(zip(lines[0][1:], map(int, lines[1][1:])))
        except (FileNotFoundError, IndexError):
            return {}
    sb_, sa_ = snmp_tcp(f"{RES}/{tag}.snmp.before"), snmp_tcp(f"{RES}/{tag}.snmp.after")
    active_opens = sa_.get("ActiveOpens", 0) - sb_.get("ActiveOpens", 0)
    tw8000 = est8000 = 0
    try:
        for l in open(f"{RES}/{tag}.tcp.mid"):
            p = l.split()
            if len(p) > 3 and p[2].endswith(":1F40"):  # remote port 8000
                # /proc/net/tcp: 01=ESTABLISHED, 06=TIME_WAIT
                tw8000 += p[3] == "06"; est8000 += p[3] == "01"
    except FileNotFoundError:
        pass
    cold = open(f"{RES}/{tag}.meta").read().split("cold_s=")[1].split()[0]
    rows.append(dict(
        run=int(m[1]), ver=m[2], cond=m[3], n=len(reqs), n_warm=len(warm), fail=checks_fail,
        median=st.median(warm), mean=st.fmean(warm), p90=pct(warm, 90), p99=pct(warm, 99),
        cpu_ms_per_req=dusage / max(1, len(reqs)),
        throttled_pct=100 * dthr / dper if dper else 0.0, cold_s=float(cold),
        opens_per_req=active_opens / max(1, len(reqs)), est_8000_mid=est8000, timewait_8000_mid=tw8000,
    ))

hdr = ["run", "ver", "cond", "n", "n_warm", "fail", "median", "mean", "p90", "p99", "cpu_ms_per_req", "throttled_pct", "cold_s", "opens_per_req", "est_8000_mid", "timewait_8000_mid"]
w = csv.writer(sys.stdout, delimiter="\t")
w.writerow(hdr)
for r in sorted(rows, key=lambda r: (r["cond"], r["ver"], r["run"])):
    w.writerow([f"{r[h]:.2f}" if isinstance(r[h], float) else r[h] for h in hdr])

print()
for cond in ("free", "lim"):
    agg = {}
    for ver in ("sb", "qj", "qja", "sbu"):
        sel = [r for r in rows if r["cond"] == cond and r["ver"] == ver]
        if sel:
            agg[ver] = {k: st.fmean(r[k] for r in sel) for k in ("median", "mean", "p90", "cpu_ms_per_req")}
    if "sb" in agg:
        s = agg["sb"]
        for ver, v in agg.items():
            print(f"{cond} {ver:>3} vs sb: " + "  ".join(
                f"{k} {v[k]:.2f} ({100 * (v[k] / s[k] - 1):+.1f}%)" for k in ("median", "mean", "p90", "cpu_ms_per_req")))
