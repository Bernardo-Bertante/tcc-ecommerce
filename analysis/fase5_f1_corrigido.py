"""
Roda EXATAMENTE o pipeline estatístico da Fase 5 (fase5_analise_estatistica.py),
sem alterar nenhuma lógica, apontando o cenário F1 para a re-coleta corrigida
(analysis/fargate/fase3-f1-rerun/, F1_RATE=48) em vez da coleta original com bug
(analysis/fargate/fase3/, que rodou a 30 iter/s por engano).

Reutiliza as funções do módulo original via import — só troca o diretório de F1 e
restringe a saída ao cenário F1. NÃO toca nos CSVs *_novo.csv.

Saída (analysis/fase5/):
    fase5_f1_corrigido_estatistica.csv     <- mesmo formato de fase5_estatistica_descritiva_novo.csv
    fase5_f1_corrigido_significancia.csv   <- mesmo formato de fase5_testes_significancia_novo.csv
    fase5_f1_corrigido_teste_global.csv    <- mesmo formato de fase5_teste_global_novo.csv
"""
import os
import numpy as np
import pandas as pd

import fase5_analise_estatistica as f5

OUT = f5.OUTPUT_DIR

# --- única mudança: F1 aponta para a re-coleta corrigida -------------------
f5.SCENARIOS["f1"]["dir"] = "fargate/fase3-f1-rerun"

SCEN = "f1"


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- descritiva + significância (mesma lógica de analyze_scenario) ----
    res = f5.analyze_scenario(SCEN)

    desc_rows = []
    for rt, d in res["descriptive"].items():
        if not d:
            continue
        row = {"cenario": SCEN, "runtime": rt}
        row.update(d)
        row.update(res["stability"][rt])
        desc_rows.append(row)
    desc_df = pd.DataFrame(desc_rows)
    desc_df.to_csv(os.path.join(OUT, "fase5_f1_corrigido_estatistica.csv"), index=False)

    comp_rows = []
    for c in res["comparisons"]:
        row = {"cenario": SCEN}
        row.update(c)
        comp_rows.append(row)
    comp_df = pd.DataFrame(comp_rows)
    comp_df = f5.apply_holm_correction(comp_df)   # família = as 3 comparações de F1 (idêntico ao pipeline)
    comp_df.to_csv(os.path.join(OUT, "fase5_f1_corrigido_significancia.csv"), index=False)

    # ---- teste global (mesma lógica de analyze_global_tests, só F1) -------
    groups, ns = [], []
    for rt in f5.RUNTIMES:
        rdf = f5.load_round_summaries(SCEN, rt)
        g = rdf["avg_ms"].dropna().to_numpy()
        groups.append(g)
        ns.append(len(g))
    test_res = f5.global_test_for_groups(groups)
    diag = f5.normality_and_variance(groups)
    metodo = "ANOVA" if (diag["shapiro_ok"] and diag["levene_ok"]) else "Kruskal-Wallis"
    global_df = pd.DataFrame([{
        "cenario": SCEN,
        "n_por_grupo": "/".join(str(n) for n in ns),
        "nivel": "rodada",
        "anova_f": test_res["anova_f"],
        "anova_p": test_res["anova_p"],
        "kruskal_h": test_res["kruskal_h"],
        "kruskal_p": test_res["kruskal_p"],
        "shapiro_ok": diag["shapiro_ok"],
        "levene_ok": diag["levene_ok"],
        "metodo_indicado": metodo,
    }])
    global_df.to_csv(os.path.join(OUT, "fase5_f1_corrigido_teste_global.csv"), index=False)

    # ---- comparação lado a lado com as linhas F1 antigas (buggy) ----------
    print("\n" + "=" * 78)
    print("COMPARAÇÃO  F1 antigo (30 iter/s, com bug)  vs  F1 corrigido (48 iter/s)")
    print("=" * 78)

    def old_rows(fname):
        p = os.path.join(OUT, fname)
        if not os.path.exists(p):
            return None
        df = pd.read_csv(p)
        return df[df["cenario"] == "f1"]

    for label, newdf, oldfname in [
        ("DESCRITIVA", desc_df, "fase5_estatistica_descritiva_novo.csv"),
        ("SIGNIFICÂNCIA", comp_df, "fase5_testes_significancia_novo.csv"),
        ("TESTE GLOBAL", global_df, "fase5_teste_global_novo.csv"),
    ]:
        print(f"\n--- {label} ---")
        old = old_rows(oldfname)
        print("[ANTIGO]"); print(old.to_string(index=False) if old is not None else "  (não encontrado)")
        print("[NOVO]"); print(newdf.to_string(index=False))

    print("\n[ok] arquivos gerados em", OUT)
    for f in ("fase5_f1_corrigido_estatistica.csv",
              "fase5_f1_corrigido_significancia.csv",
              "fase5_f1_corrigido_teste_global.csv"):
        print("  ", f)


if __name__ == "__main__":
    main()
