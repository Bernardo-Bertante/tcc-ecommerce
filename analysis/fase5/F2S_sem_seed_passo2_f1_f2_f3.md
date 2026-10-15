# Passo 2 — o mesmo seed existe em F1, F2 e F3?

Sim, mas a contaminação é pequena em todos (< 0,5% das amostras), então **só reportado, sem recálculo** dos testes.

Os scripts f1_low_load.js, f2_high_load.js e f3_burst_autoscaling.js usam `setup()` → `prepareOrderPools(benchmarkDataConfig(smoke))`; em modo não-smoke são 120 `POST /orders` de semeadura (`READ_POOL_SIZE` default 120). f3_black_friday_controlled.js reexporta o `setup` do F2.

Nesses cenários `http_reqs − iterations` NÃO é só o seed: 12% das iterações (slots 86–97 do mix) fazem create + update_status (2 requests). O fechamento exato é `http_reqs = iterations + 0,12·iterations + 120` (resíduo 0 a ±7 requests por rodada).

| Diretório / cenário | amostras por rodada | seed (120) | resíduo `reqs−it−120−0,12·it` | efeito de remover as 120 primeiras (concat. 5 rodadas; SB / QJ / QN): média, p95, p99 |
|---|---:|---:|---:|---|
| fase3 F1 (antigo, 30 req/s) | ≈44.531 | 0,27% | −7…−6 | −0,55/−0,53/−5,77 ; −0,40/−1,18/−0,59 ; 0,00/+0,05/+0,05 |
| fase3-f1-rerun F1 (48 req/s) | ≈71.144 | 0,17% | −2,4…−0,2 | −0,27/−0,60/−0,42 ; −0,22/−1,13/−0,33 ; −0,01/+0,10/+0,06 |
| fase3 F2 | 242.844 | 0,05% | −2,4 | −0,05/−0,31/0,00 ; −0,03/−0,26/0,00 ; +0,01/−0,01/+0,04 |
| fase3 F3 / fase3-f3-rerun F3 | 233.975 | 0,05% | +0,1 | ≤ +0,10 em todas |

(valores em %, remover o seed − com seed)

Os `*-latency.json` de F1/F2/F3 incluem os 120 POST nas primeiras 120 posições, como no F2-S. O maior efeito é na cauda do F1 (p95 do QJ −1,1%; no F1 antigo, p99 do SB −5,8%, descartado). Todos abaixo do ruído entre rodadas. Fora do escopo: também entram nessas distribuições os POSTs auxiliares (`create_order_for_status_update`) e o warm-up do F2, por desenho.
