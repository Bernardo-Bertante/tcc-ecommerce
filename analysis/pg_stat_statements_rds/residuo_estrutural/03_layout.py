#!/usr/bin/env python3
"""Layout fisico de `orders` ao fim de cada rodada + EXPLAIN direto + CLUSTER + conexoes.
Testa se a diferenca de blocos por linha do get_summary vem da ordem fisica do heap
(ctid) em relacao a created_at. Exploratorio, fora do desenho oficial.
Uso: 03_layout.py [dados] [resultados]
"""
import csv, re, sys, collections, statistics as st
from pathlib import Path

base = Path(sys.argv[1] if len(sys.argv) > 1 else "dados")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "resultados"); out.mkdir(exist_ok=True)
COND = {"springboot-noval": "SB-noval", "quarkus-jvm": "QJ"}

def layout(d):
    rows = list(csv.DictReader((d / "layout_orders.csv").open()))
    blk = [int(r["blk"]) for r in rows]
    upd = [r["updated_at"] != r["created_at"] for r in rows]
    n = len(rows)
    trans = [blk[i] != blk[i - 1] for i in range(1, n)]
    runs, cur = [], 1
    for t in trans:
        if t: runs.append(cur); cur = 1
        else: cur += 1
    runs.append(cur)
    def janela(w):
        return st.mean(len(set(blk[i:i + w])) for i in range(0, n - w, max(1, w // 2)))
    tu = [t for i, t in enumerate(trans) if upd[i] or upd[i + 1]]
    tn = [t for i, t in enumerate(trans) if not (upd[i] or upd[i + 1])]
    # distancia entre paginas consecutivas
    dist = [abs(blk[i] - blk[i - 1]) for i in range(1, n) if blk[i] != blk[i - 1]]
    pg = list(csv.DictReader((d / "paginas_orders.csv").open()))
    return dict(linhas=n, paginas=max(blk) + 1, frac_atualizadas=sum(upd) / n,
                transicoes_por_linha=sum(trans) / (n - 1), run_medio=st.mean(runs),
                pag_distintas_em_20=janela(20), pag_distintas_em_100=janela(100),
                trans_par_com_atualizada=(sum(tu) / len(tu) if tu else float("nan")),
                trans_par_sem_atualizada=(sum(tn) / len(tn) if tn else float("nan")),
                dist_mediana_paginas=st.median(dist) if dist else 0,
                versoes_antigas=sum(int(p["versao_antiga"]) for p in pg), dead=sum(int(p["dead"]) for p in pg),
                redirect=sum(int(p["redirect"]) for p in pg), unused=sum(int(p["unused"]) for p in pg),
                linhas_por_pagina=st.mean(int(p["normal"]) for p in pg))

def explains(path):
    txt = path.read_text() if path.exists() else ""
    res = {}
    for sec in re.split(r"^##### ", txt, flags=re.M)[1:]:
        nome = sec.split("\n", 1)[0].split(" (")[0].strip()
        blocos = re.split(r"(?=^(?:Aggregate|Limit|Sort|HashAggregate|GroupAggregate|Finalize|Seq Scan|Index)\S* .*cost=)", sec, flags=re.M)
        runs = []
        for b in re.split(r"\n(?=\w[^\n]*\(cost=)", sec):
            m_ex = re.search(r"Execution Time: ([\d.]+) ms", b)
            if not m_ex: continue
            scan = re.search(r"(Seq Scan|Index Only Scan|Index Scan|Bitmap Heap Scan)[^\n]*\n(?:[^\n]*\n)*?\s+Buffers: shared hit=(\d+)(?: read=(\d+))?", b)
            top = re.search(r"Buffers: shared hit=(\d+)(?: read=(\d+))?", b)
            nome_scan = re.search(r"(Seq Scan|Index Only Scan|Index Scan|Bitmap Heap Scan)", b)
            runs.append(dict(ms=float(m_ex.group(1)), scan=nome_scan.group(1) if nome_scan else "",
                             buf=int(top.group(1)) + int(top.group(2) or 0) if top else None))
        res[nome] = runs
    return res

rows_out = []; ex_out = []; conn_out = []
for d in sorted(base.glob("r*-*")):
    cond = COND.get(d.name.split("-", 1)[1])
    if not cond or not (d / "layout_orders.csv").exists(): continue
    L = layout(d); L.update(rodada=d.name, cond=cond); rows_out.append(L)
    for fase, f in (("antes", "explain_direto_antes.txt"), ("depois_cluster", "explain_direto_depois_cluster.txt")):
        for nome, runs in explains(d / f).items():
            for i, r in enumerate(runs):
                ex_out.append(dict(rodada=d.name, cond=cond, fase=fase, consulta=nome, exec=i + 1, **r))
    c = collections.defaultdict(lambda: collections.defaultdict(int))
    for ln in (d / "conexoes.tsv").read_text().splitlines():
        p = ln.split("\t")
        if len(p) == 3: c[p[0]][p[1]] += int(p[2])
    if c:
        tot = [sum(v.values()) for v in c.values()]; act = [v.get("active", 0) for v in c.values()]
        idt = [v.get("idle in transaction", 0) for v in c.values()]
        conn_out.append(dict(rodada=d.name, cond=cond, amostras=len(tot), backends_medio=st.mean(tot), backends_max=max(tot),
                             backends_min=min(tot), ativos_medio=st.mean(act), idle_in_tx_medio=st.mean(idt)))

def dump(nome, dados):
    if not dados: return
    with (out / nome).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dados[0])); w.writeheader(); w.writerows(dados)
dump("layout_por_rodada.csv", rows_out); dump("explain_direto.csv", ex_out); dump("conexoes_por_rodada.csv", conn_out)

print("== layout fisico de orders (ordem de created_at x ctid)")
cols = ["linhas", "paginas", "frac_atualizadas", "transicoes_por_linha", "run_medio", "pag_distintas_em_20", "pag_distintas_em_100",
        "trans_par_com_atualizada", "trans_par_sem_atualizada", "dist_mediana_paginas", "versoes_antigas", "dead", "redirect", "linhas_por_pagina"]
print(f"{'rodada':24}" + "".join(f"{c[:14]:>15}" for c in cols))
for r in rows_out: print(f"{r['rodada']:24}" + "".join(f"{r[c]:15.3f}" for c in cols))
print("\n== EXPLAIN direto (2a execucao de cada consulta): blocos e ms")
for r in ex_out:
    if r["exec"] == 2 or r["consulta"].startswith("forcado"):
        print(f"{r['rodada']:24} {r['fase']:15} {r['consulta'][:34]:35} exec{r['exec']} {r['scan']:16} blocos={r['buf']} ms={r['ms']}")
print("\n== conexoes"); [print(r) for r in conn_out]
