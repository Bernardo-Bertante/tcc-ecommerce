#!/usr/bin/env python3
"""Teste de taxa-base da correlacao GC x cauda de latencia.

Por que existe: dizer que "os segundos de pior latencia contem pausa de GC" nao
significa nada se QUASE TODO segundo contem pausa. Com ~600 pausas/min (10/s) no
Spring Boot, a coincidencia temporal e garantida por construcao. Este script mede
a taxa-base e o lift, e separa a questao da COINCIDENCIA da questao da MAGNITUDE.

Le latencia_por_segundo.csv e gc_pausas.csv (saidas do analyze.py).
"""
import csv, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "latencia_por_segundo.csv"))))
out = []

print("=" * 78)
print("1) COINCIDENCIA -- corrigida por taxa-base")
print("=" * 78)
for ver in ["sb", "qj"]:
    R = [r for r in rows if r["ver"] == ver]
    gc = np.array([float(r["gc_ms"]) for r in R])
    gcmax = np.array([float(r["gc_max_ms"]) for r in R])
    mx = np.array([float(r["max_ms"]) for r in R])
    base = (gc > 0).mean() * 100
    print(f"\n  {ver}: {len(R)} segundos de carga")
    print(f"    taxa-base: {base:.1f}% de TODOS os segundos contem alguma pausa")
    for n in (20, 100, 500):
        idx = np.argsort(-mx)[:n]
        top = (gc[idx] > 0).mean() * 100
        print(f"    {n:4d} piores segundos de latencia: {top:5.1f}% contem pausa  ->  lift {top/base:.2f}x")
    out.append(dict(ver=ver, n_seg=len(R), taxa_base_pct=round(base, 2)))

print()
print("=" * 78)
print("2) MAGNITUDE -- quanto da cauda a pausa poderia cobrir")
print("=" * 78)
for ver, o in zip(["sb", "qj"], out):
    R = [r for r in rows if r["ver"] == ver]
    gc = np.array([float(r["gc_ms"]) for r in R])
    gcmax = np.array([float(r["gc_max_ms"]) for r in R])
    mx = np.array([float(r["max_ms"]) for r in R])
    idx = np.argsort(-mx)[:20]
    print(f"\n  {ver}: 20 segundos de pior latencia")
    print(f"    latencia maxima media nesses segundos : {mx[idx].mean():8.1f} ms")
    print(f"    maior pausa media nesses segundos     : {gcmax[idx].mean():8.1f} ms  ({gcmax[idx].mean()/mx[idx].mean()*100:.1f}% da latencia)")
    print(f"    soma de pausas media nesses segundos  : {gc[idx].mean():8.1f} ms  ({gc[idx].mean()/mx[idx].mean()*100:.1f}% da latencia)")
    print(f"    pior caso absoluto: maior pausa {gcmax.max():.1f} ms vs maior latencia {mx.max():.1f} ms ({gcmax.max()/mx.max()*100:.1f}%)")
    j = np.argsort(-gcmax)[:20]
    print(f"    sobreposicao {{20 piores latencias}} ∩ {{20 maiores pausas}}: {len(set(idx.tolist()) & set(j.tolist()))}/20")
    o.update(top20_lat_max_ms=round(float(mx[idx].mean()), 1),
             top20_maior_pausa_ms=round(float(gcmax[idx].mean()), 1),
             top20_pausa_pct_da_lat=round(float(gcmax[idx].mean()/mx[idx].mean()*100), 1),
             pausa_max_abs_ms=round(float(gcmax.max()), 1),
             lat_max_abs_ms=round(float(mx.max()), 1))

p = os.path.join(HERE, "correlacao_taxabase.csv")
with open(p, "w", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print(f"\n[ok] {p}")
