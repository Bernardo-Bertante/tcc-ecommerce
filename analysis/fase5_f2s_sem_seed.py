"""
F2-S sem as 120 amostras de semeadura do setup() do k6 (reprocessamento).

Reaproveita, por import, as funcoes do metodo oficial de
fase5_analise_estatistica.py (descriptive_stats, stability_metrics,
pairwise_comparison, apply_holm_correction, global_test_for_groups,
normality_and_variance) -- o metodo nao e reescrito; so muda o carregamento
dos dados (descarta as 120 primeiras amostras de cada *-latency.json) e a
media por rodada do teste global (recalculada sem o seed, em vez de ler
http_req_duration.avg do summary.json, que inclui o seed).

Nao sobrescreve nenhum arquivo oficial: todas as saidas levam _sem_seed.
Uso: python3 analysis/fase5_f2s_sem_seed.py [--sanity]
  --sanity: roda com SEED=0 e confere contra os CSVs oficiais (valida o pipeline).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fase5_analise_estatistica as f5

BASE = f5.BASE_DIR
DIR = os.path.join(BASE, "fargate/fase3b")
OUT = f5.OUTPUT_DIR
N_SEED = 120


def load_round(rt, r, n_seed):
    p = os.path.join(DIR, f"f2s-{rt}-r{r}")
    lat = np.array(json.load(open(p + "-latency.json")), dtype=float)
    sm = json.load(open(p + "-summary.json"))
    m = sm["metrics"]
    # conferencias: n == http_reqs e o grupo setup do summary tem 120 passes
    assert len(lat) == m["http_reqs"]["count"], p
    assert len(sm["setup_data"]["readOrders"]) == N_SEED, p
    setup_passes = sm["root_group"]["groups"]["setup"]["checks"]["setup seed order: status 201"]["passes"]
    assert setup_passes == N_SEED, p
    assert m["http_reqs"]["count"] - m["iterations"]["count"] == N_SEED, p
    return lat[n_seed:], m


def build(n_seed):
    lat, rdfs = {}, {}
    for rt in f5.RUNTIMES:
        arrs, rows = [], []
        for r in f5.ROUNDS:
            a, m = load_round(rt, r, n_seed)
            arrs.append(a)
            dur = m["http_reqs"]["count"] / m["http_reqs"]["rate"]
            rows.append({"round": r, "avg_ms": a.mean(), "p95_ms": np.percentile(a, 95),
                         "http_reqs": len(a), "failed_pct": 0.0,
                         "test_duration_sec": dur, "throughput_rps": len(a) / dur})
        lat[rt] = np.concatenate(arrs)
        rdfs[rt] = pd.DataFrame(rows)
    return lat, rdfs


def compute(n_seed):
    lat, rdfs = build(n_seed)
    desc_rows = []
    for rt in f5.RUNTIMES:
        row = {"cenario": "f2s", "runtime": rt}
        row.update(f5.descriptive_stats(lat[rt]))
        row.update(f5.stability_metrics(rdfs[rt], lat[rt]))
        desc_rows.append(row)
    desc = pd.DataFrame(desc_rows)

    comp_rows = []
    for a, b in f5.PAIRS:
        row = {"cenario": "f2s"}
        row.update(f5.pairwise_comparison(lat[a], lat[b], a, b))
        comp_rows.append(row)
    comp = f5.apply_holm_correction(pd.DataFrame(comp_rows))

    groups = [rdfs[rt]["avg_ms"].to_numpy() for rt in f5.RUNTIMES]
    tr = f5.global_test_for_groups(groups)
    dg = f5.normality_and_variance(groups)
    glob = pd.DataFrame([{
        "cenario": "f2s", "n_por_grupo": "/".join(str(len(g)) for g in groups), "nivel": "rodada",
        "anova_f": tr["anova_f"], "anova_p": tr["anova_p"],
        "kruskal_h": tr["kruskal_h"], "kruskal_p": tr["kruskal_p"],
        "shapiro_ok": dg["shapiro_ok"], "levene_ok": dg["levene_ok"],
        "metodo_indicado": "ANOVA" if (dg["shapiro_ok"] and dg["levene_ok"]) else "Kruskal-Wallis",
    }])
    return desc, comp, glob, lat, rdfs


def sanity():
    """SEED=0 deve reproduzir os CSVs oficiais (valida o pipeline)."""
    desc, comp, glob, _, _ = compute(0)
    o_d = pd.read_csv(os.path.join(OUT, "fase5_estatistica_descritiva_novo.csv")).query("cenario=='f2s'").reset_index(drop=True)
    o_c = pd.read_csv(os.path.join(OUT, "fase5_testes_significancia.csv")).query("cenario=='f2s'").reset_index(drop=True)
    o_g = pd.read_csv(os.path.join(OUT, "fase5_teste_global.csv")).query("cenario=='f2s'").reset_index(drop=True)
    for name, new, old in (("descritiva", desc, o_d), ("significancia", comp, o_c), ("global", glob, o_g)):
        cols = [c for c in old.columns if c in new.columns and pd.api.types.is_numeric_dtype(old[c])]
        diff = max(float(np.nanmax(np.abs(new[c].astype(float).to_numpy() - old[c].astype(float).to_numpy())
                                   / np.maximum(np.abs(old[c].astype(float).to_numpy()), 1e-300))) for c in cols)
        print(f"[sanity] {name}: max diff relativa vs oficial = {diff:.2e}")


if __name__ == "__main__":
    if "--sanity" in sys.argv:
        sanity()
        sys.exit()
    desc, comp, glob, _, _ = compute(N_SEED)
    desc.to_csv(os.path.join(OUT, "fase5_estatistica_descritiva_f2s_sem_seed.csv"), index=False)
    comp.to_csv(os.path.join(OUT, "fase5_testes_significancia_f2s_sem_seed.csv"), index=False)
    glob.to_csv(os.path.join(OUT, "fase5_teste_global_f2s_sem_seed.csv"), index=False)
    print(desc.to_string()); print(comp.to_string()); print(glob.to_string())
