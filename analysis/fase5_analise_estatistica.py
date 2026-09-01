"""
Fase 5 — Analise Estatistica Formal
TCC: Serverless e Java em e-commerce sob variacao extrema de carga

Requisitos:
    pip install scipy pandas numpy --break-system-packages

Estrutura de pastas CONFIRMADA em disco (levantamento de 21/jul/2026):

    analysis/fargate/fase3/{f1,f2,f3}-{runtime}-r{1..5}-latency.json
    analysis/fargate/fase3/{f1,f2,f3}-{runtime}-r{1..5}-summary.json
    analysis/fargate/fase3b/f2s-{runtime}-r{1..5}-latency.json
    analysis/fargate/fase3b/f2s-{runtime}-r{1..5}-summary.json

    analysis/lambda/fase4/{l2,l3}-{runtime}-r{1..5}-summary.json
    analysis/lambda/fase4/{l2,l3}-{runtime}-r{1..3}-raw.json      <- NDJSON bruto do k6
    analysis/lambda/fase4/{l2,l3}-{runtime}-r{4,5}-latency.json   <- array simples de floats
    analysis/lambda/fase4/timestamps.json                         <- so cobre r1-r3

    analysis/lambda/l1/l1_init_durations.json                     <- ja consolidado,
        contem as listas brutas de init_duration por runtime (11/10/11 valores),
        nao so o agregado. Ver load_l1_init_durations().

runtime in {"springboot", "quarkus-jvm", "quarkus-native"}

IMPORTANTE: os summary.json (Fargate e Lambda) NAO tem data["state"]["testRunDurationMs"]
(formato customizado via handleSummary do k6, so com root_group/metrics/setup_data).
A duracao do teste e obtida via metrics.http_reqs.count / metrics.http_reqs.rate,
que reproduz o valor real com precisao (confirmado: 44523/30.79 = 1445.86s em f1-springboot-r1).
SCENARIO_DURATION_SEC so e usado como ultimo fallback, se um summary vier sem
http_reqs.rate por algum motivo.
"""

import json
import os
import statistics
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

# --------------------------------------------------------------------------
# CONFIGURACAO -- ajustar caminhos conforme o ambiente real (Claude Code)
# --------------------------------------------------------------------------

BASE_DIR = os.path.expanduser("~/Programming/ecommerce-tcc/analysis")

RUNTIMES = ["springboot", "quarkus-jvm", "quarkus-native"]
ROUNDS = [1, 2, 3, 4, 5]

# cenario -> (subpasta, prefixo de arquivo, rodadas que vem como raw.json NDJSON)
# Fargate (f1/f2/f3/f2s): todas as rodadas sao latency.json.
# Lambda (l2/l3): r1-r3 sao raw.json (NDJSON), r4-r5 sao latency.json.
SCENARIOS = {
    "f1":  {"dir": "fargate/fase3",  "file_prefix": "f1",  "raw_rounds": set()},
    "f2":  {"dir": "fargate/fase3",  "file_prefix": "f2",  "raw_rounds": set()},
    "f3":  {"dir": "fargate/fase3",  "file_prefix": "f3",  "raw_rounds": set()},
    "f2s": {"dir": "fargate/fase3b", "file_prefix": "f2s", "raw_rounds": set()},
    "l2":  {"dir": "lambda/fase4",   "file_prefix": "l2",  "raw_rounds": {1, 2, 3}},
    "l3":  {"dir": "lambda/fase4",   "file_prefix": "l3",  "raw_rounds": {1, 2, 3}},
}

# Duracao configurada de cada cenario (usada como fallback para calculo de
# vazao quando o summary.json nao trouxer "state.testRunDurationMs", e
# tambem para estimar a janela de tempo de cada rodada em
# estimate_round_window_from_mtime, usado pelo "recursos"/Fargate).
# Fonte: 04-experiments.md
# f2s atualizado em 10/ago/2026: recoleta sob desenho novo (30s rampa +
# 13min medicao + 30s encerramento = 14min de k6, confirmado via
# http_reqs.count/rate nos summary.json reais). Valor antigo (9.5min) era
# do desenho de 8min de medicao, ja substituido.
SCENARIO_DURATION_SEC = {
    "f1": 24 * 60,
    "f2": int(44.5 * 60),
    "f3": 25 * 60,
    "f2s": 14 * 60,
    "l2": 12 * 60,
    "l3": 8 * 60,
}

OUTPUT_DIR = os.path.expanduser("~/Programming/ecommerce-tcc/analysis/fase5")


# --------------------------------------------------------------------------
# CARREGAMENTO DE DADOS
# --------------------------------------------------------------------------

def _extract_http_req_duration_from_raw(path: str) -> list:
    """Le um raw.json do k6 (NDJSON, ~130-180MB) em streaming, linha a linha,
    extraindo apenas os pontos de http_req_duration -- nunca carrega o
    arquivo inteiro na memoria de uma vez (mesmo padrao usado no proprio
    runner, ver 09-scripts.md)."""
    values = []
    with open(path, "r") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "Point" and obj.get("metric") == "http_req_duration":
                v = obj.get("data", {}).get("value")
                if v is not None:
                    values.append(v)
    return values


def load_latency(scenario: str, runtime: str, rounds=ROUNDS) -> np.ndarray:
    """Concatena as observacoes individuais de latencia (http_req_duration)
    das N rodadas de um cenario/runtime em um unico array.

    Fargate (f1/f2/f3/f2s): sempre le *-latency.json (array simples de floats).
    Lambda (l2/l3): rodadas 1-3 vem como *-raw.json (NDJSON bruto, extrai via
    streaming); rodadas 4-5 vem como *-latency.json (ja extraido)."""
    cfg = SCENARIOS[scenario]
    values = []
    for r in rounds:
        if r in cfg["raw_rounds"]:
            path = os.path.join(
                BASE_DIR, cfg["dir"],
                f"{cfg['file_prefix']}-{runtime}-r{r}-raw.json"
            )
            if not os.path.exists(path):
                print(f"[aviso] arquivo nao encontrado, pulando: {path}")
                continue
            values.extend(_extract_http_req_duration_from_raw(path))
        else:
            path = os.path.join(
                BASE_DIR, cfg["dir"],
                f"{cfg['file_prefix']}-{runtime}-r{r}-latency.json"
            )
            if not os.path.exists(path):
                print(f"[aviso] arquivo nao encontrado, pulando: {path}")
                continue
            with open(path) as fp:
                data = json.load(fp)
            values.extend(data)
    return np.array(values, dtype=float)


def load_l1_init_durations() -> dict:
    """Le analysis/lambda/l1/l1_init_durations.json -- ja consolidado com as
    listas brutas de init_duration por runtime (N=9-11), nao so o agregado.
    Retorna {runtime: np.ndarray}."""
    path = os.path.join(BASE_DIR, "lambda/l1/l1_init_durations.json")
    if not os.path.exists(path):
        print(f"[aviso] arquivo nao encontrado: {path}")
        return {}
    with open(path) as fp:
        data = json.load(fp)
    result = {}
    for runtime in RUNTIMES:
        entry = data.get(runtime, {})
        values = entry.get("init_duration_ms", []) if isinstance(entry, dict) else entry
        result[runtime] = np.array(values, dtype=float)
    return result


def load_round_summaries(scenario: str, runtime: str, rounds=ROUNDS) -> pd.DataFrame:
    """Le o summary.json de cada rodada e retorna um DataFrame com
    avg/p95/http_reqs/failed por rodada -- usado para throughput e
    para a analise de variabilidade ENTRE rodadas."""
    cfg = SCENARIOS[scenario]
    rows = []
    for r in rounds:
        path = os.path.join(
            BASE_DIR, cfg["dir"],
            f"{cfg['file_prefix']}-{runtime}-r{r}-summary.json"
        )
        if not os.path.exists(path):
            print(f"[aviso] arquivo nao encontrado, pulando: {path}")
            continue
        with open(path) as fp:
            data = json.load(fp)
        m = data.get("metrics", {})
        dur = m.get("http_req_duration", {})
        reqs_metric = m.get("http_reqs", {})
        reqs = reqs_metric.get("count", 0)
        reqs_rate = reqs_metric.get("rate")
        failed = m.get("http_req_failed", {}).get("value", 0)

        # summary.json customizado (handleSummary) nao tem state.testRunDurationMs.
        # A duracao real do teste e reconstruida via count/rate (confirmado:
        # bate exatamente com iterations.count/iterations.rate). So cai no
        # fallback de duracao configurada (SCENARIO_DURATION_SEC) se rate
        # vier ausente ou zero por algum motivo.
        if reqs_rate:
            test_duration_sec = reqs / reqs_rate
        else:
            test_duration_sec = SCENARIO_DURATION_SEC[scenario]

        rows.append({
            "round": r,
            "avg_ms": dur.get("avg", np.nan),
            "p95_ms": dur.get("p(95)", np.nan),
            "http_reqs": reqs,
            "failed_pct": failed * 100,
            "test_duration_sec": test_duration_sec,
            "throughput_rps": reqs / test_duration_sec if test_duration_sec else np.nan,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ESTATISTICA DESCRITIVA
# --------------------------------------------------------------------------

def descriptive_stats(arr: np.ndarray) -> dict:
    """Media, mediana, desvio padrao, min, max e percentis relevantes
    sobre a distribuicao completa (todas as observacoes individuais)."""
    if len(arr) == 0:
        return {}
    return {
        "n": len(arr),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=1)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }


def stability_metrics(round_df: pd.DataFrame, latency_arr: np.ndarray) -> dict:
    """Dois niveis de estabilidade, conforme distincao feita em 03-methodology.md:
    - entre rodadas (N=5): CV sobre as medias de cada rodada
    - dentro das rodadas (N=observacoes): CV sobre a distribuicao completa,
      mais razao p95/p50 como indicador de cauda longa / instabilidade sob
      pico (o mesmo padrao que revelou a instabilidade do Spring Boot em F3)
    """
    entre_rodadas_cv = np.nan
    if len(round_df) > 1 and round_df["avg_ms"].mean() > 0:
        entre_rodadas_cv = round_df["avg_ms"].std(ddof=1) / round_df["avg_ms"].mean()

    dentro_rodada_cv = np.nan
    p95_p50_ratio = np.nan
    if len(latency_arr) > 0:
        mean = np.mean(latency_arr)
        if mean > 0:
            dentro_rodada_cv = np.std(latency_arr, ddof=1) / mean
        p50 = np.percentile(latency_arr, 50)
        p95 = np.percentile(latency_arr, 95)
        if p50 > 0:
            p95_p50_ratio = p95 / p50

    return {
        "cv_entre_rodadas": entre_rodadas_cv,
        "cv_dentro_rodada": dentro_rodada_cv,
        "p95_p50_ratio": p95_p50_ratio,
    }


# --------------------------------------------------------------------------
# TESTES DE SIGNIFICANCIA
# --------------------------------------------------------------------------

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = len(a), len(b)
    s1, s2 = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return np.nan
    return (np.mean(a) - np.mean(b)) / pooled_std


def cliffs_delta_from_u(u_stat: float, n1: int, n2: int) -> float:
    """Cliff's delta derivado diretamente da estatistica U de Mann-Whitney:
    delta = 2*U/(n1*n2) - 1
    Evita o calculo O(n1*n2) par-a-par, que seria inviavel com dezenas de
    milhares de observacoes por runtime."""
    return 2 * u_stat / (n1 * n2) - 1


def pairwise_comparison(a: np.ndarray, b: np.ndarray, label_a: str, label_b: str, alpha=0.05) -> dict:
    """Mann-Whitney U + Welch t-test + effect sizes entre duas distribuicoes
    de latencia. alpha=0.05 conforme 03-methodology.md."""
    u_stat, p_mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    t_stat, p_t = stats.ttest_ind(a, b, equal_var=False)  # Welch, nao assume variancias iguais

    d = cohens_d(a, b)
    delta = cliffs_delta_from_u(u_stat, len(a), len(b))

    return {
        "comparacao": f"{label_a} vs {label_b}",
        "mannwhitney_u": u_stat,
        "mannwhitney_p": p_mw,
        "significativo_mw": p_mw < alpha,
        "ttest_t": t_stat,
        "ttest_p": p_t,
        "significativo_t": p_t < alpha,
        "cohens_d": d,
        "cliffs_delta": delta,
        "media_a": float(np.mean(a)),
        "media_b": float(np.mean(b)),
    }


PAIRS = [
    ("springboot", "quarkus-jvm"),
    ("springboot", "quarkus-native"),
    ("quarkus-jvm", "quarkus-native"),
]


def holm_bonferroni(pvals: list) -> list:
    """Correcao de Holm-Bonferroni (step-down) para uma familia de p-valores.
    Ordena em ordem crescente, aplica o fator (m-i+1) ao i-esimo (1-indexado),
    forca monotonicidade (cada p ajustado >= o anterior na ordem crescente) e
    limita a 1.0 -- mesmo resultado que
    statsmodels.stats.multitest.multipletests(pvals, method='holm'), porem
    implementado manualmente porque statsmodels NAO e dependencia do projeto
    (requirements.txt so lista boto3; ver imports no topo deste arquivo --
    so scipy/pandas/numpy)."""
    m = len(pvals)
    pvals_arr = np.asarray(pvals, dtype=float)
    order = np.argsort(pvals_arr)
    sorted_p = pvals_arr[order]

    adjusted_sorted = np.empty(m)
    running_max = 0.0
    for i, p in enumerate(sorted_p):
        rank = i + 1  # 1-indexado
        value = min((m - rank + 1) * p, 1.0)
        running_max = max(running_max, value)
        adjusted_sorted[i] = running_max

    adjusted = np.empty(m)
    adjusted[order] = adjusted_sorted
    return adjusted.tolist()


def apply_holm_correction(comp_df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """Aplica Holm-Bonferroni por familia = as 3 comparacoes par a par de um
    mesmo cenario (nunca as 21 linhas juntas). mannwhitney_p e ttest_p sao
    corrigidos de forma INDEPENDENTE um do outro (duas familias de 3
    p-valores por cenario, nao uma familia combinada de 6). So adiciona
    colunas novas (mannwhitney_p_holm, ttest_p_holm e as flags booleanas
    correspondentes) -- nao sobrescreve nenhuma coluna existente."""
    df = comp_df.copy()
    df["mannwhitney_p_holm"] = np.nan
    df["ttest_p_holm"] = np.nan
    for _, idx in df.groupby("cenario", sort=False).groups.items():
        idx = list(idx)
        df.loc[idx, "mannwhitney_p_holm"] = holm_bonferroni(df.loc[idx, "mannwhitney_p"].tolist())
        df.loc[idx, "ttest_p_holm"] = holm_bonferroni(df.loc[idx, "ttest_p"].tolist())
    df["significativo_mw_holm"] = df["mannwhitney_p_holm"] < alpha
    df["significativo_t_holm"] = df["ttest_p_holm"] < alpha
    return df


# --------------------------------------------------------------------------
# TESTE GLOBAL (ANOVA de uma via / Kruskal-Wallis) -- compara as tres
# versoes simultaneamente, um artefato adicional ao pairwise_comparison
# (nao uma substituicao). Nivel usado: por rodada (N=5, via
# load_round_summaries/avg_ms) para f1/f2/f3/f2s/l2/l3, que e a unidade
# experimental real do desenho -- cada requisicao dentro da mesma rodada
# nao e uma replica independente, entao testar no nivel de observacao
# individual infla o N artificialmente (pseudo-replicacao). Excecao: l1
# nao tem rodadas (N=9-11 invocacoes espacadas dentro de uma sessao
# unica), entao usa as observacoes individuais diretamente como grupos.
# Confirmado via exploracao previa (script separado, descartado): todos
# os 7 cenarios dao significativo (p<0.05) em ambos os testes, sem
# divergencia com os pares de fase5_testes_significancia.csv.
# --------------------------------------------------------------------------

GLOBAL_TEST_SCENARIOS = ["f1", "f2", "f3", "f2s", "l2", "l3"]


def normality_and_variance(groups: list, alpha=0.05) -> dict:
    """Shapiro-Wilk por grupo + Levene entre os tres grupos -- mesmo
    criterio ja usado nas comparacoes par a par para decidir entre ANOVA
    (dados ~normais e variancias compativeis) e Kruskal-Wallis (caso
    contrario). shapiro_ok so e True se TODOS os grupos com n>=3
    passarem (p>alpha)."""
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

    valid_ps = [p for p in shapiro_ps if not np.isnan(p)]
    shapiro_ok = bool(valid_ps) and all(p > alpha for p in valid_ps)

    try:
        _, levene_p = stats.levene(*groups)
    except Exception:
        levene_p = np.nan
    levene_ok = (not np.isnan(levene_p)) and levene_p > alpha

    return {"shapiro_ok": shapiro_ok, "levene_ok": levene_ok}


def global_test_for_groups(groups: list) -> dict:
    """ANOVA de uma via + Kruskal-Wallis sobre os tres grupos -- grava os
    dois sempre (mesmo padrao ja usado em pairwise_comparison com
    Mann-Whitney + Welch t-test lado a lado); a escolha de qual e o
    'oficial' para a narrativa acontece no texto do capitulo de
    resultados, nao no CSV."""
    f_stat, anova_p = stats.f_oneway(*groups)
    h_stat, kruskal_p = stats.kruskal(*groups)
    return {"anova_f": f_stat, "anova_p": anova_p, "kruskal_h": h_stat, "kruskal_p": kruskal_p}


def analyze_global_tests() -> pd.DataFrame:
    """Teste global (3 versoes simultaneas) por cenario -- 7 linhas, uma
    por cenario (diferente de PAIRS/pairwise_comparison, que e por par)."""
    rows = []

    for scenario in GLOBAL_TEST_SCENARIOS:
        groups = []
        ns = []
        for rt in RUNTIMES:
            rdf = load_round_summaries(scenario, rt)
            g = rdf["avg_ms"].dropna().to_numpy()
            groups.append(g)
            ns.append(len(g))

        test_res = global_test_for_groups(groups)
        diag = normality_and_variance(groups)
        metodo_indicado = "ANOVA" if (diag["shapiro_ok"] and diag["levene_ok"]) else "Kruskal-Wallis"

        rows.append({
            "cenario": scenario,
            "n_por_grupo": "/".join(str(n) for n in ns),
            "nivel": "rodada",
            "anova_f": test_res["anova_f"],
            "anova_p": test_res["anova_p"],
            "kruskal_h": test_res["kruskal_h"],
            "kruskal_p": test_res["kruskal_p"],
            "shapiro_ok": diag["shapiro_ok"],
            "levene_ok": diag["levene_ok"],
            "metodo_indicado": metodo_indicado,
        })
        print(f"  [teste global] {scenario}: {metodo_indicado} -- "
              f"anova_p={test_res['anova_p']:.4g} kruskal_p={test_res['kruskal_p']:.4g}")

    # l1: sem rodadas -- observacoes individuais sao a unidade experimental
    init_durations = load_l1_init_durations()
    groups = [init_durations.get(rt, np.array([])) for rt in RUNTIMES]
    ns = [len(g) for g in groups]

    test_res = global_test_for_groups(groups)
    diag = normality_and_variance(groups)
    metodo_indicado = "ANOVA" if (diag["shapiro_ok"] and diag["levene_ok"]) else "Kruskal-Wallis"

    rows.append({
        "cenario": "l1",
        "n_por_grupo": "/".join(str(n) for n in ns),
        "nivel": "individual",
        "anova_f": test_res["anova_f"],
        "anova_p": test_res["anova_p"],
        "kruskal_h": test_res["kruskal_h"],
        "kruskal_p": test_res["kruskal_p"],
        "shapiro_ok": diag["shapiro_ok"],
        "levene_ok": diag["levene_ok"],
        "metodo_indicado": metodo_indicado,
    })
    print(f"  [teste global] l1: {metodo_indicado} -- "
          f"anova_p={test_res['anova_p']:.4g} kruskal_p={test_res['kruskal_p']:.4g}")

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# PIPELINE PRINCIPAL
# --------------------------------------------------------------------------

def analyze_scenario(scenario: str) -> dict:
    print(f"\n=== Cenario: {scenario} ===")
    latencies = {}
    round_summaries = {}
    desc = {}
    stab = {}

    for rt in RUNTIMES:
        arr = load_latency(scenario, rt)
        rdf = load_round_summaries(scenario, rt)
        latencies[rt] = arr
        round_summaries[rt] = rdf
        desc[rt] = descriptive_stats(arr)
        stab[rt] = stability_metrics(rdf, arr)
        print(f"  {rt}: n={len(arr)} media={desc[rt].get('mean', float('nan')):.2f}ms "
              f"p95={desc[rt].get('p95', float('nan')):.2f}ms "
              f"vazao_media={rdf['throughput_rps'].mean() if len(rdf) else float('nan'):.2f} req/s")

    comparisons = []
    for a, b in PAIRS:
        if len(latencies[a]) == 0 or len(latencies[b]) == 0:
            print(f"  [aviso] pulando comparacao {a} vs {b} -- dados ausentes")
            continue
        comparisons.append(pairwise_comparison(latencies[a], latencies[b], a, b))

    return {
        "descriptive": desc,
        "stability": stab,
        "comparisons": comparisons,
        "round_summaries": round_summaries,
    }


def analyze_l1() -> dict:
    """L1 nao segue o padrao 'N rodadas x arquivo por rodada' dos demais
    cenarios -- e um unico arquivo ja consolidado com N=9-11 observacoes
    por runtime (ver load_l1_init_durations)."""
    print("\n=== Cenario: l1 (init_duration) ===")
    init_durations = load_l1_init_durations()
    desc = {}
    for rt in RUNTIMES:
        arr = init_durations.get(rt, np.array([]))
        desc[rt] = descriptive_stats(arr)
        if desc[rt]:
            print(f"  {rt}: n={len(arr)} media={desc[rt]['mean']:.1f}ms "
                  f"mediana={desc[rt]['median']:.1f}ms")

    comparisons = []
    for a, b in PAIRS:
        arr_a, arr_b = init_durations.get(a), init_durations.get(b)
        if arr_a is None or arr_b is None or len(arr_a) == 0 or len(arr_b) == 0:
            print(f"  [aviso] pulando comparacao {a} vs {b} -- dados ausentes")
            continue
        comparisons.append(pairwise_comparison(arr_a, arr_b, a, b))

    return {"descriptive": desc, "stability": {rt: {} for rt in RUNTIMES}, "comparisons": comparisons}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_results = {}

    for scenario in SCENARIOS:
        all_results[scenario] = analyze_scenario(scenario)

    all_results["l1"] = analyze_l1()

    # --- Memoria (Lambda) -- so L1 e viavel sem gerar volume grande de
    # chamadas de API (L2/L3 tem dezenas de milhares de invocacoes por
    # rodada; ver analyze_lambda_memory_l2_l3 se decidir seguir por la) ---
    try:
        l1_memory_df = analyze_lambda_memory_l1()
        if not l1_memory_df.empty:
            mem_path = os.path.join(OUTPUT_DIR, "fase5_l1_memoria.csv")
            l1_memory_df.to_csv(mem_path, index=False)
            print(f"[ok] memoria L1 salva em {mem_path}")
    except ImportError:
        print("[aviso] boto3 nao instalado -- pulando extracao de memoria do L1. "
              "Rode: pip install boto3 --break-system-packages")
    except Exception as e:
        print(f"[aviso] falha ao extrair memoria do L1 via CloudWatch: {e}")

    # --- Exporta tabela consolidada de estatistica descritiva ---
    desc_rows = []
    for scenario, res in all_results.items():
        for rt, d in res["descriptive"].items():
            if not d:
                continue
            row = {"cenario": scenario, "runtime": rt}
            row.update(d)
            row.update(res["stability"][rt])
            desc_rows.append(row)
    desc_df = pd.DataFrame(desc_rows)
    desc_path = os.path.join(OUTPUT_DIR, "fase5_estatistica_descritiva.csv")
    desc_df.to_csv(desc_path, index=False)
    print(f"\n[ok] estatistica descritiva salva em {desc_path}")

    # --- Exporta tabela consolidada de testes de significancia ---
    comp_rows = []
    for scenario, res in all_results.items():
        for c in res["comparisons"]:
            row = {"cenario": scenario}
            row.update(c)
            comp_rows.append(row)
    comp_df = pd.DataFrame(comp_rows)
    comp_df = apply_holm_correction(comp_df)
    comp_path = os.path.join(OUTPUT_DIR, "fase5_testes_significancia.csv")
    comp_df.to_csv(comp_path, index=False)
    print(f"[ok] testes de significancia salvos em {comp_path}")

    # --- Exporta teste global (3 versoes simultaneas) por cenario --
    # artefato adicional, nao sobrescreve nem substitui os dois CSVs acima ---
    global_df = analyze_global_tests()
    global_path = os.path.join(OUTPUT_DIR, "fase5_teste_global.csv")
    global_df.to_csv(global_path, index=False)
    print(f"[ok] teste global salvo em {global_path}")


# --------------------------------------------------------------------------
# MEMORIA E CUSTO (Lambda) -- via CloudWatch Logs, profile "pessoal"
# Confirmado em disco: log groups com retentionInDays=null (nunca expiram),
# formato de linha REPORT tab-delimited, campo Init Duration so aparece em
# invocacoes cold start.
# --------------------------------------------------------------------------

AWS_PROFILE = "pessoal"
AWS_REGION = "us-east-1"

LAMBDA_LOG_GROUPS = {
    "springboot": "/aws/lambda/order-processor-springboot",
    "quarkus-jvm": "/aws/lambda/order-processor-quarkus-jvm",
    "quarkus-native": "/aws/lambda/order-processor-quarkus-native",
}


def parse_report_line(line: str) -> dict:
    """Extrai metricas de uma linha REPORT do CloudWatch Logs do Lambda.

    Formato confirmado (tab-delimited, order-processor-springboot):
    REPORT RequestId: <id>\tDuration: 616.53 ms\tBilled Duration: 4261 ms\t
    Memory Size: 512 MB\tMax Memory Used: 211 MB\tInit Duration: 3644.37 ms\t

    "Init Duration" so aparece em invocacoes cold start -- ausente em warm,
    o que e esperado (nao e erro de parsing)."""
    import re
    result = {}
    m = re.search(r"RequestId:\s*([a-f0-9-]+)", line)
    if m:
        result["request_id"] = m.group(1)
    patterns = {
        "duration_ms": r"Duration:\s*([\d.]+)\s*ms",
        "billed_duration_ms": r"Billed Duration:\s*([\d.]+)\s*ms",
        "memory_size_mb": r"Memory Size:\s*(\d+)\s*MB",
        "max_memory_used_mb": r"Max Memory Used:\s*(\d+)\s*MB",
        "init_duration_ms": r"Init Duration:\s*([\d.]+)\s*ms",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, line)
        if m:
            result[key] = float(m.group(1))
    return result


def fetch_report_lines(log_group: str, start_time_ms: int = None, end_time_ms: int = None,
                        filter_pattern: str = "REPORT") -> list:
    """Busca linhas REPORT de um log group via boto3, paginando automaticamente.

    ATENCAO: os log groups /aws/lambda/order-processor-* tem retencao
    infinita e acumulam invocacoes de L1+L2+L3 juntas (confirmado: 240k-392k
    linhas por funcao). Sem start/end NEM filtro adicional, isso varre tudo
    -- so use sem filtro/tempo se realmente quiser o volume completo.
    Para isolar L1 (cold start esparso), use filter_pattern='"Init Duration"'
    (so aparece em invocacoes cold start) + fingerprint de valor, ver
    analyze_lambda_memory_l1().

    Requer: pip install boto3 --break-system-packages
    Usa o profile "pessoal" (confirmado como o profile correto da conta
    776648109551, ver 02-environment.md)."""
    import boto3
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    logs_client = session.client("logs")

    kwargs = {"logGroupName": log_group, "filterPattern": filter_pattern}
    if start_time_ms is not None:
        kwargs["startTime"] = start_time_ms
    if end_time_ms is not None:
        kwargs["endTime"] = end_time_ms

    lines = []
    paginator = logs_client.get_paginator("filter_log_events")
    for page in paginator.paginate(**kwargs):
        for event in page.get("events", []):
            lines.append(event["message"])
    return lines


def match_init_durations(targets: np.ndarray, candidates: list, tolerance_ms: float = 0.05):
    """Casamento OTIMO (bipartite assignment, scipy.optimize.linear_sum_assignment)
    entre os valores-alvo (init_duration_ms salvos em l1_init_durations.json)
    e os candidatos encontrados no CloudWatch -- minimiza a soma global das
    diferencas absolutas, em vez do greedy anterior que pegava o primeiro
    candidato dentro da tolerancia (causa real da ambiguidade observada no
    quarkus-native: varios cold starts muito proximos em valor, tipico de
    um runtime estavel).

    Pares cuja diferenca (mesmo apos o assignment otimo) passe de
    tolerance_ms sao descartados -- o assignment e obrigado a preencher a
    matriz completa, mas isso nao significa que o par seja um match
    confiavel; filtramos isso explicitamente depois.

    Retorna (matched, diffs): listas paralelas a `targets`, com None nas
    posicoes sem match confiavel."""
    from scipy.optimize import linear_sum_assignment

    n_targets = len(targets)
    matched = [None] * n_targets
    diffs = [None] * n_targets
    if len(candidates) == 0:
        return matched, diffs

    cand_values = np.array([c["init_duration_ms"] for c in candidates])
    cost = np.abs(np.subtract.outer(targets, cand_values))
    row_ind, col_ind = linear_sum_assignment(cost)
    for r, c in zip(row_ind, col_ind):
        diff = cost[r, c]
        if diff <= tolerance_ms:
            matched[r] = candidates[c]
            diffs[r] = diff
    return matched, diffs


def diagnose_l1_mismatch(runtime: str):
    """Ferramenta de diagnostico para o caso em que a maioria dos valores de
    um runtime NAO acha match (ex: quarkus-jvm, 2/10) -- imprime os valores
    salvos em l1_init_durations.json lado a lado com o vizinho mais proximo
    encontrado de fato no CloudWatch, MESMO que a diferenca estoure a
    tolerancia. Isso revela se e:
      (a) um offset sistematico/constante (ex: rounding diferente na fonte
          original) -- os diffs seriam todos parecidos
      (b) valores completamente sem relacao (fonte diferente de verdade,
          ex: X-Ray, aws lambda invoke sync response, ou script antigo) --
          os diffs seriam grandes e irregulares
    """
    log_group = LAMBDA_LOG_GROUPS[runtime]
    targets = sorted(load_l1_init_durations().get(runtime, np.array([])))
    lines = fetch_report_lines(log_group, filter_pattern='"Init Duration"')
    parsed = [parse_report_line(l) for l in lines]
    candidates = sorted(p["init_duration_ms"] for p in parsed if "init_duration_ms" in p)

    print(f"\n=== Diagnostico L1 -- {runtime} ===")
    print(f"Valores salvos em l1_init_durations.json (N={len(targets)}): {targets}")
    print(f"Total de cold starts encontrados no CloudWatch (L1+L2+L3 misturados): {len(candidates)}")
    if not candidates:
        print("Nenhum cold start com 'Init Duration' encontrado -- log group vazio ou filtro errado.")
        return
    print(f"Faixa dos valores encontrados: min={min(candidates):.2f}ms max={max(candidates):.2f}ms")
    print("\ntarget_ms | vizinho_mais_proximo_ms | diferenca_ms")
    for t in targets:
        nearest = min(candidates, key=lambda c: abs(c - t))
        print(f"{t:9.2f} | {nearest:23.2f} | {abs(nearest - t):.2f}")


def analyze_lambda_memory_l1(tolerance_ms: float = 0.5) -> pd.DataFrame:
    """L1 nao pode ser isolado por volume nem por tempo (log group acumula
    L1+L2+L3 juntos, sem timestamp de sessao registrado). Estrategia:

    1. Filtra no lado do CloudWatch so as linhas com "Init Duration" presente
       -- reduz de 240k-392k linhas totais para so os cold starts (bem
       menor, ainda que continue incluindo cold starts de L2/L3 tambem).
    2. Usa os valores de init_duration_ms ja salvos em l1_init_durations.json
       como fingerprint -- casamento OTIMO (bipartite assignment, ver
       match_init_durations) contra os cold starts encontrados.
    3. tolerance_ms=0.5 (nao 0.05) -- diagnosticado via diagnose_l1_mismatch:
       os valores salvos em l1_init_durations.json tem uma diferenca real de
       0.01-0.39ms contra a linha REPORT bruta correspondente (arredondamento
       na coleta original, nao dado de fonte diferente). 0.5ms ainda e bem
       mais apertado que a distancia entre cold starts distintos (faixa
       observada: ~1042-1873ms para quarkus-jvm, sem risco de colisao).
    4. So aceita o match se o numero de linhas encontradas bater com o N
       esperado (9-11) -- caso contrario, avisa em vez de reportar numero
       errado silenciosamente.
    """
    init_durations = load_l1_init_durations()
    rows = []
    for runtime, log_group in LAMBDA_LOG_GROUPS.items():
        targets = init_durations.get(runtime, np.array([]))
        if len(targets) == 0:
            print(f"  [aviso] sem valores de init_duration_ms para {runtime} -- pulando")
            continue

        print(f"[l1-memoria] {runtime}: buscando cold starts (filtro 'Init Duration') em {log_group} ...")
        lines = fetch_report_lines(log_group, filter_pattern='"Init Duration"')
        parsed = [parse_report_line(l) for l in lines]
        print(f"  {len(parsed)} cold starts encontrados no total (L1+L2+L3 misturados)")

        candidates = [p for p in parsed if "init_duration_ms" in p]
        matched, diffs = match_init_durations(targets, candidates, tolerance_ms)

        n_matched = sum(1 for m in matched if m is not None)
        if n_matched != len(targets):
            print(f"  [aviso] {runtime}: {n_matched}/{len(targets)} invocacoes L1 casadas -- "
                  f"resultado PARCIAL. Rode diagnose_l1_mismatch('{runtime}') antes de usar este numero.")

        mem = np.array([m["max_memory_used_mb"] for m in matched if m is not None and "max_memory_used_mb" in m])
        if len(mem) == 0:
            print(f"  [aviso] nenhuma memoria extraida para {runtime}")
            continue
        d = descriptive_stats(mem)
        d["runtime"] = runtime
        d["n_matched"] = int(n_matched)
        d["n_expected"] = len(targets)
        rows.append(d)
        print(f"  {runtime}: n_matched={n_matched}/{len(targets)} "
              f"max_memory_used mean={d['mean']:.1f}MB min={d['min']:.0f}MB max={d['max']:.0f}MB")
    return pd.DataFrame(rows)


def analyze_lambda_memory_l2_l3(scenario: str, timestamps: dict) -> pd.DataFrame:
    """L2/L3: volume grande (~20-27 mil invocacoes por rodada por runtime) --
    puxar TUDO via filter_log_events pode ser lento (varias paginas de API).
    Usa as janelas de tempo conhecidas por rodada (timestamps.json para
    r1-r3; para r4-r5, aproxime via mtime do summary.json menos a duracao
    do cenario, ja que nao ha timestamp exato salvo).

    timestamps: {runtime: {round: (start_epoch_ms, end_epoch_ms)}}

    Chamar essa funcao e opcional -- avalie se o tempo de execucao compensa
    frente a so declarar a limitação, dado o volume envolvido."""
    rows = []
    for runtime, log_group in LAMBDA_LOG_GROUPS.items():
        rt_windows = timestamps.get(runtime, {})
        all_mem = []
        for round_num, (start_ms, end_ms) in rt_windows.items():
            print(f"[{scenario}-memoria] {runtime} r{round_num}: buscando REPORT lines...")
            lines = fetch_report_lines(log_group, start_ms, end_ms)
            parsed = [parse_report_line(l) for l in lines]
            all_mem.extend(p["max_memory_used_mb"] for p in parsed if "max_memory_used_mb" in p)
        if not all_mem:
            continue
        d = descriptive_stats(np.array(all_mem))
        d["runtime"] = runtime
        rows.append(d)
    return pd.DataFrame(rows)


def lambda_invocation_cost(billed_duration_ms: float, memory_mb: int = 512,
                            price_per_request: float = 0.20 / 1_000_000,
                            price_per_gb_second: float = 0.0000166667) -> float:
    """Custo estimado de UMA invocacao Lambda (x86, us-east-1, tier base),
    conforme AWS Lambda pricing (verificado em jul/2026):
        - USD 0,20 por 1 milhao de requisicoes
        - USD 0,0000166667 por GB-segundo

    NAO inclui o free tier (1M req + 400.000 GB-s/mes) -- se a analise for
    para o volume total do experimento (nao por invocacao isolada), o free
    tier provavelmente absorve tudo e o custo real seria zero; nesse caso,
    o numero relevante para a monografia e o custo MARGINAL projetado para
    escala de producao, nao o custo do experimento em si."""
    gb = memory_mb / 1024
    seconds = billed_duration_ms / 1000
    compute_cost = gb * seconds * price_per_gb_second
    return price_per_request + compute_cost


def cost_stats_from_report_lines(lines: list) -> dict:
    """Estatistica descritiva (media/mediana/desvio/min/max/percentis) do
    custo por invocacao, calculado a partir das linhas REPORT reais
    (billed_duration_ms real, nao estimado)."""
    parsed = [parse_report_line(l) for l in lines]
    costs = np.array([
        lambda_invocation_cost(p["billed_duration_ms"], p.get("memory_size_mb", 512))
        for p in parsed if "billed_duration_ms" in p
    ])
    return descriptive_stats(costs)


# --------------------------------------------------------------------------
# CPU E MEMORIA DO FARGATE -- via ECS/ContainerInsights, profile "pessoal"
# CONFIRMADO em disco: dados reais cobrindo toda a coleta (05-15/jul/2026).
# Container Insights estava ativo por default de conta/regiao (nao por flag
# explicita no cluster). Dimensao TaskDefinitionFamily separa por runtime.
#
# ATENCAO -- URGENTE: granularidade de 1min (period=60) para fase3b
# (F2-S, 14-15/jul) esta numa janela de retencao rolante de 15 dias e vai
# comecar a expirar rodada por rodada nos proximos dias. Extraia fase3b
# PRIMEIRO, antes de fase3. fase3 (F1/F2/F3, 05-06/jul) so tem period=300
# disponivel (period=60 ja expirou) -- ainda assim mais que suficiente para
# estatistica agregada por rodada (24-45min de teste = 5-9 datapoints).
# --------------------------------------------------------------------------

FARGATE_CLUSTER = "order-service-cluster"
FARGATE_TASK_CPU_UNITS = 1024   # ver 02-environment.md -- igual nas 3 variantes
FARGATE_TASK_MEMORY_MB = 2048   # idem

TASK_DEF_FAMILIES = {
    "springboot": "order-service-springboot",
    "quarkus-jvm": "order-service-quarkus-jvm",
    "quarkus-native": "order-service-quarkus-native",
}

# period recomendado por fase, conforme retencao confirmada em 21/jul/2026:
#   fase3  (F1/F2/F3, 05-06/jul): period=60 ja expirou -> usar 300 (5min)
#   fase3b (F2-S, 14-15/jul):     period=60 ainda disponivel, mas por pouco
SCENARIO_METRIC_PERIOD_SEC = {
    "f1": 300, "f2": 300, "f3": 300,
    "f2s": 60,
}


def fetch_ecs_container_insights_metric(metric_name: str, task_def_family: str,
                                         start_ms: int, end_ms: int, period_sec: int) -> list:
    """Busca CpuUtilized ou MemoryUtilized do namespace ECS/ContainerInsights,
    filtrado por TaskDefinitionFamily (separa por runtime automaticamente,
    ja que so uma task roda por vez -- protocolo de "task fresca")."""
    import boto3
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    cw = session.client("cloudwatch")
    resp = cw.get_metric_statistics(
        Namespace="ECS/ContainerInsights",
        MetricName=metric_name,
        Dimensions=[
            {"Name": "ClusterName", "Value": FARGATE_CLUSTER},
            {"Name": "TaskDefinitionFamily", "Value": task_def_family},
        ],
        StartTime=start_ms / 1000, EndTime=end_ms / 1000,
        Period=period_sec, Statistics=["Average", "Maximum"],
    )
    return sorted(resp["Datapoints"], key=lambda d: d["Timestamp"])


def estimate_round_window_from_mtime(scenario: str, runtime: str, round_num: int,
                                      padding_sec: int = 600):
    """Nao ha timestamp exato de inicio/fim de rodada salvo para Fargate
    (nem raw do k6 -- que nem existe para Fargate -- nem log solto). Unica
    aproximacao disponivel: mtime local do *-summary.json (momento em que
    foi baixado do runner via scp), subtraindo a duracao conhecida do
    cenario (04-experiments.md) para estimar o inicio.

    padding_sec: folga adicional pra compensar o atraso entre fim do teste
    e o scp de volta (extracao de latencia no runner + transferencia).
    Retorna (start_ms, end_ms) ou None se o arquivo nao existir."""
    cfg = SCENARIOS[scenario]
    path = os.path.join(BASE_DIR, cfg["dir"], f"{cfg['file_prefix']}-{runtime}-r{round_num}-summary.json")
    if not os.path.exists(path):
        return None
    end_ts = os.path.getmtime(path) + padding_sec
    start_ts = end_ts - SCENARIO_DURATION_SEC[scenario] - 2 * padding_sec
    return int(start_ts * 1000), int(end_ts * 1000)


def analyze_fargate_resources(scenario: str, rounds=ROUNDS) -> pd.DataFrame:
    """CPU e memoria por rodada, runtime e cenario, via janela estimada por
    mtime. period conforme SCENARIO_METRIC_PERIOD_SEC (fase3b=60, urgente;
    fase3=300, ja e o maximo disponivel)."""
    period = SCENARIO_METRIC_PERIOD_SEC[scenario]
    rows = []
    for runtime, family in TASK_DEF_FAMILIES.items():
        for r in rounds:
            window = estimate_round_window_from_mtime(scenario, runtime, r)
            if window is None:
                continue
            start_ms, end_ms = window
            cpu_points = fetch_ecs_container_insights_metric("CpuUtilized", family, start_ms, end_ms, period)
            mem_points = fetch_ecs_container_insights_metric("MemoryUtilized", family, start_ms, end_ms, period)
            if not cpu_points and not mem_points:
                print(f"  [aviso] sem datapoints para {scenario}/{runtime}/r{r} "
                      f"(janela pode estar fora da retencao ou mal estimada)")
                continue
            cpu_avg_vals = [d["Average"] for d in cpu_points]
            cpu_max_vals = [d["Maximum"] for d in cpu_points]
            mem_avg_vals = [d["Average"] for d in mem_points]
            mem_max_vals = [d["Maximum"] for d in mem_points]
            rows.append({
                "cenario": scenario, "runtime": runtime, "round": r,
                "n_datapoints_cpu": len(cpu_points),
                "cpu_units_mean": np.mean(cpu_avg_vals) if cpu_avg_vals else np.nan,
                "cpu_units_max": np.max(cpu_max_vals) if cpu_max_vals else np.nan,
                "cpu_pct_mean": (np.mean(cpu_avg_vals) / FARGATE_TASK_CPU_UNITS * 100) if cpu_avg_vals else np.nan,
                "cpu_pct_max": (np.max(cpu_max_vals) / FARGATE_TASK_CPU_UNITS * 100) if cpu_max_vals else np.nan,
                "mem_mb_mean": np.mean(mem_avg_vals) if mem_avg_vals else np.nan,
                "mem_mb_max": np.max(mem_max_vals) if mem_max_vals else np.nan,
                "mem_pct_mean": (np.mean(mem_avg_vals) / FARGATE_TASK_MEMORY_MB * 100) if mem_avg_vals else np.nan,
                "mem_pct_max": (np.max(mem_max_vals) / FARGATE_TASK_MEMORY_MB * 100) if mem_max_vals else np.nan,
            })
            print(f"  {scenario}/{runtime}/r{r}: CPU avg={rows[-1]['cpu_pct_mean']:.1f}% "
                  f"max={rows[-1]['cpu_pct_max']:.1f}% | MEM avg={rows[-1]['mem_mb_mean']:.0f}MB "
                  f"max={rows[-1]['mem_mb_max']:.0f}MB")
    return pd.DataFrame(rows)


def run_fargate_resource_extraction_urgent_first():
    """Ordem de execucao recomendada: f2s PRIMEIRO (retencao de 1min
    expirando), depois f1/f2/f3 (ja garantidos em period=300)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_rows = []

    print("\n=== URGENTE: F2-S (period=60, retencao expirando em breve) ===")
    df_f2s = analyze_fargate_resources("f2s")
    all_rows.append(df_f2s)

    for scenario in ("f1", "f2", "f3"):
        print(f"\n=== {scenario} (period=300, ja garantido) ===")
        all_rows.append(analyze_fargate_resources(scenario))

    result = pd.concat(all_rows, ignore_index=True)
    path = os.path.join(OUTPUT_DIR, "fase5_fargate_recursos.csv")
    result.to_csv(path, index=False)
    print(f"\n[ok] recursos Fargate salvos em {path}")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "recursos":
        # Rodar SO isso primeiro, com prioridade -- retencao de 1min do
        # F2-S esta expirando. Uso: python3 fase5_analise_estatistica.py recursos
        run_fargate_resource_extraction_urgent_first()
    else:
        main()