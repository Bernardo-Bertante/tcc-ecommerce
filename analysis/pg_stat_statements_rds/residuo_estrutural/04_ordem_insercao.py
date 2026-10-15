#!/usr/bin/env python3
"""Separa as causas da intercalacao de paginas em `orders` (so linhas NUNCA atualizadas, cujo ctid
e o do INSERT original): (a) insercoes concorrentes em paginas-alvo diferentes -> intercala mesmo na
ordem de xmin; (b) created_at fora da ordem de insercao -> contiguo por xmin, intercalado por created_at.
Tambem estima quantas paginas recebem insercoes ao mesmo tempo. Exploratorio."""
import csv, sys, statistics as st, collections
from pathlib import Path
base = Path(sys.argv[1] if len(sys.argv) > 1 else "dados")
print(f"{'rodada':22} {'n':>6} {'trans/lin por created_at':>25} {'trans/lin por xmin':>19} {'pags abertas (med)':>19} {'inversoes created_at x xmin':>28}")
for d in sorted(base.glob("r*-*")):
    f = d / "layout_orders.csv"
    if not f.exists(): continue
    R = [r for r in csv.DictReader(f.open()) if r["updated_at"] == r["created_at"]]
    for r in R: r["blk"] = int(r["blk"]); r["xmin"] = int(r["xmin"])
    def trans(rows): return sum(rows[i]["blk"] != rows[i-1]["blk"] for i in range(1, len(rows))) / (len(rows) - 1)
    por_ct = R  # arquivo ja vem ordenado por created_at, id
    por_x = sorted(R, key=lambda r: r["xmin"])
    inv = sum(por_ct[i]["xmin"] < por_ct[i-1]["xmin"] for i in range(1, len(por_ct))) / (len(por_ct) - 1)
    # paginas "abertas": intervalo [min,max] de xmin de insercao por pagina; quantas contem cada xmin
    span = collections.defaultdict(lambda: [10**18, 0])
    for r in R:
        s = span[r["blk"]]; s[0] = min(s[0], r["xmin"]); s[1] = max(s[1], r["xmin"])
    iv = sorted(span.values())
    amostra = por_x[::max(1, len(por_x)//500)]
    abertas = [sum(a <= r["xmin"] <= b for a, b in iv) for r in amostra]
    print(f"{d.name:22} {len(R):6d} {trans(por_ct):25.3f} {trans(por_x):19.3f} {st.median(abertas):19.1f} {inv:28.3f}")
