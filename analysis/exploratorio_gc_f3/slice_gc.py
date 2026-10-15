#!/usr/bin/env python3
"""Refatia o gc.log por RODADA usando timestamp absoluto, nao offset de bytes.

Motivo: o -Xlog do JVM rotaciona em 20 MB por default (filesize=20M), o que
quebrou o fatiamento por offset a partir da r2. As fontes brutas ficam em
results/gc_raw/ (gc.log.N rotacionados + gc.stream.<ver>.log capturado ao vivo);
este script uniao-deduplica por linha, ordena por tempo e corta a janela
[k6_start, k6_end] de cada rodada, sobrescrevendo results/<ver>-rN.gc.log.

Uso: slice_gc.py [sb|qj ...]
"""
import glob, json, os, re, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
RAW = os.path.join(RES, "gc_raw")
RE_TS = re.compile(r'^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+[+-]\d{4})\]')


def ep(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def load_raw(ver):
    """Le todas as fontes brutas, dedupe por linha, devolve [(epoch, linha)] ordenado."""
    files = sorted(glob.glob(os.path.join(RAW, "gc.log.*"))) + \
            sorted(glob.glob(os.path.join(RAW, f"gc.stream.{ver}.log*")))
    seen, out, nots = set(), [], 0
    for f in files:
        with open(f, errors="replace") as fp:
            for line in fp:
                if line in seen:
                    continue
                seen.add(line)
                m = RE_TS.match(line)
                if not m:
                    nots += 1
                    continue
                out.append((ep(m.group(1)), line))
    out.sort(key=lambda x: x[0])
    print(f"  [{ver}] {len(files)} fontes, {len(out)} linhas com timestamp, {nots} sem")
    if out:
        print(f"  [{ver}] cobertura: {datetime.fromtimestamp(out[0][0])} -> {datetime.fromtimestamp(out[-1][0])}")
    return out


def main():
    vers = sys.argv[1:] or ["sb", "qj"]
    for ver in vers:
        metas = sorted(glob.glob(os.path.join(RES, f"{ver}-r*.meta.json")))
        metas = [m for m in metas if "r99" not in m]
        if not metas:
            print(f"  [{ver}] sem rodadas"); continue
        raw = load_raw(ver)
        if not raw:
            print(f"  [{ver}] SEM FONTE BRUTA -- slices nao refeitos"); continue
        times = [r[0] for r in raw]
        import bisect
        for mp in metas:
            meta = json.load(open(mp))
            tag = f"{ver}-r{meta['round']}"
            a, b = meta["k6_start_epoch"], meta["k6_end_epoch"]
            i, j = bisect.bisect_left(times, a), bisect.bisect_right(times, b)
            sl = [r[1] for r in raw[i:j]]
            cov = "OK" if (times[0] <= a and times[-1] >= b) else "INCOMPLETA"
            with open(os.path.join(RES, f"{tag}.gc.log"), "w") as fp:
                fp.writelines(sl)
            print(f"  [{tag}] {len(sl)} linhas, janela {int(b-a)}s, cobertura {cov}")


if __name__ == "__main__":
    main()
