#!/usr/bin/env python3
"""Estatística descritiva do teste exploratório de build (n=5 por versão, sem teste de hipótese).

Entradas: build_runs.csv, profiles/*.html. Saídas: resumo_por_versao.csv, razoes_mediana.csv,
tarefas_gradle.csv, analise.txt.
"""
import csv
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent
NAMES = {"os-sb": "Order Service · Spring Boot", "os-qj": "Order Service · Quarkus JVM",
         "os-qn": "Order Service · Quarkus Native", "op-sb": "Order Processor · Spring Boot",
         "op-qj": "Order Processor · Quarkus JVM", "op-qn": "Order Processor · Quarkus Native"}
ORDER = list(NAMES)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def desc(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return dict(n=0)
    mean = st.mean(v)
    sd = st.stdev(v) if len(v) > 1 else 0.0
    return dict(n=len(v), median=st.median(v), min=min(v), max=max(v), mean=mean, sd=sd,
                cv_pct=100 * sd / mean if mean else None)


def load_runs():
    rows = list(csv.DictReader(open(D / "build_runs.csv")))
    # Execução válida por repetição medida: a medida, ou o retry dela se a medida falhou.
    by = defaultdict(dict)
    for r in rows:
        if r["kind"] not in ("measured", "retry"):
            continue
        rep = r["rep"].rstrip("b")
        key = (r["version"], rep)
        tot = by[key].setdefault(r["run_id"], {})
        tot[r["phase"]] = r
    valid = defaultdict(list)
    for (ver, rep), runs in sorted(by.items()):
        ok = [rid for rid, ph in runs.items() if ph.get("total", {}).get("exit_code") == "0"]
        if ok:
            valid[ver].append(runs[sorted(ok)[0]])
    # Relê os números do native-image direto dos logs (o aquecimento foi gravado antes da correção
    # do regex para vírgula decimal; ver NOTAS).
    from run_one import parse_native
    for ver, runs in valid.items():
        if ver.endswith("qn"):
            for ph in runs:
                s, p, l = parse_native(D / ph["total"]["log_file"])
                ph["total"].update(native_image_s=s, native_peak_rss_gb=p, native_cpu_load=l)
    return rows, valid


def parse_profile(path):
    txt = Path(path).read_text(errors="replace")
    out = {}
    summ = txt.split("<h2>Configuration</h2>")[0]
    for k, v in re.findall(r"<td>([^<]+)</td>\s*<td class=\"numeric\">([^<]+)</td>", summ):
        out["summary:" + k] = to_s(v)
    task = txt.split("<h2>Task Execution</h2>")[-1]
    for k, v in re.findall(r"<td class=\"indentPath\">([^<]+)</td>\s*<td class=\"numeric\">([^<]+)</td>", task):
        out["task" + k] = to_s(v)
    return out


def to_s(v):
    s = 0.0
    for amt, unit in re.findall(r"([\d.]+)(ms|s|m|h)", v):
        s += float(amt) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return s


def main():
    rows, valid = load_runs()
    resumo, lines = [], []
    med = {}
    for ver in ORDER:
        runs = valid.get(ver, [])
        if not runs:
            continue
        def col(phase, c):
            return [num(r.get(phase, {}).get(c)) for r in runs]
        tot_wall = desc(col("total", "wall_s"))
        cpu_host = desc([(a or 0) + (b or 0) for a, b in zip(col("total", "user_s"), col("total", "sys_s"))])
        rec = dict(version=ver, nome=NAMES[ver], layer=runs[0]["total"]["layer"], n=tot_wall["n"])
        for pref, d in [("total_wall", tot_wall), ("gradle_wall", desc(col("gradle", "wall_s"))),
                        ("image_wall", desc(col("image", "wall_s"))), ("cpu_host_user_sys", cpu_host),
                        ("cpu_containers", desc(col("total", "docker_cpu_s"))),
                        ("cpu_sys_excess", desc(col("total", "sys_cpu_excess_s"))),
                        ("cpu_avg_pct16", desc(col("total", "cpu_avg_pct_of_16"))),
                        ("mem_peak_above_base_mb", desc(col("total", "mem_peak_above_baseline_mb"))),
                        ("swap_peak_mb", desc(col("total", "swap_peak_mb"))),
                        ("tree_rss_peak_mb", desc(col("total", "tree_rss_peak_mb"))),
                        ("container_mem_peak_mb", desc(col("total", "docker_scope_peak_max_mb"))),
                        ("native_image_s", desc(col("total", "native_image_s"))),
                        ("native_peak_rss_gb", desc(col("total", "native_peak_rss_gb"))),
                        ("native_cpu_load", desc(col("total", "native_cpu_load"))),
                        ("artifact_mb", desc([x / 1e6 if x else None for x in col("total", "artifact_bytes")])),
                        ("image_mb", desc([x / 1e6 if x else None for x in col("total", "image_bytes")]))]:
            for k, val in d.items():
                if k != "n":
                    rec[f"{pref}_{k}"] = round(val, 3) if isinstance(val, float) else val
        rec["reps"] = " ".join(r["total"]["rep"] for r in runs)
        resumo.append(rec)
        med[ver] = rec

    with open(D / "resumo_por_versao.csv", "w", newline="") as f:
        keys = sorted({k for r in resumo for k in r}, key=lambda k: (k not in ("version", "nome", "layer", "n", "reps"), k))
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(resumo)

    ratios = []
    for layer, (sb, qj, qn) in {"1": ("os-sb", "os-qj", "os-qn"), "2": ("op-sb", "op-qj", "op-qn")}.items():
        for metric in ("total_wall_median", "gradle_wall_median", "cpu_sys_excess_median",
                       "cpu_host_user_sys_median", "mem_peak_above_base_mb_median"):
            for num_v, den_v in ((qn, qj), (qn, sb), (qj, sb)):
                if num_v in med and den_v in med:
                    a, b = med[num_v].get(metric), med[den_v].get(metric)
                    if a is not None and b:
                        ratios.append(dict(layer=layer, metric=metric, ratio=f"{num_v}/{den_v}",
                                           numerator=a, denominator=b, value=round(a / b, 2)))
    with open(D / "razoes_mediana.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["layer", "metric", "ratio", "numerator", "denominator", "value"])
        w.writeheader()
        w.writerows(ratios)

    # Tempos por tarefa Gradle (mediana das execuções válidas)
    task_rows = []
    for ver in ORDER:
        per = defaultdict(list)
        for r in valid.get(ver, []):
            p = D / "profiles" / f"{r['total']['run_id']}.html"
            if p.exists():
                for k, v in parse_profile(p).items():
                    per[k].append(v)
        for k, vs in sorted(per.items(), key=lambda kv: -st.median(kv[1])):
            if st.median(vs) >= 0.05 or k.startswith("summary:"):
                task_rows.append(dict(version=ver, item=k, n=len(vs), median_s=round(st.median(vs), 3),
                                      min_s=round(min(vs), 3), max_s=round(max(vs), 3)))
    with open(D / "tarefas_gradle.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["version", "item", "n", "median_s", "min_s", "max_s"])
        w.writeheader()
        w.writerows(task_rows)

    # Texto
    lines.append("Exploratório — estatística descritiva (execuções válidas medidas; n por versão abaixo)\n")
    for r in resumo:
        lines.append(f"{r['nome']} (n={r['n']}, reps {r['reps']})")
        lines.append(f"  total  mediana {r['total_wall_median']:.1f}s  [{r['total_wall_min']:.1f}–{r['total_wall_max']:.1f}]"
                     f"  média {r['total_wall_mean']:.1f}±{r['total_wall_sd']:.1f}s  CV {r['total_wall_cv_pct']:.1f}%")
        lines.append(f"  gradle mediana {r['gradle_wall_median']:.1f}s" +
                     (f"   imagem mediana {r['image_wall_median']:.1f}s" if 'image_wall_median' in r else ""))
        lines.append(f"  CPU host (user+sys) {r['cpu_host_user_sys_median']:.0f}s · CPU contêineres {r.get('cpu_containers_median', 0):.0f}s"
                     f" · CPU sistema em excesso {r['cpu_sys_excess_median']:.0f}s · CPU média {r['cpu_avg_pct16_median']:.0f}% de 16 threads")
        lines.append(f"  memória sistema acima da base: mediana {r['mem_peak_above_base_mb_median']:.0f} MB, máx {r['mem_peak_above_base_mb_max']:.0f} MB;"
                     f" RSS árvore de processos máx {r['tree_rss_peak_mb_max']:.0f} MB; maior pico de contêiner máx {r.get('container_mem_peak_mb_max', 0):.0f} MB;"
                     f" swap máx {r['swap_peak_mb_max']:.0f} MB")
        if r.get("native_image_s_median") is not None:
            lines.append(f"  native-image: {r['native_image_s_median']:.1f}s (mediana), Peak RSS {r['native_peak_rss_gb_median']:.2f} GB,"
                         f" CPU load {r['native_cpu_load_median']:.2f}")
        lines.append(f"  artefato {r['artifact_mb_median']:.1f} MB" +
                     (f" · imagem {r['image_mb_median']:.1f} MB" if r.get('image_mb_median') else ""))
        lines.append("")
    lines.append("Razões pela mediana")
    for x in ratios:
        lines.append(f"  camada {x['layer']} {x['metric']:32s} {x['ratio']:13s} {x['value']:.2f}  ({x['numerator']:.1f} / {x['denominator']:.1f})")
    (D / "analise.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
