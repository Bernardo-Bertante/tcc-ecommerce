#!/usr/bin/env python3
"""Mede uma execução de build (exploratório, fora do desenho oficial).

Uso: run_one.py --version os-qn --rep r1 --kind measured

Fases: 'baseline' (pausa antes do build, só amostrador), 'gradle' (comando oficial com clean) e,
na camada 1, 'image' (docker build --no-cache). Amostrador a 1 Hz em thread própria lendo /proc e os
cgroups dos contêineres Docker (onde roda o native-image e os Testcontainers).
"""
import argparse
import csv
import glob
import os
import re
import resource
import shutil
import subprocess
import threading
import time
from pathlib import Path

WORK = Path.home() / "exp-build-work" / "repo"
OUT = Path(__file__).resolve().parent
CLK = os.sysconf("SC_CLK_TCK")
NATIVE_FLAGS = [
    "-Dquarkus.package.type=native",
    "-Dquarkus.native.container-build=true",
    "-Dquarkus.native.native-image-xmx=6g",
]

# Comandos oficiais (infrastructure/aws/scripts/prepare-*.sh), Native com clean (decisão iv).
VERSIONS = {
    "os-sb": dict(layer=1, module="order-service/springboot",
                  gradle=["clean", "bootJar"],
                  dockerfile="Dockerfile",
                  artifact="build/libs/order-service-springboot-0.0.1-SNAPSHOT.jar"),
    "os-qj": dict(layer=1, module="order-service/quarkus",
                  gradle=["clean", "build"],
                  dockerfile="Dockerfile.jvm",
                  artifact="build/quarkus-app"),
    "os-qn": dict(layer=1, module="order-service/quarkus",
                  gradle=["clean", "build", *NATIVE_FLAGS],
                  dockerfile="Dockerfile.native",
                  artifact="build/order-service-quarkus-0.0.1-SNAPSHOT-runner"),
    "op-sb": dict(layer=2, module="order-processor/springboot",
                  gradle=["clean", "build"],
                  dockerfile=None,
                  artifact="build/distributions/order-processor-springboot-0.0.1-SNAPSHOT-lambda.zip"),
    "op-qj": dict(layer=2, module="order-processor/quarkus",
                  gradle=["clean", "build"],
                  dockerfile=None,
                  artifact="build/function.zip"),
    "op-qn": dict(layer=2, module="order-processor/quarkus",
                  gradle=["clean", "build", *NATIVE_FLAGS],
                  dockerfile=None,
                  artifact="build/function.zip"),
}

ENV = dict(os.environ)
ENV.update({
    "DOCKER_HOST": "unix:///var/run/docker.sock",
    "TESTCONTAINERS_DOCKER_CLIENT_STRATEGY":
        "org.testcontainers.dockerclient.EnvironmentAndSystemPropertyClientProviderStrategy",
    "TESTCONTAINERS_RYUK_DISABLED": "true",
})

CSV_FIELDS = [
    "run_id", "version", "layer", "rep", "kind", "phase", "start_epoch", "end_epoch", "wall_s",
    "user_s", "sys_s", "child_maxrss_mb", "exit_code",
    "loadavg1_pre", "memavail_mb_pre", "swap_used_mb_pre",
    "mem_baseline_mb", "mem_peak_mb", "mem_peak_above_baseline_mb", "swap_peak_mb",
    "sys_cpu_busy_s", "sys_cpu_baseline_rate", "sys_cpu_excess_s", "cpu_avg_pct_of_16",
    "tree_rss_peak_mb", "docker_mem_peak_sum_mb", "docker_scope_peak_max_mb", "docker_cpu_s",
    "native_image_s", "native_peak_rss_gb", "native_cpu_load",
    "artifact_bytes", "image_bytes", "samples_file", "log_file",
]


def meminfo():
    d = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            d[k] = int(v.split()[0]) // 1024
    return d


def cpu_busy_jiffies():
    with open("/proc/stat") as f:
        p = [int(x) for x in f.readline().split()[1:]]
    # user nice system idle iowait irq softirq steal
    return sum(p[:8]) - p[3] - p[4]


def proc_children_rss(root_pid):
    parent, rss = {}, {}
    for st in glob.glob("/proc/[0-9]*/stat"):
        try:
            with open(st) as f:
                data = f.read()
            rest = data[data.rfind(")") + 2:].split()
            pid = int(st.split("/")[2])
            parent[pid] = int(rest[1])
            rss[pid] = int(rest[21]) * 4 // 1024  # páginas de 4 KiB -> MiB
        except (OSError, ValueError, IndexError):
            continue
    total, stack = 0, [root_pid]
    kids = {}
    for pid, pp in parent.items():
        kids.setdefault(pp, []).append(pid)
    seen = set()
    while stack:
        p = stack.pop()
        for c in kids.get(p, []):
            if c not in seen:
                seen.add(c)
                total += rss.get(c, 0)
                stack.append(c)
    return total


def read_int(path, key=None):
    try:
        with open(path) as f:
            if key is None:
                return int(f.read().strip())
            for line in f:
                k, v = line.split()
                if k == key:
                    return int(v)
    except (OSError, ValueError):
        return None
    return None


class Sampler(threading.Thread):
    def __init__(self, path):
        super().__init__(daemon=True)
        self.path = path
        self.phase = "baseline"
        self.stop_evt = threading.Event()
        self.scope_cpu = {}   # scope -> último usage_usec visto
        self.scope_peak = {}  # scope -> maior memory.peak visto
        self.rows = []

    def run(self):
        me = os.getpid()
        with open(self.path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "phase", "mem_used_mb", "memavail_mb", "swap_used_mb", "cpu_busy_jiffies",
                        "tree_rss_mb", "docker_mem_sum_mb", "docker_cpu_usec_cum", "n_containers", "loadavg1"])
            while not self.stop_evt.is_set():
                t = time.time()
                m = meminfo()
                used = m["MemTotal"] - m["MemAvailable"]
                swap = m["SwapTotal"] - m["SwapFree"]
                busy = cpu_busy_jiffies()
                tree = proc_children_rss(me)
                dmem, n = 0, 0
                for scope in glob.glob("/sys/fs/cgroup/system.slice/docker-*.scope"):
                    cur = read_int(scope + "/memory.current")
                    pk = read_int(scope + "/memory.peak")
                    cpu = read_int(scope + "/cpu.stat", "usage_usec")
                    if cur is not None:
                        dmem += cur // (1024 * 1024)
                        n += 1
                    if pk is not None:
                        self.scope_peak[scope] = max(self.scope_peak.get(scope, 0), pk // (1024 * 1024))
                    if cpu is not None:
                        self.scope_cpu[scope] = max(self.scope_cpu.get(scope, 0), cpu)
                with open("/proc/loadavg") as lf:
                    la = float(lf.read().split()[0])
                row = [round(t, 3), self.phase, used, m["MemAvailable"], swap, busy, tree, dmem,
                       sum(self.scope_cpu.values()), n, la]
                w.writerow(row)
                f.flush()
                self.rows.append(row)
                self.stop_evt.wait(max(0.0, 1.0 - (time.time() - t)))


def run_phase(cmd, cwd, log_path, sampler, phase):
    sampler.phase = phase
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    s = time.time()
    with open(log_path, "a") as log:
        log.write(f"\n### {phase}: {' '.join(cmd)} (cwd={cwd}) start={s:.3f}\n")
        log.flush()
        p = subprocess.run(cmd, cwd=cwd, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    e = time.time()
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    with open(log_path, "a") as log:
        log.write(f"### {phase}: exit={p.returncode} end={e:.3f} wall={e - s:.3f}\n")
    return dict(start=s, end=e, wall=e - s, user=r1.ru_utime - r0.ru_utime, sys=r1.ru_stime - r0.ru_stime,
                maxrss=r1.ru_maxrss // 1024, rc=p.returncode)


def window_stats(rows, s, e, baseline_rate, mem_base):
    w = [r for r in rows if s - 0.5 <= r[0] <= e + 1.5]
    if len(w) < 2:
        return {}
    busy = (w[-1][5] - w[0][5]) / CLK
    dur = w[-1][0] - w[0][0]
    peak = max(r[2] for r in w)
    return dict(
        mem_baseline_mb=round(mem_base), mem_peak_mb=peak, mem_peak_above_baseline_mb=round(peak - mem_base),
        swap_peak_mb=max(r[4] for r in w), sys_cpu_busy_s=round(busy, 1),
        sys_cpu_baseline_rate=round(baseline_rate, 3),
        sys_cpu_excess_s=round(busy - baseline_rate * dur, 1),
        cpu_avg_pct_of_16=round(100 * busy / dur / 16, 1) if dur > 0 else "",
        tree_rss_peak_mb=max(r[6] for r in w), docker_mem_peak_sum_mb=max(r[7] for r in w),
        docker_cpu_s=round((w[-1][8] - w[0][8]) / 1e6, 1),
    )


def du_bytes(path):
    p = Path(path)
    if p.is_file():
        return p.stat().st_size
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return ""


def parse_native(log_path):
    txt = Path(log_path).read_text(errors="replace")
    secs = peak = load = ""
    # O native-image formata números no locale do builder (aqui pt_BR: vírgula decimal).
    m = re.search(r"Finished generating '[^']+' in (?:(\d+)m )?([\d.,]+)s", txt)
    if m:
        secs = int(m.group(1) or 0) * 60 + float(m.group(2).replace(",", "."))
    m = re.search(r"Peak RSS: ([\d.,]+)GB \| CPU load: ([\d.,]+)", txt)
    if m:
        peak, load = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    return secs, peak, load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, choices=VERSIONS)
    ap.add_argument("--rep", required=True)
    ap.add_argument("--kind", required=True, choices=["smoke", "warmup", "measured", "retry"])
    ap.add_argument("--pause", type=float, default=30.0)
    ap.add_argument("--csv", default=str(OUT / "build_runs.csv"))
    a = ap.parse_args()

    v = VERSIONS[a.version]
    run_id = f"{a.version}_{a.rep}"
    for d in ("samples", "logs", "profiles"):
        (OUT / d).mkdir(exist_ok=True)
    samples = OUT / "samples" / f"{run_id}.csv"
    log = OUT / "logs" / f"{run_id}.log"
    log.write_text(f"run_id={run_id} kind={a.kind} host={os.uname().nodename}\n")

    with open("/proc/loadavg") as f:
        la_pre = float(f.read().split()[0])
    m = meminfo()
    pre = dict(loadavg1_pre=la_pre, memavail_mb_pre=m["MemAvailable"],
               swap_used_mb_pre=m["SwapTotal"] - m["SwapFree"])

    sampler = Sampler(samples)
    sampler.start()
    b0 = time.time()
    time.sleep(a.pause)  # pausa entre builds = janela de linha de base
    base_rows = [r for r in sampler.rows if r[0] >= b0 + min(10.0, a.pause / 3)]
    if len(base_rows) >= 2:
        baseline_rate = (base_rows[-1][5] - base_rows[0][5]) / CLK / (base_rows[-1][0] - base_rows[0][0])
        mem_base = sum(r[2] for r in base_rows) / len(base_rows)
    else:
        baseline_rate, mem_base = 0.0, float(meminfo()["MemTotal"] - meminfo()["MemAvailable"])

    module = WORK / v["module"]
    results = []
    g = run_phase(["./gradlew", *v["gradle"], "--no-daemon", "--profile", "--console=plain"],
                  module, log, sampler, "gradle")
    results.append(("gradle", g))
    prof = sorted((module / "build/reports/profile").glob("profile-*.html"))
    if prof:
        shutil.copy(prof[-1], OUT / "profiles" / f"{run_id}.html")

    artifact_bytes = du_bytes(module / v["artifact"]) if g["rc"] == 0 else ""
    image_bytes = ""
    if v["dockerfile"] and g["rc"] == 0:
        tag = f"exp-build/{a.version}:{a.rep}"
        img = run_phase(["docker", "build", "--no-cache", "--progress=plain", "-f", v["dockerfile"],
                         "-t", tag, "."], module, log, sampler, "image")
        results.append(("image", img))
        if img["rc"] == 0:
            out = subprocess.run(["docker", "image", "inspect", tag, "--format", "{{.Size}}"],
                                 env=ENV, capture_output=True, text=True)
            image_bytes = out.stdout.strip()
    time.sleep(1.5)
    sampler.stop_evt.set()
    sampler.join()

    native = parse_native(log) if a.version.endswith("qn") else ("", "", "")
    rows = []
    for phase, r in results:
        rows.append((phase, r))
    total = dict(start=results[0][1]["start"], end=results[-1][1]["end"],
                 user=sum(r["user"] for _, r in results), sys=sum(r["sys"] for _, r in results),
                 maxrss=max(r["maxrss"] for _, r in results),
                 rc=max(r["rc"] for _, r in results))
    total["wall"] = total["end"] - total["start"]
    rows.append(("total", total))

    new = not Path(a.csv).exists()
    with open(a.csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        for phase, r in rows:
            rec = dict(run_id=run_id, version=a.version, layer=v["layer"], rep=a.rep, kind=a.kind, phase=phase,
                       start_epoch=round(r["start"], 3), end_epoch=round(r["end"], 3), wall_s=round(r["wall"], 2),
                       user_s=round(r["user"], 2), sys_s=round(r["sys"], 2), child_maxrss_mb=r["maxrss"],
                       exit_code=r["rc"], samples_file=f"samples/{run_id}.csv", log_file=f"logs/{run_id}.log",
                       **pre)
            rec.update(window_stats(sampler.rows, r["start"], r["end"], baseline_rate, mem_base))
            if phase in ("gradle", "total"):
                rec.update(native_image_s=native[0], native_peak_rss_gb=native[1], native_cpu_load=native[2])
            if phase == "total":
                rec.update(artifact_bytes=artifact_bytes, image_bytes=image_bytes,
                           docker_scope_peak_max_mb=max(sampler.scope_peak.values(), default=0))
            w.writerow(rec)
    print(f"{run_id} kind={a.kind} rc={total['rc']} wall={total['wall']:.1f}s "
          f"gradle={g['wall']:.1f}s native={native[0]} artifact={artifact_bytes} image={image_bytes}", flush=True)
    raise SystemExit(1 if total["rc"] else 0)


if __name__ == "__main__":
    main()
