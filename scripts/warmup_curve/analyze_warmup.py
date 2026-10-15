#!/usr/bin/env python3
"""Lê warmup_curve/invocations_long.csv e produz:
  - warmup_curve_summary.md  (tabelas + respostas às duas perguntas)
  - warmup_curve.png         (duration vs nº de sequência, SB x Quarkus JVM)
  - band_stats_aggregate.csv / band_stats_by_round.csv já vêm do extrator;
    aqui só gero visão fina por seq + fração acumulada.
Não sobrescreve nada oficial.
"""
import csv
import os
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.expanduser("~/Programming/ecommerce-tcc/analysis/lambda/fase4/warmup_curve")
import json as _json
_wu = _json.load(open(os.path.join(OUT, "windows_used.json")))
_csv = os.path.join(OUT, "invocations_long.csv")
df = pd.read_csv(_csv if os.path.exists(_csv) else _csv + ".gz")
df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")

# Relabel scenario a partir dos timestamps das janelas k6 (o extrator usava
# +90s de padding no fim de L2, o que jogava ~90s do burst inicial de L3 para
# dentro de L2). Fronteira: fim de L2 (k6) + 15s -> tudo depois é L3.
def _relabel(row):
    w = _wu[f"{row.runtime}-r{row['round']}"]
    l2e = pd.Timestamp(w["l2"][1]) + pd.Timedelta(seconds=15)
    l3e = pd.Timestamp(w["l3"][1]) + pd.Timedelta(seconds=20)
    l2s = pd.Timestamp(w["l2"][0]) - pd.Timedelta(seconds=10)
    if l2s <= row.ts <= l2e:
        return "L2"
    if l2e < row.ts <= l3e:
        return "L3"
    return "gap"
df["scenario"] = df.apply(_relabel, axis=1)
df = df[df["scenario"].isin(["L2", "L3"])].copy()
df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")
df = df.dropna(subset=["duration_ms"])

RT = ["springboot", "quarkus-jvm"]
BAND_LABELS = ["1", "2-10", "11-100", "101-1000", "1001-5000", "5001+"]


def band(seq):
    if seq == 1: return "1"
    if seq <= 10: return "2-10"
    if seq <= 100: return "11-100"
    if seq <= 1000: return "101-1000"
    if seq <= 5000: return "1001-5000"
    return "5001+"


df["band"] = df["seq"].map(band)

lines = []
def p(s=""):
    lines.append(s)
    print(s)

p("# Seção 6.5 — Curva de aquecimento por ambiente de execução (Lambda L2/L3)")
p()
p("Fonte: linhas REPORT do CloudWatch Logs (retenção infinita, conta 776648109551,")
p("`--profile pessoal`), cenários L2 e L3, runtimes Spring Boot e Quarkus JVM,")
p("5 rodadas (05–06/jul e 16/jul/2026). Nº de sequência = ordem de invocação")
p("dentro do próprio `@logStream` (ambiente de execução), acumulada L2→L3")
p("(L3 reaproveita os ambientes já aquecidos por L2). Nada foi reexecutado;")
p("CSVs oficiais preservados.")
p()

# ---- cobertura ----
p("## Cobertura de extração (REPORT vs. esperado k6)")
p()
p("| runtime | rodada | cenário | REPORT | esperado | % |")
p("|---|---|---|---|---|---|")
wu = _wu
for rt in RT:
    for r in [1, 2, 3, 4, 5]:
        for sc in ["L2", "L3"]:
            n = len(df[(df.runtime == rt) & (df["round"] == r) & (df.scenario == sc)])
            exp = wu[f"{rt}-r{r}"][f"expected_{sc.lower()}"]
            p(f"| {rt} | {r} | {sc} | {n} | {exp} | {100*n/exp:.1f}% |")
p()

# ---- tabela agregada por faixa ----
p("## Tabela 1 — duration por faixa de sequência (agregado das 5 rodadas)")
p()
p("| cenário | faixa seq. | runtime | N obs | % das req. | dur. média (ms) | dur. mediana (ms) | p90 (ms) |")
p("|---|---|---|---|---|---|---|---|")
for sc in ["L2", "L3", "L2+L3"]:
    sub_all = df if sc == "L2+L3" else df[df.scenario == sc]
    for bl in BAND_LABELS:
        for rt in RT:
            s = sub_all[(sub_all.runtime == rt) & (sub_all.band == bl)]
            tot = len(sub_all[sub_all.runtime == rt])
            if len(s) == 0:
                p(f"| {sc} | {bl} | {rt} | 0 | 0.0% | — | — | — |")
                continue
            p(f"| {sc} | {bl} | {rt} | {len(s)} | {100*len(s)/tot:.1f}% | "
              f"{s.duration_ms.mean():.1f} | {s.duration_ms.median():.1f} | "
              f"{s.duration_ms.quantile(0.9):.1f} |")
    p("| | | | | | | | |")
p()

# ---- fração por faixa, por rodada ----
p("## Tabela 2 — fração das requisições por faixa de sequência (por rodada)")
p()
p("Combinado L2+L3. Cada célula = % das requisições daquela rodada/runtime cujo")
p("ambiente já tinha acumulado N invocações naquele ponto.")
p()
p("| runtime | rodada | seq=1 | 2-10 | 11-100 | 101-1k | 1k-5k | 5k+ | <100 (soma) |")
p("|---|---|---|---|---|---|---|---|---|")
for rt in RT:
    for r in [1, 2, 3, 4, 5]:
        s = df[(df.runtime == rt) & (df["round"] == r)]
        tot = len(s)
        fr = {bl: 100*len(s[s.band == bl])/tot for bl in BAND_LABELS}
        cold = fr["1"] + fr["2-10"] + fr["11-100"]
        p(f"| {rt} | {r} | {fr['1']:.1f}% | {fr['2-10']:.1f}% | {fr['11-100']:.1f}% | "
          f"{fr['101-1000']:.1f}% | {fr['1001-5000']:.1f}% | {fr['5001+']:.1f}% | **{cold:.1f}%** |")
p()

# ---- fração cold agregada (só L2) ----
p("## Tabela 3 — fração em ambiente pouco aquecido, só cenário L2")
p()
p("| runtime | rodada | % req. em env <100 inv | % req. em env <1000 inv |")
p("|---|---|---|---|")
for rt in RT:
    vals100, vals1k = [], []
    for r in [1, 2, 3, 4, 5]:
        s = df[(df.runtime == rt) & (df["round"] == r) & (df.scenario == "L2")]
        tot = len(s)
        c100 = 100*len(s[s.seq < 100])/tot
        c1k = 100*len(s[s.seq < 1000])/tot
        vals100.append(c100); vals1k.append(c1k)
        p(f"| {rt} | {r} | {c100:.1f}% | {c1k:.1f}% |")
    p(f"| {rt} | **média** | **{np.mean(vals100):.1f}%** | **{np.mean(vals1k):.1f}%** |")
p()

# ---- gap persistente em envs muito aquecidos ----
p("## Tabela 4 — duration em ambientes muito aquecidos (gap persistente?)")
p()
p("Mediana de duration por faixa alta de sequência, agregado 5 rodadas, L2+L3.")
p()
p("| faixa seq. | SB mediana | Quarkus JVM mediana | gap (QJ−SB) | gap % |")
p("|---|---|---|---|---|")
for bl in ["101-1000", "1001-5000", "5001+"]:
    sb = df[(df.runtime == "springboot") & (df.band == bl)].duration_ms
    qj = df[(df.runtime == "quarkus-jvm") & (df.band == bl)].duration_ms
    if len(sb) and len(qj):
        g = qj.median() - sb.median()
        p(f"| {bl} | {sb.median():.1f} | {qj.median():.1f} | {g:+.1f} ms | {100*g/sb.median():+.1f}% |")
    else:
        p(f"| {bl} | {'—' if not len(sb) else f'{sb.median():.1f}'} | "
          f"{'—' if not len(qj) else f'{qj.median():.1f}'} | — | — |")
p()

# ---- curva fina: mediana por bin log de seq ----
edges = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
p("## Tabela 5 — curva fina duration mediana vs. nº de sequência (L2+L3, agregado)")
p()
p("| seq (>=) | SB N | SB mediana | SB p90 | QJ N | QJ mediana | QJ p90 |")
p("|---|---|---|---|---|---|---|")
for i in range(len(edges) - 1):
    lo, hi = edges[i], edges[i+1]
    row = [f"{lo}"]
    for rt in RT:
        s = df[(df.runtime == rt) & (df.seq >= lo) & (df.seq < hi)].duration_ms
        if len(s):
            row += [str(len(s)), f"{s.median():.1f}", f"{s.quantile(0.9):.1f}"]
        else:
            row += ["0", "—", "—"]
    p("| " + " | ".join(row) + " |")
p()

# ---- Tabela 6 — decomposição composição vs. taxa (padronização) ----
p("## Tabela 6 — decomposição do gap: composição (aquecimento) vs. taxa (intrínseco)")
p()
p("Padronização direta: reponderando as invocações QUENTES (seq>1) do Quarkus JVM")
p("pela distribuição de nº de sequência do Spring Boot (bins log finos), isola-se")
p("quanto do gap vem da MISTURA de aquecimento (composição) e quanto vem da")
p("diferença de duration DENTRO de cada faixa (taxa / eficiência intrínseca).")
p()
fedges = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 20000]
df["_fbin"] = pd.cut(df["seq"], bins=fedges, right=False,
                     labels=[str(e) for e in fedges[:-1]])
p("| cenário | mean SB | mean QJ | gap mean | median SB | median QJ | gap median | "
  "gap QUENTE bruto | efeito composição | **gap intrínseco (taxa)** |")
p("|---|---|---|---|---|---|---|---|---|---|")
for lbl, mask in [("L2", df.scenario == "L2"), ("L3", df.scenario == "L3"),
                  ("L2+L3", df.scenario.isin(["L2", "L3"]))]:
    d = df[mask]
    sb, qj = d[d.runtime == "springboot"], d[d.runtime == "quarkus-jvm"]
    sbw, qjw = sb[sb.seq > 1], qj[qj.seq > 1]
    w = sbw["_fbin"].value_counts(normalize=True)
    qb = qjw.groupby("_fbin", observed=True).duration_ms.mean()
    sbb = sbw.groupby("_fbin", observed=True).duration_ms.mean()
    common = w.index.intersection(qb.index).intersection(sbb.index)
    wn = w[common] / w[common].sum()
    qj_std = float((wn * qb[common]).sum())
    sb_std = float((wn * sbb[common]).sum())
    raw_warm = qjw.duration_ms.mean() - sbw.duration_ms.mean()
    intrinsic = qj_std - sb_std
    comp = raw_warm - intrinsic
    p(f"| {lbl} | {sb.duration_ms.mean():.1f} | {qj.duration_ms.mean():.1f} | "
      f"{qj.duration_ms.mean()-sb.duration_ms.mean():+.1f} | "
      f"{sb.duration_ms.median():.1f} | {qj.duration_ms.median():.1f} | "
      f"{qj.duration_ms.median()-sb.duration_ms.median():+.1f} | "
      f"{raw_warm:+.2f} ms | {comp:+.2f} ms | **{intrinsic:+.2f} ms ({100*intrinsic/sb_std:+.1f}%)** |")
p()

# ---- Tabela 7 — ambiente mais aquecido por rodada ----
p("## Tabela 7 — ambiente mais aquecido de cada rodada (L2+L3)")
p()
p("`max_seq` = invocações acumuladas pelo @logStream mais ativo. `tail-2k` =")
p("mediana de duration nas últimas 2000 invocações desse ambiente (estado mais")
p("quente efetivamente atingido na rodada).")
p()
p("| runtime | rodada | nº ambientes | max_seq | tail-2k mediana (ms) |")
p("|---|---|---|---|---|")
for rt in RT:
    for r in [1, 2, 3, 4, 5]:
        s = df[(df.runtime == rt) & (df["round"] == r)]
        g = s.groupby("log_stream").size()
        top = g.idxmax()
        tail = s[s.log_stream == top].nlargest(2000, "seq").duration_ms.median()
        p(f"| {rt} | {r} | {len(g)} | {int(g.max())} | {tail:.1f} |")
p()

p("## Respostas")
p()
p("**1. A curva do Quarkus JVM converge para o Spring Boot conforme o ambiente")
p("esquenta?** Não. Ambos os runtimes atingem um platô: Spring Boot em ~16,4 ms")
p("por volta de seq≈1000, Quarkus JVM em ~20,5 ms por volta de seq≈700. Desse")
p("ponto em diante o gap (~3,5 ms, ~20 %) é estável — não diminui em ambientes")
p("com 5.000+ invocações (Tabela 4: gap de +3,7 ms / +23 % na faixa 5001+, ")
p("igual ou maior que na faixa 101-1000). O ambiente mais quente do Spring Boot")
p("chega a 10-16 mil invocações e continua em ~16 ms; o do Quarkus JVM não passa")
p("de ~9,5 mil e está plano em ~20 ms desde seq≈1000. Nada indica convergência")
p("se o Quarkus JVM recebesse mais tráfego. (Curiosidade: em seq 2-30 o Quarkus")
p("JVM é *mais rápido* que o Spring Boot; o Spring Boot ultrapassa por volta de")
p("seq≈40 e abre o gap definitivo até o platô.)")
p()
p("**2. A fração de requisições em ambiente pouco aquecido é maior no Quarkus JVM?**")
p("Só marginalmente, e não onde importa. Em env com <100 invocações as duas")
p("versões são praticamente iguais (L2: SB 3,2 % vs QJ 3,4 %). Em env com <1000")
p("invocações o Quarkus JVM é moderadamente maior (L2: 21,0 % vs 25,5 %). A")
p("diferença real de distribuição é outra: o Spring Boot CONCENTRA tráfego em")
p("poucos ambientes ultra-quentes (10-31 % das req. em seq 5000+), o Quarkus JVM")
p("espalha por ambientes medianamente quentes (8-15 % em seq 5000+). Mas como")
p("ambos já estão no platô desde seq≈1000, essa assimetria de concentração")
p("explica quase nada do gap: a padronização (Tabela 6) atribui apenas ~0,2 ms")
p("de ~3,4 ms de gap quente ao efeito de composição; ~3,2 ms (~17 %) é diferença")
p("intrínseca de duration por invocação, dentro da mesma faixa de aquecimento.")
p()
p("**Conclusão para a §6.5:** a inversão de ranking em L2/L3 em regime aquecido")
p("**não** é primariamente um artefato de aquecimento/distribuição de tráfego.")
p("Dentro de um mesmo ambiente de execução bem aquecido, a execução por")
p("invocação do Quarkus JVM é intrinsecamente ~17 % (~3,2 ms) mais lenta que a")
p("do Spring Boot, e esse gap é estável de ~1000 invocações em diante. A")
p("assimetria de concentração de tráfego notada na investigação anterior")
p("(min/mediana/máx) é real, mas contribui de forma desprezível para a diferença")
p("de mediana / média-quente. Ela infla a diferença de **média** via cold starts")
p("(execução de cold start do Quarkus JVM ~5,5 s vs ~2,7 s do Spring Boot), o")
p("que pesa em agregados baseados em média, não em mediana.")

with open(os.path.join(OUT, "warmup_curve_summary.md"), "w") as f:
    f.write("\n".join(lines) + "\n")

# ---- plot: curva de aquecimento (seq>=2, exclui cold start) ----
pedges = [2, 3, 4, 6, 9, 14, 21, 32, 48, 73, 110, 166, 251, 379, 573, 866,
          1309, 1979, 2991, 4520, 6833, 10329, 16000]


def curve(s, ymin_n=30):
    xs, med, p90 = [], [], []
    for i in range(len(pedges) - 1):
        lo, hi = pedges[i], pedges[i + 1]
        v = s[(s.seq >= lo) & (s.seq < hi)].duration_ms
        if len(v) >= ymin_n:
            xs.append((lo * hi) ** 0.5)
            med.append(v.median())
            p90.append(v.quantile(0.9))
    return xs, med, p90


fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
for ax, (lbl, ylim, scen) in zip(axes, [
        ("L2", (0, 120), "L2"),
        ("L2+L3", (0, 120), "both"),
        ("L2+L3 (zoom)", (12, 34), "both")]):
    d = df[df.scenario == "L2"] if scen == "L2" else df[df.scenario.isin(["L2", "L3"])]
    for rt, color in [("springboot", "#1f77b4"), ("quarkus-jvm", "#d62728")]:
        s = d[(d.runtime == rt) & (d.seq >= 2)]
        xs, med, p90 = curve(s)
        ax.plot(xs, med, "o-", color=color, label=rt, ms=4)
        if "zoom" not in lbl:
            ax.plot(xs, p90, "^--", color=color, alpha=0.35, ms=4)
        else:
            plateau = d[(d.runtime == rt) & (d.seq >= 2000)].duration_ms.median()
            ax.axhline(plateau, color=color, ls=":", alpha=0.6)
    ax.set_xscale("log")
    ax.set_ylim(*ylim)
    ax.set_xlabel("nº de invocação acumulada no ambiente (seq) — escala log")
    ax.set_title(f"{lbl} — seq ≥ 2 (exclui cold start)")
    ax.grid(True, which="both", alpha=0.3)
axes[0].set_ylabel("duration REPORT (ms)")
axes[0].legend(fontsize=8)
axes[2].legend(fontsize=8)
fig.suptitle("Curva de aquecimento por ambiente de execução — Lambda L2/L3 "
             "(linha cheia = mediana, tracejada = p90; agregado das 5 rodadas)",
             fontsize=10)
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(os.path.join(OUT, "warmup_curve.png"), dpi=130)
p(f"\nplot salvo em {OUT}/warmup_curve.png")
