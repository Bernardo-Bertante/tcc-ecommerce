#!/usr/bin/env python3
"""Recalculos estatisticos da versao reduzida do TCC (fase de reducao, nov/2026).

Uso:
    python3 reducao_estatistica.py <pasta analysis do repositorio> [pasta de saida]

Exemplo, a partir da raiz do repositorio:
    python3 analysis/reducao/reducao_estatistica.py analysis saida_reducao

Os CSVs gerados devem ser iguais aos versionados em analysis/reducao/.

Le apenas arquivos versionados no repositorio tcc-ecommerce (commit 89ef019):
    F1:    fargate/fase3-f1-rerun/f1-<versao>-r<1..5>-{summary,latency}.json
    F2:    fargate/fase3/f2-<versao>-r<1..5>-{summary,latency}.json      (coleta de julho)
    F3:    fargate/fase3-f3-rerun/f3-<versao>-r<1..5>-{summary,latency}.json (recoleta de setembro)
    L2/L3: lambda/fase4/<cen>-<versao>-r<1..5>-summary.json
           (agregado de L2/L3 lido de fase5/fase5_estatistica_descritiva_novo.csv,
            porque o NDJSON bruto das rodadas 1-3 nao esta no repositorio)
    L1:    lambda/l1/l1_init_durations.json e lambda/l1/l1_duration_postinit.csv
    H1b:   fargate/h1b/h1b_startup_times.json

Gera, na pasta de saida:
    reducao_por_rodada.csv   media, mediana e p95 de cada rodada (valores do k6)
    reducao_cenarios.csv     por cenario e versao: media das 5 rodadas, desvio entre
                             rodadas, IC 95% e CV, para media, mediana e p95; e as
                             mesmas tres medidas sobre todas as requisicoes juntas
                             (agregado), para comparacao com as tabelas atuais
    reducao_welch.csv        t de Welch por par de versoes, sobre as 5 rodadas, com
                             IC 95% da diferenca e razao entre as medias
    reducao_l1_h1b.csv       L1 (inicializacao, primeira execucao, tempo faturado,
                             memoria) e H1b: media, desvio, IC 95%, min, max
    reducao_l1_h1b_welch.csv t de Welch por par de versoes sobre as observacoes
                             individuais do L1 e do H1b

Convencoes:
    - desvio padrao amostral (ddof=1);
    - IC 95% da media: media +/- t(0,975; n-1) * dp / sqrt(n);
    - Welch: dp de cada grupo separado; gl de Welch-Satterthwaite;
      IC 95% da diferenca A - B: dif +/- t(0,975; gl) * ep;
    - nenhuma correcao para comparacoes multiplas.
"""

import csv
import json
import math
import os
import sys
import warnings

import numpy as np
from scipy import stats

VERSOES = ["springboot", "quarkus-jvm", "quarkus-native"]
PARES = [("springboot", "quarkus-jvm"), ("springboot", "quarkus-native"), ("quarkus-jvm", "quarkus-native")]
RODADAS = [1, 2, 3, 4, 5]

CENARIOS = {
    # cenario: (pasta, prefixo, agregado a partir de)
    "F1": ("fargate/fase3-f1-rerun", "f1", "latency"),
    "F2": ("fargate/fase3", "f2", "latency"),
    "F3": ("fargate/fase3-f3-rerun", "f3", "latency"),
    "L2": ("lambda/fase4", "l2", "csv"),
    "L3": ("lambda/fase4", "l3", "csv"),
}
MEDIDAS = [("media", "avg"), ("mediana", "med"), ("p95", "p(95)")]


def ic_media(x):
    x = np.asarray(x, dtype=float)
    n = len(x)
    m = x.mean()
    s = x.std(ddof=1) if n > 1 else float("nan")
    meia = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n) if n > 1 else float("nan")
    return n, m, s, m - meia, m + meia


def welch(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1) / na, b.var(ddof=1) / nb
    ep = math.sqrt(va + vb)
    dif = a.mean() - b.mean()
    gl = (va + vb) ** 2 / ((va ** 2) / (na - 1) + (vb ** 2) / (nb - 1))
    t = dif / ep
    p = 2 * stats.t.sf(abs(t), gl)
    meia = stats.t.ppf(0.975, gl) * ep
    # conferencia com a implementacao do scipy. O aviso de "precision loss" aparece
    # quando um grupo tem todos os valores iguais (memoria do Native no L1: 68 MB em
    # todas as invocacoes); o calculo manual acima nao depende dele.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        t_sp, p_sp = stats.ttest_ind(a, b, equal_var=False)
    assert abs(t - t_sp) < 1e-9 * max(1, abs(t)) and abs(p - p_sp) < 1e-12 + 1e-9 * p_sp
    return dif, dif - meia, dif + meia, t, gl, p


def fmt(v):
    # 8 algarismos significativos: preserva valores de p muito pequenos
    if isinstance(v, (float, np.floating)):
        v = float(v)
        if math.isnan(v):
            return ""
        return "%.8g" % v
    return v


def escrever(caminho, cabecalho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        for l in linhas:
            w.writerow([fmt(v) for v in l])
    print("gravado:", caminho)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    base = os.path.expanduser(sys.argv[1])
    saida = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else "saida_reducao"
    os.makedirs(saida, exist_ok=True)

    # ---------------------------------------------------------------- por rodada
    por_rodada = {}  # (cen, versao) -> {medida: [5 valores]}
    linhas_rodada = []
    for cen, (pasta, pref, _) in CENARIOS.items():
        for v in VERSOES:
            vals = {m: [] for m, _ in MEDIDAS}
            for r in RODADAS:
                p = os.path.join(base, pasta, f"{pref}-{v}-r{r}-summary.json")
                met = json.load(open(p))["metrics"]
                d = met["http_req_duration"]
                n = met["http_reqs"]["count"]
                linhas_rodada.append([cen, v, r, n, d["avg"], d["med"], d["p(95)"], os.path.relpath(p, base)])
                for m, chave in MEDIDAS:
                    vals[m].append(d[chave])
            por_rodada[(cen, v)] = vals
    escrever(os.path.join(saida, "reducao_por_rodada.csv"),
             ["cenario", "versao", "rodada", "n_requisicoes", "media_ms", "mediana_ms", "p95_ms", "fonte"],
             linhas_rodada)

    # ---------------------------------------------------------------- agregado
    canon = {}
    with open(os.path.join(base, "fase5/fase5_estatistica_descritiva_novo.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            canon[(row["cenario"].upper(), row["runtime"])] = row

    agregado = {}
    for cen, (pasta, pref, origem) in CENARIOS.items():
        for v in VERSOES:
            if origem == "latency":
                arr = np.concatenate([
                    np.asarray(json.load(open(os.path.join(base, pasta, f"{pref}-{v}-r{r}-latency.json"))), dtype=float)
                    for r in RODADAS])
                agregado[(cen, v)] = (len(arr), arr.mean(), float(np.median(arr)), float(np.percentile(arr, 95)),
                                      "latency.json das 5 rodadas")
            else:
                row = canon[(cen, v)]
                agregado[(cen, v)] = (int(row["n"]), float(row["mean"]), float(row["median"]), float(row["p95"]),
                                      "fase5_estatistica_descritiva_novo.csv")

    linhas_cen = []
    for cen in CENARIOS:
        for v in VERSOES:
            l = [cen, v]
            for m, _ in MEDIDAS:
                n, media, dp, lo, hi = ic_media(por_rodada[(cen, v)][m])
                l += [media, dp, lo, hi, dp / media]
            na, ma, med_a, p95_a, fonte = agregado[(cen, v)]
            l += [na, ma, med_a, p95_a, fonte]
            linhas_cen.append(l)
    cab = ["cenario", "versao"]
    for m, _ in MEDIDAS:
        cab += [f"{m}_rodadas_ms", f"{m}_dp_entre_rodadas_ms", f"{m}_ic95_inf_ms", f"{m}_ic95_sup_ms", f"{m}_cv_entre_rodadas"]
    cab += ["agregado_n", "agregado_media_ms", "agregado_mediana_ms", "agregado_p95_ms", "agregado_fonte"]
    escrever(os.path.join(saida, "reducao_cenarios.csv"), cab, linhas_cen)

    # ---------------------------------------------------------------- Welch por rodada
    linhas_w = []
    for cen in CENARIOS:
        for m, _ in MEDIDAS:
            for a, b in PARES:
                xa, xb = por_rodada[(cen, a)][m], por_rodada[(cen, b)][m]
                dif, lo, hi, t, gl, p = welch(xa, xb)
                linhas_w.append([cen, m, a, b, np.mean(xa), np.mean(xb), np.mean(xa) / np.mean(xb),
                                 dif, lo, hi, t, gl, p, "sim" if p < 0.05 else "nao"])
    escrever(os.path.join(saida, "reducao_welch.csv"),
             ["cenario", "medida", "versao_a", "versao_b", "a_ms", "b_ms", "razao_a_b", "dif_a_menos_b_ms",
              "dif_ic95_inf_ms", "dif_ic95_sup_ms", "t", "gl", "p", "p_menor_0_05"],
             linhas_w)

    # ---------------------------------------------------------------- L1 e H1b
    obs = {}  # (medida, versao) -> lista
    init_json = json.load(open(os.path.join(base, "lambda/l1/l1_init_durations.json")))
    for v in VERSOES:
        obs[("L1 inicializacao (Init Duration, l1_init_durations.json)", v)] = init_json[v]["init_duration_ms"]
    with open(os.path.join(base, "lambda/l1/l1_duration_postinit.csv"), encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["excluded_outlier"] == "False"]
    for v in VERSOES:
        rv = [r for r in rows if r["runtime"] == v]
        ini = [float(r["init_duration_ms"]) for r in rv]
        dur = [float(r["duration_ms"]) for r in rv]
        obs[("L1 inicializacao (Init Duration, l1_duration_postinit.csv)", v)] = ini
        obs[("L1 primeira execucao (Duration)", v)] = dur
        obs[("L1 inicializacao + primeira execucao", v)] = [a + b for a, b in zip(ini, dur)]
        obs[("L1 Billed Duration (campo do CloudWatch)", v)] = [float(r["billed_duration_ms"]) for r in rv]
        obs[("L1 memoria maxima (MB)", v)] = [float(r["max_memory_used_mb"]) for r in rv]
    h1b = json.load(open(os.path.join(base, "fargate/h1b/h1b_startup_times.json")))
    for v in VERSOES:
        obs[("H1b inicializacao do conteiner (s)", v)] = h1b[v]["startup_seconds"]

    medidas_l1 = []
    for (med, v) in obs:
        if med not in medidas_l1:
            medidas_l1.append(med)
    linhas_l1 = []
    for med in medidas_l1:
        for v in VERSOES:
            x = obs[(med, v)]
            n, media, dp, lo, hi = ic_media(x)
            linhas_l1.append([med, v, n, media, dp, lo, hi, min(x), max(x), float(np.median(x))])
    escrever(os.path.join(saida, "reducao_l1_h1b.csv"),
             ["medida", "versao", "n", "media", "dp", "ic95_inf", "ic95_sup", "min", "max", "mediana"],
             linhas_l1)

    linhas_l1w = []
    for med in medidas_l1:
        for a, b in PARES:
            xa, xb = obs[(med, a)], obs[(med, b)]
            dif, lo, hi, t, gl, p = welch(xa, xb)
            disj = "sim" if (min(xa) > max(xb) or min(xb) > max(xa)) else "nao"
            linhas_l1w.append([med, a, b, np.mean(xa), np.mean(xb), np.mean(xa) / np.mean(xb),
                               dif, lo, hi, t, gl, p, disj])
    escrever(os.path.join(saida, "reducao_l1_h1b_welch.csv"),
             ["medida", "versao_a", "versao_b", "a", "b", "razao_a_b", "dif_a_menos_b", "dif_ic95_inf",
              "dif_ic95_sup", "t", "gl", "p", "faixas_disjuntas"],
             linhas_l1w)


if __name__ == "__main__":
    main()
