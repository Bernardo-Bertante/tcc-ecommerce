#!/usr/bin/env python3
"""Figuras do capitulo de Resultados da versao reduzida do TCC (nov/2026).

Uso:
    python3 reducao_figuras.py <pasta com os CSVs do reducao_estatistica.py> <pasta analysis do repositorio> [pasta de saida]

Exemplo, a partir da raiz do repositorio:
    python3 analysis/reducao/reducao_figuras.py analysis/reducao analysis figuras

Gera tres PDFs (largura de 16 cm, a largura util da pagina):
    fig_coldstart_lambda.pdf     L1: inicializacao + primeira execucao, media por versao
    fig_inicializacao_fargate.pdf  H1b: os 9 ciclos de cada versao e a media, eixo logaritmico
    fig_latencia_aquecida.pdf    L2, L3, F1, F2, F3: media das 5 rodadas e IC 95% da media

Nenhum numero e calculado aqui: medias e intervalos vem dos CSVs do reducao_estatistica.py;
os pontos individuais do H1b vem de fargate/h1b/h1b_startup_times.json.
"""

import csv
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

VERSOES = ["springboot", "quarkus-jvm", "quarkus-native"]
NOMES = {"springboot": "Spring Boot JVM", "quarkus-jvm": "Quarkus JVM", "quarkus-native": "Quarkus Native"}
# Paleta categórica validada (três primeiros slots; passa todos os pares, CVD inclusive)
COR = {"springboot": "#2a78d6", "quarkus-jvm": "#eb6834", "quarkus-native": "#1baf7a"}
# Textura como canal de reserva para impressão em tons de cinza (45° e 135°)
HACHURA = {"springboot": "", "quarkus-jvm": "///", "quarkus-native": "\\\\\\"}
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRADE = "#e4e3df"
CM = 1 / 2.54


def br(v, casas=1):
    """Número no formato brasileiro: milhar com ponto, decimal com vírgula."""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def estilo():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Latin Modern Roman", "LM Roman 10", "DejaVu Serif"],
        "font.size": 9,
        "axes.edgecolor": TINTA_2,
        "axes.labelcolor": TINTA,
        "axes.linewidth": 0.6,
        "xtick.color": TINTA_2,
        "ytick.color": TINTA_2,
        "xtick.labelcolor": TINTA,
        "ytick.labelcolor": TINTA,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "hatch.linewidth": 0.6,
        "hatch.color": "white",
        "pdf.fonttype": 42,
        "legend.frameon": False,
    })


def ler_csv(caminho):
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fig_coldstart_lambda(l1, saida):
    linhas = {(r["medida"], r["versao"]): r for r in l1}
    ini = {v: float(linhas[("L1 inicializacao (Init Duration, l1_duration_postinit.csv)", v)]["media"]) for v in VERSOES}
    exe = {v: float(linhas[("L1 primeira execucao (Duration)", v)]["media"]) for v in VERSOES}
    tot = {v: float(linhas[("L1 inicializacao + primeira execucao", v)]["media"]) for v in VERSOES}

    fig, ax = plt.subplots(figsize=(16 * CM, 5.2 * CM))
    ordem = list(reversed(VERSOES))  # Spring Boot no topo
    y = range(len(ordem))
    c_ini, c_exe = "#1d4f91", "#9cc3ee"  # mesmo matiz, claro/escuro: as partes, não as versões
    ax.barh(y, [ini[v] for v in ordem], height=0.55, color=c_ini, edgecolor="white", linewidth=1.0,
            label="Inicialização (Init Duration)")
    ax.barh(y, [exe[v] for v in ordem], left=[ini[v] for v in ordem], height=0.55, color=c_exe,
            edgecolor="white", linewidth=1.0, label="Primeira execução (Duration)")
    for i, v in enumerate(ordem):
        ax.text(tot[v] + 80, i, f"{br(tot[v])} ms", va="center", ha="left", color=TINTA, fontsize=8.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels([NOMES[v] for v in ordem])
    ax.set_xlim(0, 8200)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: br(x, 0)))
    ax.set_xlabel("Tempo médio por invocação com cold start (ms)")
    ax.grid(axis="x", color=GRADE, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=8.5, handlelength=1.2)
    fig.tight_layout()
    fig.savefig(os.path.join(saida, "fig_coldstart_lambda.pdf"))
    plt.close(fig)


def fig_inicializacao_fargate(l1, h1b_json, saida):
    linhas = {(r["medida"], r["versao"]): r for r in l1}
    fig, ax = plt.subplots(figsize=(16 * CM, 4.8 * CM))
    ordem = list(reversed(VERSOES))
    for i, v in enumerate(ordem):
        pontos = h1b_json[v]["startup_seconds"]
        media = float(linhas[("H1b inicializacao do conteiner (s)", v)]["media"])
        ax.scatter(pontos, [i] * len(pontos), s=22, color="#1d4f91", alpha=0.55, linewidths=0, zorder=3)
        ax.plot([media, media], [i - 0.28, i + 0.28], color=TINTA, linewidth=1.6, zorder=4)
        ax.text(max(pontos) * 1.18, i, f"média {br(media, 2 if media >= 1 else 3)} s", va="center",
                ha="left", color=TINTA, fontsize=8.5)
    ax.set_xscale("log")
    ax.set_xlim(0.1, 40)
    ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1.0,)))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: br(x, 1) if x < 1 else br(x, 0)))
    ax.set_yticks(range(len(ordem)))
    ax.set_yticklabels([NOMES[v] for v in ordem])
    ax.set_ylim(-0.6, len(ordem) - 0.4)
    ax.set_xlabel("Tempo de inicialização do contêiner (s, escala logarítmica)")
    ax.grid(axis="x", which="both", color=GRADE, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    fig.savefig(os.path.join(saida, "fig_inicializacao_fargate.pdf"))
    plt.close(fig)


def fig_latencia_aquecida(cen, saida):
    d = {(r["cenario"], r["versao"]): r for r in cen}
    paineis = [("AWS Lambda", ["L2", "L3"]), ("ECS Fargate", ["F1", "F2", "F3"])]
    fig, eixos = plt.subplots(1, 2, figsize=(16 * CM, 6.6 * CM), gridspec_kw={"width_ratios": [2, 3]})
    larg = 0.26
    for ax, (titulo, cens) in zip(eixos, paineis):
        for j, v in enumerate(VERSOES):
            xs, ys, err_lo, err_hi = [], [], [], []
            for i, c in enumerate(cens):
                r = d[(c, v)]
                m = float(r["media_rodadas_ms"])
                lo, hi = float(r["media_ic95_inf_ms"]), float(r["media_ic95_sup_ms"])
                xs.append(i + (j - 1) * (larg + 0.02))
                ys.append(m)
                err_lo.append(m - lo)
                err_hi.append(hi - m)
            ax.bar(xs, ys, width=larg, color=COR[v], hatch=HACHURA[v], edgecolor="white", linewidth=0.8,
                   label=NOMES[v], zorder=2)
            ax.errorbar(xs, ys, yerr=[err_lo, err_hi], fmt="none", ecolor=TINTA, elinewidth=0.8,
                        capsize=2.5, capthick=0.8, zorder=3)
        ax.set_xticks(range(len(cens)))
        ax.set_xticklabels(cens)
        ax.set_title(titulo, fontsize=9.5, color=TINTA, loc="left")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: br(x, 0)))
        ax.grid(axis="y", color=GRADE, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
        ax.set_ylim(bottom=0)
    eixos[0].set_ylabel("Latência média (ms)")
    handles, labels = eixos[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=8.5, bbox_to_anchor=(0.5, 1.0),
               handlelength=1.6)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(os.path.join(saida, "fig_latencia_aquecida.pdf"))
    plt.close(fig)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    csvs = os.path.expanduser(sys.argv[1])
    base = os.path.expanduser(sys.argv[2])
    saida = os.path.expanduser(sys.argv[3]) if len(sys.argv) > 3 else "figuras"
    os.makedirs(saida, exist_ok=True)
    estilo()
    l1 = ler_csv(os.path.join(csvs, "reducao_l1_h1b.csv"))
    cen = ler_csv(os.path.join(csvs, "reducao_cenarios.csv"))
    h1b_json = json.load(open(os.path.join(base, "fargate/h1b/h1b_startup_times.json")))
    fig_coldstart_lambda(l1, saida)
    fig_inicializacao_fargate(l1, h1b_json, saida)
    fig_latencia_aquecida(cen, saida)
    print("figuras gravadas em", saida)


if __name__ == "__main__":
    main()
