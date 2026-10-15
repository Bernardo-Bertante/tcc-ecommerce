# Coleta 2 — desenho (23/09/2026)

Segunda coleta exploratória, para atacar o que a primeira deixou aberto
(ver `03_resposta_direta.md`). Mesmo status: exploratório, fora do desenho oficial.

## Perguntas

1. O 1,371× da primeira coleta é efeito de framework ou de ordem? (1 rodada por versão, ordem fixa)
2. Quanto custam de fato as 144.394 validações de pool do Spring Boot?
3. As 7 aridades distintas de `IN (...)` do SB custam planejamento a mais?
4. Por que o SB toca 2,6× menos blocos por linha varrida e ainda assim é mais lento?

## Três condições

| rótulo | task definition | diferença |
|---|---|---|
| `springboot` | `repro-f3-springboot:1` | como está no repo |
| `quarkus-jvm` | `repro-f3-quarkus-jvm:1` | como está no repo |
| `springboot-noval` | `repro-f3-springboot-noval:1` | igual a `springboot` + `SPRING_R2DBC_POOL_VALIDATION_QUERY=""` |

A validação de conexão **não é default do framework**: vem de uma linha explícita em
`order-service/springboot/src/main/resources/application.yml`
(`spring.r2dbc.pool.validation-query: SELECT 1`). Com a variável vazia, o autoconfigure do
Spring Boot cai no `validationDepth` (LOCAL por default), que é checagem local, sem ida ao banco.
**Confirmado por smoke de 1 min antes da coleta:** nenhuma ocorrência de `SELECT $1` no dump,
contra 144.394 na coleta 1. Nenhuma outra variável foi alterada.

## Ordem: palíndromo ABCCBA

```
1: springboot   2: quarkus-jvm   3: springboot-noval
4: springboot-noval   5: quarkus-jvm   6: springboot
```

Posição média de cada condição = **3,5**. Qualquer deriva monotônica ao longo da coleta
(aquecimento de cache, créditos de CPU, vizinho do host, hora do dia) afeta as três igualmente,
em vez de se confundir com a condição. Dá 2 réplicas por condição e um contraste de ordem
interno: a rodada 1 e a 6 são a mesma condição nas duas pontas, assim como a 2 e a 5.

## Instrumentação acrescentada

| item | o que responde |
|---|---|
| `pg_stat_statements.track_planning = on` (dinâmico, sem reboot) | preenche `plans` e `total_plan_time` — pergunta 3 |
| `pg_stats.correlation` de `created_at`/`customer_id`/`id` ao fim de cada rodada | clustering físico — pergunta 4 |
| `n_tup_upd` × `n_tup_hot_upd` por tabela | se o `UPDATE` de 14 colunas do SB impede HOT update — pergunta 4 |
| `seq_tup_read`, `idx_tup_fetch`, tamanho de tabela e de cada índice | volume real lido e inchaço — pergunta 4 |
| `pg_statio_user_tables` | separa blocos de heap de blocos de índice — pergunta 4 |

Mantido da coleta 1: `auto_explain` com `sample_rate = 0,02`, `log_analyze`/`log_buffers`/
`log_verbose`/`log_timing`, dump completo de `pg_stat_statements` por rodada, `TRUNCATE` das três
tabelas e `pg_stat_statements_reset()` antes de cada rodada, task Fargate fresca a cada rodada.

**Ressalva:** `track_planning` tem custo próprio e entra no tempo medido. Como está ligado nas
seis rodadas, não distorce a comparação *dentro* desta coleta, mas os tempos absolutos daqui
**não** são comparáveis aos da coleta 1.

## Custo previsto

6 rodadas × ~19 min ≈ 1h55 de carga. Disparado 23/09 11:35:26Z.
