#!/usr/bin/env python3
"""Exploratorio gc_f3: cruza pausas de GC (gc.log) com latencia por segundo (k6 csv).

Nao e resultado formal do TCC. Saidas:
  gc_p95_por_rodada.csv   -- p95/p99/max por rodada + estatisticas de pausa
  gc_pausas.csv           -- toda pausa individual (inicio, duracao, tipo)
  latencia_por_segundo.csv-- por segundo: n, p95, max, ms de pausa de GC naquele segundo
  correlacao.csv          -- segundos com/sem pausa longa vs latencia
"""
import csv, glob, gzip, json, os, re, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE
RES = os.path.join(HERE, "results")

# "At safepoint: 4523781 ns" dentro de uma linha de safepoint = pausa real (stop-the-world)
RE_SAFEPOINT = re.compile(
    r'^\[(?P<ts>[\d\-T:.+]+)\]\[(?P<up>[\d.]+)s\]\[info\]\[safepoint\s*\]\s*'
    r'Safepoint "(?P<op>[^"]+)".*At safepoint: (?P<at>\d+) ns.*Total: (?P<total>\d+) ns')
# "GC(123) Pause Young (Allocation Failure) 12M->1M(20M) 8.123ms"
RE_PAUSE = re.compile(
    r'^\[(?P<ts>[\d\-T:.+]+)\]\[(?P<up>[\d.]+)s\]\[info\]\[gc\s*\]\s*'
    r'GC\((?P<id>\d+)\) (?P<kind>Pause \w+[^)]*\)?)[^\d]*?(?P<ms>[\d.]+)ms\s*$')


def parse_epoch(ts):
    # 2026-09-20T23:17:21.679+0000
    from datetime import datetime
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def read_gc(path):
    """Devolve lista de (epoch_inicio, dur_ms, rotulo) das pausas stop-the-world."""
    pauses = []
    with open(path, errors="replace") as fp:
        for line in fp:
            m = RE_SAFEPOINT.search(line)
            if m:
                dur_ms = int(m.group("at")) / 1e6
                total_ms = int(m.group("total")) / 1e6
                end = parse_epoch(m.group("ts"))
                pauses.append((end - total_ms / 1000.0, dur_ms, m.group("op"), total_ms))
    return pauses


def read_k6(path):
    """Devolve dict epoch_seg -> lista de latencias (ms) da fase de carga."""
    per_s = defaultdict(list)
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", newline="") as fp:
        rd = csv.reader(fp)
        hdr = next(rd)
        i_m, i_t, i_v, i_tags = (hdr.index("metric_name"), hdr.index("timestamp"),
                                 hdr.index("metric_value"), hdr.index("extra_tags"))
        for row in rd:
            if len(row) <= i_tags or row[i_m] != "http_req_duration":
                continue
            if "phase=setup" in row[i_tags]:
                continue
            per_s[int(row[i_t])].append(float(row[i_v]))
    return per_s


def main():
    rounds = sorted(glob.glob(os.path.join(RES, "*-r*.meta.json")))
    if not rounds:
        sys.exit("sem rodadas em results/")

    per_round, all_pauses, per_sec = [], [], []
    for mp in rounds:
        meta = json.load(open(mp))
        tag = f"{meta['ver']}-r{meta['round']}"
        gcp = os.path.join(RES, f"{tag}.gc.log")
        csvp = os.path.join(RES, f"{tag}.k6.csv.gz")
        if not (os.path.exists(gcp) and os.path.exists(csvp)):
            print(f"  [skip] {tag}: artefato faltando"); continue

        pauses = read_gc(gcp)
        lat = read_k6(csvp)
        allv = np.array([v for vs in lat.values() for v in vs])
        if allv.size == 0:
            print(f"  [skip] {tag}: sem latencia"); continue

        # ms de pausa por segundo
        pause_by_s = defaultdict(float)
        pause_max_by_s = defaultdict(float)
        for start, dur, op, total in pauses:
            pause_by_s[int(start)] += dur
            pause_max_by_s[int(start)] = max(pause_max_by_s[int(start)], dur)
            all_pauses.append(dict(ver=meta["ver"], round=meta["round"], epoch=round(start, 3),
                                   dur_ms=round(dur, 3), total_ms=round(total, 3), op=op))

        durs = np.array([p[1] for p in pauses]) if pauses else np.array([0.0])
        wall = max(1.0, meta["k6_end_epoch"] - meta["k6_start_epoch"])
        per_round.append(dict(
            ver=meta["ver"], round=meta["round"], n_req=int(allv.size),
            p50=round(float(np.percentile(allv, 50)), 2),
            p95=round(float(np.percentile(allv, 95)), 2),
            p99=round(float(np.percentile(allv, 99)), 2),
            max_ms=round(float(allv.max()), 2),
            n_pausas=len(pauses), pausas_por_min=round(len(pauses) / (wall / 60), 1),
            pausa_media_ms=round(float(durs.mean()), 2),
            pausa_p99_ms=round(float(np.percentile(durs, 99)), 2),
            pausa_max_ms=round(float(durs.max()), 2),
            tempo_em_gc_pct=round(float(durs.sum()) / 1000.0 / wall * 100, 4),
            orders_rows=meta.get("orders_rows_after"),
        ))

        for s, vs in sorted(lat.items()):
            a = np.array(vs)
            per_sec.append(dict(ver=meta["ver"], round=meta["round"], epoch=s,
                                t_rel=s - meta["k6_start_epoch"], n=len(vs),
                                p95=round(float(np.percentile(a, 95)), 2),
                                max_ms=round(float(a.max()), 2),
                                gc_ms=round(pause_by_s.get(s, 0.0), 3),
                                gc_max_ms=round(pause_max_by_s.get(s, 0.0), 3)))

    def dump(name, rows):
        if not rows: return
        p = os.path.join(OUT, name)
        with open(p, "w", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        print(f"[ok] {p}  ({len(rows)} linhas)")

    dump("gc_p95_por_rodada.csv", per_round)
    dump("gc_pausas.csv", all_pauses)
    dump("latencia_por_segundo.csv", per_sec)

    # correlacao: segundos com pausa longa vs sem
    corr = []
    for ver in sorted({r["ver"] for r in per_sec}):
        rows = [r for r in per_sec if r["ver"] == ver]
        gc_ms = np.array([r["gc_ms"] for r in rows])
        mx = np.array([r["max_ms"] for r in rows])
        p95 = np.array([r["p95"] for r in rows])
        # limiar: pausa longa = acima do p95 das pausas por segundo (>0)
        pos = gc_ms[gc_ms > 0]
        thr = float(np.percentile(pos, 95)) if pos.size else 0.0
        hi, lo = gc_ms >= max(thr, 1e-9), gc_ms == 0
        with np.errstate(invalid="ignore"):
            r_max = float(np.corrcoef(gc_ms, mx)[0, 1]) if gc_ms.std() > 0 else float("nan")
            r_p95 = float(np.corrcoef(gc_ms, p95)[0, 1]) if gc_ms.std() > 0 else float("nan")
        corr.append(dict(
            ver=ver, n_seg=len(rows), seg_com_pausa=int((gc_ms > 0).sum()),
            limiar_pausa_longa_ms=round(thr, 3),
            max_ms_seg_pausa_longa=round(float(mx[hi].mean()), 2) if hi.any() else None,
            max_ms_seg_sem_pausa=round(float(mx[lo].mean()), 2) if lo.any() else None,
            p95_seg_pausa_longa=round(float(p95[hi].mean()), 2) if hi.any() else None,
            p95_seg_sem_pausa=round(float(p95[lo].mean()), 2) if lo.any() else None,
            pearson_gcms_vs_maxlat=round(r_max, 4), pearson_gcms_vs_p95=round(r_p95, 4),
            # quanto da cauda a pausa poderia explicar: pausa max vs latencia max
            pausa_max_ms=round(float(gc_ms.max()), 2), lat_max_ms=round(float(mx.max()), 2)))
    dump("correlacao.csv", corr)

    print("\n=== p95 por rodada ===")
    for r in per_round:
        print(f"  {r['ver']}-r{r['round']}: p95={r['p95']:8.1f}ms p99={r['p99']:9.1f}ms "
              f"max={r['max_ms']:9.1f}ms | pausas/min={r['pausas_por_min']:6.1f} "
              f"media={r['pausa_media_ms']:5.2f}ms max={r['pausa_max_ms']:7.2f}ms "
              f"tempo_em_gc={r['tempo_em_gc_pct']:.3f}%")
    print("\n=== correlacao (segundos) ===")
    for c in corr:
        print(f"  {c['ver']}: r(gc_ms,max_lat)={c['pearson_gcms_vs_maxlat']} | "
              f"max_lat com pausa longa={c['max_ms_seg_pausa_longa']}ms vs sem pausa={c['max_ms_seg_sem_pausa']}ms | "
              f"pausa max={c['pausa_max_ms']}ms vs lat max={c['lat_max_ms']}ms")


if __name__ == "__main__":
    main()
