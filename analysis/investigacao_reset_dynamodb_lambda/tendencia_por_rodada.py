#!/usr/bin/env python3
"""Testa se a latencia de L2/L3 cresce ao longo da ordem de execucao (r1 -> r5).

Hipotese testada: se o acumulo de itens no DynamoDB tivesse efeito sobre a
medicao, as rodadas posteriores seriam sistematicamente mais lentas.

Fontes (dados oficiais, nada novo e coletado):
  analysis/lambda/fase4/{l2,l3}-{versao}-r{1..5}-summary.json  (mediana/p95/n)
  analysis/lambda/fase4/l2-springboot-r1-raw.json              (perfil intra-rodada)
  analysis/lambda/fase4/l2-springboot-r5-latency.json          (perfil intra-rodada)

Uso: python3 tendencia_por_rodada.py
"""
import csv
import json
import os
import statistics

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
FASE4 = os.path.join(HERE, '..', 'lambda', 'fase4')
VERSOES = ('springboot', 'quarkus-jvm', 'quarkus-native')
RODADAS = (1, 2, 3, 4, 5)
BLOCO = 2048


def summary(cenario, versao, rodada):
    with open(os.path.join(FASE4, f'{cenario}-{versao}-r{rodada}-summary.json')) as fp:
        return json.load(fp)['metrics']


def tendencia():
    linhas = []
    for cenario in ('l2', 'l3'):
        for versao in VERSOES:
            med = [summary(cenario, versao, r)['http_req_duration']['med'] for r in RODADAS]
            p95 = [summary(cenario, versao, r)['http_req_duration']['p(95)'] for r in RODADAS]
            n = [int(summary(cenario, versao, r)['http_reqs']['count']) for r in RODADAS]
            rho, p = stats.spearmanr(RODADAS, med)
            reg = stats.linregress(RODADAS, med)
            linhas.append({
                'cenario': cenario, 'versao': versao,
                **{f'med_r{r}': round(m, 2) for r, m in zip(RODADAS, med)},
                **{f'p95_r{r}': round(v, 2) for r, v in zip(RODADAS, p95)},
                **{f'n_r{r}': v for r, v in zip(RODADAS, n)},
                'delta_med_ms': round(med[-1] - med[0], 2),
                'delta_med_pct': round(100 * (med[-1] / med[0] - 1), 1),
                'spearman_rho': round(rho, 3), 'spearman_p': round(p, 4),
                'slope_ms_por_rodada': round(reg.slope, 3),
                'slope_p': round(reg.pvalue, 4),
            })
    return linhas


def perfil_intra_rodada(nome, fase=None):
    """Mediana por bloco de BLOCO iteracoes dentro de uma rodada."""
    raw = os.path.join(FASE4, f'{nome}-raw.json')
    if os.path.exists(raw):
        vals = []
        with open(raw) as fp:
            for line in fp:
                if '"http_req_duration"' not in line:
                    continue
                obj = json.loads(line)
                if obj.get('type') != 'Point' or obj.get('metric') != 'http_req_duration':
                    continue
                if fase and obj['data'].get('tags', {}).get('phase') != fase:
                    continue
                vals.append(obj['data']['value'])
    else:
        with open(os.path.join(FASE4, f'{nome}-latency.json')) as fp:
            vals = json.load(fp)
    blocos = [round(statistics.median(vals[i:i + BLOCO]), 2)
              for i in range(0, len(vals) - BLOCO + 1, BLOCO)]
    return len(vals), blocos


def main():
    linhas = tendencia()
    out = os.path.join(HERE, 'tendencia_por_rodada.csv')
    with open(out, 'w', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f'-> {out}\n')

    print('Mediana de http_req_duration (ms) por ordem de execucao:')
    for l in linhas:
        meds = ' '.join(f'{l[f"med_r{r}"]:6.2f}' for r in RODADAS)
        print(f'  {l["cenario"]:3} {l["versao"]:15} {meds} | delta={l["delta_med_ms"]:+5.2f}ms '
              f'({l["delta_med_pct"]:+5.1f}%) rho={l["spearman_rho"]:+.2f} p={l["spearman_p"]:.3f} '
              f'slope={l["slope_ms_por_rodada"]:+.3f} ms/rodada')

    print('\nPerfil INTRA-rodada (mediana por bloco de %d iteracoes, fase load):' % BLOCO)
    for nome, fase in (('l2-springboot-r1', 'load'), ('l2-springboot-r5', None)):
        n, blocos = perfil_intra_rodada(nome, fase)
        print(f'  {nome} (n={n}): {blocos}')
    print('\nA tabela `processed_orders` satura em 4096 invocacoes e `stock_reservations`')
    print('em 12286 (ver espaco_de_chaves.py) -- ambos DENTRO do 1o bloco/rodada acima.')


if __name__ == '__main__':
    main()
