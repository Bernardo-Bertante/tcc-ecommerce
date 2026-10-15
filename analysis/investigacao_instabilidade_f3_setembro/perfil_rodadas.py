"""Reexame, sem nova coleta, das rodadas do F3 de 02/09 e 05/09/2026.

Lê analysis/fargate/fase3-f3-rerun/ (oficiais + saturated-sb-r4-r5/ + _probe-sb-r4-live-2026-09-05/)
e gera:
  rodadas_f3_setembro.csv  — uma linha por rodada: data, runner, task, p95, cauda, descartes
  perfil_por_minuto.csv    — p95 e %>1s por minuto APROXIMADO de carga (ver aviso abaixo)

AVISO sobre o perfil por minuto: o latency.json guarda só os valores de http_req_duration, na ordem
de escrita do JSON bruto do k6 (≈ ordem de conclusão), sem timestamp; o bruto foi apagado no runner.
O minuto é reconstruído mapeando a posição da requisição na integral da taxa de chegada programada
(48 -> 240 -> 48 it/s). Durante um engasgo as conclusões atrasam, então a posição estimada pode
escorregar alguns segundos. Serve para localizar episódios na escala de minuto, não de segundo.
"""
import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'fargate', 'fase3-f3-rerun')

# task_id vem do CloudTrail RunTask (cloudtrail_runtask_f3_setembro.txt), casado por horário
RUNS = [
    # tag, prefixo relativo a SRC, status, task_id8
    ('springboot-r1', 'f3-springboot-r1-', 'oficial', 'bddf0b88'),
    ('springboot-r2', 'f3-springboot-r2-', 'oficial', 'cf1c4e20'),
    ('springboot-r3', 'f3-springboot-r3-', 'oficial', 'b68d3a19'),
    ('springboot-r4-02set', 'saturated-sb-r4-r5/f3-springboot-r4-', 'descartada (saturated)', '64887e06'),
    ('springboot-r5-02set', 'saturated-sb-r4-r5/f3-springboot-r5-', 'descartada (saturated)', '14b8bd16'),
    ('springboot-sonda', '_probe-sb-r4-live-2026-09-05/', 'sonda (não oficial)', '95d214a9'),
    ('springboot-r4', 'f3-springboot-r4-', 'oficial', '3be0c458'),
    ('springboot-r5', 'f3-springboot-r5-', 'oficial', '35513b06'),
] + [(f'quarkus-jvm-r{i}', f'f3-quarkus-jvm-r{i}-', 'oficial', '') for i in range(1, 6)] \
  + [(f'quarkus-native-r{i}', f'f3-quarkus-native-r{i}-', 'oficial', '') for i in range(1, 6)]

SB_STARTUP = {  # "Started OrderServiceApplication in X seconds", logs /ecs/order-service-springboot
    'bddf0b88': 12.869, 'cf1c4e20': 14.885, 'b68d3a19': 12.552, '64887e06': 12.084,
    '14b8bd16': 15.36, '95d214a9': 10.094, '3be0c458': 12.101, '35513b06': 10.207,
}


def rate(t):
    if t < 300: return 48
    if t < 420: return 48 + (t - 300) / 120 * 192
    if t < 1020: return 240
    if t < 1140: return 240 - (t - 1020) / 120 * 192
    if t < 1440: return 48
    return 48 * (1500 - t) / 60


TS = np.arange(0, 1500, 1.0)
CUM = np.cumsum([rate(t) for t in TS])
CUM = CUM / CUM[-1]


def load(prefix):
    p = os.path.join(SRC, prefix)
    s = json.load(open(p + 'summary.json'))['metrics']
    t = json.load(open(p + 'timing.json'))
    meta = p + 'meta.json'
    m = json.load(open(meta)) if os.path.exists(meta) else {}
    lat = np.array(json.load(open(p + 'latency.json')))
    return s, t, m, lat


def main():
    rows, prof = [], []
    for tag, prefix, status, tid in RUNS:
        s, t, m, lat = load(prefix)
        load_lat = lat[120:]  # ~120 requisições de setup no início do stream
        rows.append({
            'rodada': tag, 'status': status,
            'load_start_utc': t['load_start_utc'][:19],
            'runner_ip': m.get('runner_ip', '52.201.235.225 (inferido: mesma sessão do runner)'),
            'task_id8': tid, 'sb_startup_s': SB_STARTUP.get(tid, ''),
            'p95_ms': round(s['http_req_duration']['p(95)'], 1),
            'p50_ms': round(s['http_req_duration']['med'], 1),
            'max_ms': round(s['http_req_duration']['max']),
            'pct_gt_400ms': round((lat > 400).mean() * 100, 3),
            'pct_gt_1s': round((lat > 1000).mean() * 100, 3),
            'pct_gt_3s': round((lat > 3000).mean() * 100, 3),
            'dropped_iterations': s.get('dropped_iterations', {}).get('count', 0),
            'iterations': s['iterations']['count'],
            'vus_max': s['vus']['max'],
            'http_req_connecting_max_ms': round(s['http_req_connecting']['max'], 1),
        })
        frac = np.arange(len(load_lat)) / len(load_lat)
        tt = np.interp(frac, CUM, TS)
        for minute in range(25):
            x = load_lat[(tt >= minute * 60) & (tt < minute * 60 + 60)]
            prof.append({'rodada': tag, 'minuto_aprox': minute,
                         'p95_ms': round(float(np.percentile(x, 95)), 1),
                         'pct_gt_1s': round(float((x > 1000).mean() * 100), 2), 'n': len(x)})

    with open(os.path.join(HERE, 'rodadas_f3_setembro.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(HERE, 'perfil_por_minuto.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(prof[0])); w.writeheader(); w.writerows(prof)

    for r in rows:
        print(f"{r['rodada']:22s} {r['load_start_utc']}  p95={r['p95_ms']:7.1f}  >1s={r['pct_gt_1s']:6.3f}%  dropped={r['dropped_iterations']}")


if __name__ == '__main__':
    main()
