# Coleta 2 (23/09/2026, 11:35–13:17Z) — registro, defeito e o que se aproveita

Desenho em `../05_desenho_coleta2.md`. Palíndromo ABCCBA, três condições (`springboot`,
`quarkus-jvm`, `springboot-noval`), F1 48 req/s, 16 min por rodada.

## Defeito de execução (meu, no orquestrador v2)

O v2 herdou do script da repro a regra "no início de cada rodada, parar a task **da mesma família**".
Com duas famílias isso deixava no máximo 2 apps conectados. Com três famílias, a partir da rodada 3
ficaram **três apps conectados ao mesmo tempo** (pool de até 40 conexões cada) contra
`max_connections = 100`. Consequências:

| rodada | apps conectados | falhas HTTP | dump de `pg_stat_statements` |
|---|---|---|---|
| 1 springboot | 1 | 0,000 % | ok |
| 2 quarkus-jvm | 2 (SB r1 ocioso) | 0,000 % | ok |
| 3 springboot-noval | 3 | 0,000 % | **perdido** (`remaining connection slots are reserved`) |
| 4 springboot-noval | 3 | **0,186 %** (90 × `53300 too many clients`) | ok |
| 5 quarkus-jvm | 3 | 0,000 % | ok |
| 6 springboot | 3 | **0,043 %** (21 × `53300`) | perdido na hora, **recuperado** depois (ver abaixo) |

Rodada 6: foi a última, então nenhum `pg_stat_statements_reset()` veio depois. Dump refeito às
13:39Z a partir da view intacta (288.670 chamadas, contra 288.752 da rodada 1 — íntegro). O
último autovacuum/autoanalyze foi às 13:16:53Z, antes do fim da carga, então o estado físico
recapturado é o do fim da rodada.

Checagem de contaminação cruzada: rodadas SB contêm só textos de SB e rodadas QJ só de QJ.
As tasks ociosas não geraram consultas mensuráveis. O efeito delas foi ocupar slots de conexão.

## Instabilidade do host

*Steal* de CPU (Enhanced Monitoring, 1 s) subiu da rodada 3 em diante: 2,30 / 2,32 / 3,73 / 3,56 /
3,00 / 3,41 % (coleta 1: 2,15–2,52 %). O `total_exec_time` do `pg_stat_statements` é **tempo de
parede** e ficou ruidoso: SB r1 → r6 +13 %, e a rodada 2 do QJ teve operações triviais até 2,6×
mais lentas que na coleta 1 e 19,3 s de planejamento, contra 7,6 s na rodada 5.

## O que se aproveita

**CPU consumida pelos backends da aplicação** (EM `processList`, soma de `cpuUsedPc` dos
processos `postgres: orderuser orderdb`, média na janela). É CPU efetivamente consumida, não
afetada por *steal* nem por fila, e **não depende do dump** — existe inclusive para a rodada 3:

| janela | backends_app (%) |
|---|---|
| C1 springboot | 4,54 |
| C1 quarkus-jvm | 3,18 |
| C2 r1 springboot | 4,37 |
| C2 r2 quarkus-jvm | 3,32 |
| C2 r3 springboot-noval | 3,85 |
| C2 r4 springboot-noval | 3,92 |
| C2 r5 quarkus-jvm | 3,41 |
| C2 r6 springboot | 4,72 |

As rodadas sem validação são exatamente as que tiveram pressão de conexão, por isso
**não usei a coleta 2 como fonte do número de "quanto a validação explica"**. Esse número vem da
coleta 3.

Pergunta 3 (planejamento), dumps íntegros r1, r2, r4, r5, r6 — ver `resultados/por_rodada_por_operacao.csv`:
- `order_items` por lista: SB (7 textos `IN`) 1.664–2.112 planos, 255–400 ms; QJ (1 texto
  `= ANY($1)`) 6.410–6.444 planos para 6.480 chamadas, 898–1.277 ms. O QJ replaneja quase toda
  chamada; o SB, não.
- Planejamento total fora a validação é maior no QJ que no SB em todas as rodadas.
- `SELECT $1` do SB: planejado em toda chamada (144.335 / 144.322 planos), 3,0–3,7 s de
  planejamento para 0,8–1,1 s de execução.

Pergunta 4: `n_tup_hot_upd = 0` em todas as rodadas, nas duas versões (31.753 updates acumulados,
nenhum HOT). Os dois `UPDATE` alteram `status`, que tem índice (`idx_orders_status`).
