"""
EXPLORACAO -- teste global (ANOVA / Kruskal-Wallis) entre as tres versoes.

Script TEMPORARIO e separado de fase5_analise_estatistica.py -- nao edita
nem grava em nenhum arquivo oficial da Fase 5 (fase5_testes_significancia*.csv
etc). So imprime no terminal e opcionalmente salva em
analysis/exploracao_teste_global.csv, para decidir se o teste global entra
oficialmente no TCC.

Reaproveita load_round_summaries / load_latency / load_l1_init_durations
de fase5_analise_estatistica.py (import direto, sem duplicar logica de
leitura de arquivo).

Nivel usado para o teste global (por que "por rodada" e nao "por observacao
individual"): a unidade experimental real do desenho e a rodada (N=5)
-- cada requisicao dentro da mesma rodada nao e uma replica independente,
entao um ANOVA/Kruskal sobre o pool de milhoes de requisicoes teria N
inflado artificialmente (pseudo-replicacao) e p-valores otimistas demais.
O nivel "por observacao individual" e calculado aqui so a titulo de
comparacao lado a lado, nao como resultado principal.

L1 e excecao: nao tem rodadas (design de N=9-11 invocacoes espacadas
dentro de uma sessao unica), entao as observacoes individuais SAO a
unidade experimental -- usadas diretamente como os "grupos", sem o
problema de pseudo-replicacao dos demais cenarios.
"""

import os

import numpy as np
import pandas as pd
from scipy import stats

from fase5_analise_estatistica import (
    BASE_DIR,
    RUNTIMES,
    SCENARIOS,
    load_latency,
    load_round_summaries,
    load_l1_init_durations,
)

ALPHA = 0.05
OFFICIAL_SIGNIFICANCIA_CSV = os.path.join(
    os.path.dirname(BASE_DIR), "analysis", "fase5", "fase5_testes_significancia_novo.csv"
)
OUTPUT_CSV = os.path.join(os.path.dirname(BASE_DIR), "analysis", "exploracao_teste_global.csv")

SCENARIOS_ROUND_LEVEL = ["f1", "f2", "f2s", "f3", "l2", "l3"]


def normality_and_variance(groups: list) -> dict:
    """Shapiro-Wilk por grupo (n pequeno, N=5 tipicamente) + Levene entre os
    tres grupos. shapiro_ok=True so se TODOS os grupos passarem (p>alpha);
    levene_ok=True se as variancias forem compativeis (p>alpha)."""
    shapiro_ps = []
    for g in groups:
        if len(g) < 3:
            shapiro_ps.append(np.nan)
            continue
        try:
            _, p = stats.shapiro(g)
        except Exception:
            p = np.nan
        shapiro_ps.append(p)

    shapiro_ok = all(p > ALPHA for p in shapiro_ps if not np.isnan(p)) and not all(
        np.isnan(p) for p in shapiro_ps
    )

    try:
        _, levene_p = stats.levene(*groups)
    except Exception:
        levene_p = np.nan
    levene_ok = (not np.isnan(levene_p)) and levene_p > ALPHA

    return {
        "shapiro_p_per_group": shapiro_ps,
        "shapiro_ok": shapiro_ok,
        "levene_p": levene_p,
        "levene_ok": levene_ok,
    }


def global_tests(groups: list) -> dict:
    f_stat, anova_p = stats.f_oneway(*groups)
    h_stat, kruskal_p = stats.kruskal(*groups)
    return {"anova_F": f_stat, "anova_p": anova_p, "kruskal_H": h_stat, "kruskal_p": kruskal_p}


def analyze_round_level_scenario(scenario: str) -> dict:
    round_groups = []
    individual_groups = []
    ns = []
    for rt in RUNTIMES:
        rdf = load_round_summaries(scenario, rt)
        round_groups.append(rdf["avg_ms"].dropna().to_numpy())
        ns.append(len(rdf))
        individual_groups.append(load_latency(scenario, rt))

    round_res = global_tests(round_groups)
    norm_var = normality_and_variance(round_groups)
    indiv_res = global_tests(individual_groups)

    metodo_indicado = "ANOVA" if (norm_var["shapiro_ok"] and norm_var["levene_ok"]) else "Kruskal-Wallis"

    return {
        "cenario": scenario,
        "n_por_grupo_rodada": "/".join(str(n) for n in ns),
        "anova_F": round_res["anova_F"],
        "anova_p": round_res["anova_p"],
        "kruskal_H": round_res["kruskal_H"],
        "kruskal_p": round_res["kruskal_p"],
        "shapiro_ok": norm_var["shapiro_ok"],
        "shapiro_p_per_group": norm_var["shapiro_p_per_group"],
        "levene_ok": norm_var["levene_ok"],
        "levene_p": norm_var["levene_p"],
        "metodo_indicado": metodo_indicado,
        "anova_p_individual": indiv_res["anova_p"],
        "kruskal_p_individual": indiv_res["kruskal_p"],
        "anova_F_individual": indiv_res["anova_F"],
        "kruskal_H_individual": indiv_res["kruskal_H"],
    }


def analyze_l1() -> dict:
    init_durations = load_l1_init_durations()
    groups = [init_durations.get(rt, np.array([])) for rt in RUNTIMES]
    ns = [len(g) for g in groups]

    res = global_tests(groups)
    norm_var = normality_and_variance(groups)
    metodo_indicado = "ANOVA" if (norm_var["shapiro_ok"] and norm_var["levene_ok"]) else "Kruskal-Wallis"

    # L1 nao tem nivel "por rodada" separado do nivel "por observacao
    # individual" -- as observacoes individuais SAO a unidade experimental,
    # entao as colunas "individual" recebem o mesmo resultado (nao ha
    # segundo nivel a calcular).
    return {
        "cenario": "l1",
        "n_por_grupo_rodada": "/".join(str(n) for n in ns) + " (obs. individuais, sem rodadas)",
        "anova_F": res["anova_F"],
        "anova_p": res["anova_p"],
        "kruskal_H": res["kruskal_H"],
        "kruskal_p": res["kruskal_p"],
        "shapiro_ok": norm_var["shapiro_ok"],
        "shapiro_p_per_group": norm_var["shapiro_p_per_group"],
        "levene_ok": norm_var["levene_ok"],
        "levene_p": norm_var["levene_p"],
        "metodo_indicado": metodo_indicado,
        "anova_p_individual": res["anova_p"],
        "kruskal_p_individual": res["kruskal_p"],
        "anova_F_individual": res["anova_F"],
        "kruskal_H_individual": res["kruskal_H"],
    }


def load_official_pairwise_flags(scenario: str) -> dict:
    """Le o CSV oficial de comparacoes par a par (so leitura, nunca escreve
    nele) e retorna quais pares deram significativo (MW ou t-test) para o
    cenario, para cruzar com o resultado do teste global."""
    if not os.path.exists(OFFICIAL_SIGNIFICANCIA_CSV):
        return {}
    df = pd.read_csv(OFFICIAL_SIGNIFICANCIA_CSV)
    sub = df[df["cenario"] == scenario]
    out = {}
    for _, row in sub.iterrows():
        out[row["comparacao"]] = {
            "significativo_mw": bool(row["significativo_mw"]),
            "significativo_t": bool(row["significativo_t"]),
        }
    return out


def main():
    rows = []
    for scenario in SCENARIOS_ROUND_LEVEL:
        print(f"\n=== Explorando teste global: {scenario} ===")
        rows.append(analyze_round_level_scenario(scenario))

    print("\n=== Explorando teste global: l1 ===")
    rows.append(analyze_l1())

    df = pd.DataFrame(rows)

    # --- tabela resumida pedida ---
    resumo_cols = [
        "cenario", "n_por_grupo_rodada", "anova_F", "anova_p",
        "kruskal_H", "kruskal_p", "shapiro_ok", "levene_ok",
        "metodo_indicado", "anova_p_individual", "kruskal_p_individual",
    ]
    resumo = df[resumo_cols].copy()
    for col in ["anova_F", "anova_p", "kruskal_H", "kruskal_p", "anova_p_individual", "kruskal_p_individual"]:
        resumo[col] = resumo[col].map(lambda v: f"{v:.6g}")

    print("\n\n=== TABELA RESUMO -- teste global por cenario ===\n")
    print(resumo.to_string(index=False))

    # --- divergencia entre nivel por-rodada (correto) e por-observacao (pseudo-replicado) ---
    print("\n\n=== Divergencia de significancia: por rodada (N=5, correto) vs por observacao (pseudo-replicado) ===\n")
    for _, row in df.iterrows():
        sig_round = row["kruskal_p"] < ALPHA if row["metodo_indicado"] == "Kruskal-Wallis" else row["anova_p"] < ALPHA
        p_round = row["kruskal_p"] if row["metodo_indicado"] == "Kruskal-Wallis" else row["anova_p"]
        sig_indiv = row["kruskal_p_individual"] < ALPHA if row["metodo_indicado"] == "Kruskal-Wallis" else row["anova_p_individual"] < ALPHA
        p_indiv = row["kruskal_p_individual"] if row["metodo_indicado"] == "Kruskal-Wallis" else row["anova_p_individual"]
        status = "BATE" if sig_round == sig_indiv else "DIVERGE"
        print(f"  {row['cenario']:4s} [{row['metodo_indicado']:14s}]  "
              f"p(rodada)={p_round:.4g} sig={sig_round}  |  "
              f"p(individual)={p_indiv:.4g} sig={sig_indiv}  ->  {status}")

    # --- cruzamento com o CSV oficial de comparacoes par a par (so leitura) ---
    print("\n\n=== Cenarios em que o teste global (por rodada) NAO e significativo mas algum par oficial E ===\n")
    preocupantes = []
    for _, row in df.iterrows():
        global_sig = (row["kruskal_p"] < ALPHA) if row["metodo_indicado"] == "Kruskal-Wallis" else (row["anova_p"] < ALPHA)
        pares = load_official_pairwise_flags(row["cenario"])
        pares_sig = [
            comp for comp, flags in pares.items()
            if flags["significativo_mw"] or flags["significativo_t"]
        ]
        if not global_sig and pares_sig:
            preocupantes.append(row["cenario"])
            print(f"  [ATENCAO] {row['cenario']}: teste global NAO significativo "
                  f"({row['metodo_indicado']}, p={row['kruskal_p'] if row['metodo_indicado']=='Kruskal-Wallis' else row['anova_p']:.4g}) "
                  f"mas pares significativos no CSV oficial: {pares_sig}")
        else:
            marca = "sig." if global_sig else "NAO sig."
            print(f"  {row['cenario']}: teste global {marca} -- consistente com pares oficiais "
                  f"({'nenhum par sig.' if not pares_sig else pares_sig})")

    if not preocupantes:
        print("\n  Nenhum cenario com essa divergencia encontrado.")
    else:
        print(f"\n  Cenarios com divergencia preocupante: {preocupantes}")

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n[ok] output completo da EXPLORACAO salvo em {OUTPUT_CSV} "
          f"(arquivo separado -- nao mexe em nada da Fase 5 oficial)")


if __name__ == "__main__":
    main()
