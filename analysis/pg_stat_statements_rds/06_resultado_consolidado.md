# Resultado consolidado — coletas 1, 2 e 3 (22–23/09/2026)

**Investigação exploratória.** Fora do desenho oficial do TCC. Nenhum `.tex`/`.md` do projeto
principal tocado, sem branch. Sem conclusão interpretativa sobre o que isto significa para a tese.

**A coleta 3 é a fonte principal deste documento.** Ela é a única limpa e completa: palíndromo
ABCCBA, 6/6 rodadas, 0 % de falhas, 6/6 dumps íntegros, uma task conectada por vez. A coleta 1
(uma rodada por versão, ordem fixa) e a coleta 2 (defeito de conexões, ver `coleta2/NOTAS_coleta2.md`)
aparecem só como confirmação.

## Pergunta

O Spring Boot impõe 21–35 % mais CPU ao RDS que o Quarkus (oficial, `fase5_rds_cpu_por_rodada.csv`).
É uma consulta estruturalmente mais cara, ou a mesma consulta executando mais devagar?

## Resposta

**Nenhuma das duas, principalmente.** A maior parte do excesso vem de **statements a mais que não
fazem parte do mix de endpoints**: a validação de conexão do pool R2DBC (`SELECT 1` a cada aquisição
de conexão). Ela é configurada explicitamente em
`order-service/springboot/src/main/resources/application.yml`:

```yaml
spring.r2dbc.pool.validation-query: SELECT 1
```

O `application.properties` do Quarkus não configura nenhuma validação equivalente.

Com **só essa linha desligada** (`SPRING_R2DBC_POOL_VALIDATION_QUERY=""` na task definition, nada
mais alterado), o Spring Boot perde a maior parte da diferença:

| medida (coleta 3, média das 2 rodadas) | SB | SB sem validação | QJ | SB/QJ | sem val./QJ | fração do gap removida |
|---|---|---|---|---|---|---|
| **CPU total do RDS** (EM `cpuUtilization.total`, %) | 17,61 | 14,62 | 14,12 | **1,247** | 1,035 | **86 %** |
| CPU dos backends da app (EM `processList`, %) | 4,92 | 3,64 | 3,30 | 1,491 | 1,103 | **79 %** |
| tempo ativo dos backends (`pg_stat_database.active_time`, ms/s) | 246,2 | 178,3 | 151,9 | 1,621 | 1,174 | **72 %** |
| exec + planejamento (`pg_stat_statements`, ms) | 118.863 | 85.774 | 74.387 | 1,598 | 1,153 | **74 %** |

A primeira linha é a mesma métrica do resultado oficial (CPU do RDS). Aqui o SB/QJ deu
**1,247×**, dentro da faixa oficial de 21–35 %. Sem a validação, cai para **1,035×**.

## Por que a coleta 1 apontou para "a mesma consulta mais lenta"

Na coleta 1, o `get_summary` tinha 94 % do gap em `total_exec_time`, com SQL, chamadas, plano e
volume idênticos. Isso continua verdadeiro, mas a leitura estava incompleta:

1. **`total_exec_time` é tempo de parede, não CPU.** Numa instância de 2 vCPU, ele inclui espera
   por CPU. O `get_summary` do SB leva mais tempo de parede porque disputa CPU com o resto do
   tráfego do próprio SB.
2. **Tirar a validação reduz o tempo de parede do `get_summary`**, sem que a consulta mude:

   | `get_summary`, exec ms (coleta 3) | r1/r6 ou r3/r4 ou r2/r5 | média |
   |---|---|---|
   | SB | 87.231 / 89.664 | 88.448 |
   | SB sem validação | 62.061 / 71.603 | 66.832 |
   | QJ | 52.150 / 59.350 | 55.750 |

   66 % do gap de tempo de parede do `get_summary` some com a validação desligada — mesmo SQL,
   mesmas 4.320 chamadas, mesmo mix de planos.
3. **O `pg_stat_statements` subestima muito o custo da validação.** Ele mostra 0,8–1,2 s de
   execução para 144 mil `SELECT 1` (0,006 ms cada). Mas cada um também é planejado toda vez
   (144 mil planejamentos, 3–7 s) e passa por recepção, parse, bind e resposta pelo socket, que
   nenhuma view do Postgres contabiliza. Some-se a isso uma transação a mais por validação:
   `xact_commit` SB 289 mil, sem validação 145 mil, QJ 131 mil por rodada.

## Controle de ordem (o que a coleta 1 não tinha)

Posição média de cada condição = 3,5. As réplicas nas duas pontas do palíndromo são quase iguais:

| CPU dos backends da app (%) | início | fim |
|---|---|---|
| SB (r1 / r6) | 4,91 | 4,93 |
| SB sem validação (r3 / r4) | 3,67 | 3,61 |
| QJ (r2 / r5) | 3,32 | 3,28 |

Diferença máxima dentro da condição: 0,06 ponto. Entre condições: 0,34 a 1,62 ponto. **Não há
efeito de ordem mensurável.** As três coletas dão o mesmo sentido e a mesma ordenação.

## O que sobra: SB sem validação × QJ (~14–21 % do gap)

Sem a validação, o SB ainda consome um pouco mais (CPU total 1,035×, CPU dos backends 1,103×,
`active_time` 1,174×). Fatos medidos, sem mecanismo isolado:

- **Mais bytes no fio para a mesma carga** (EM, bytes/s): recebidos pelo RDS 48,5 mil (SB sem
  validação) × 36,5 mil (QJ) = 1,33×; enviados 128 mil × 84 mil = 1,52×.
- **Diferenças estruturais de SQL** (coleta 1, `02_comparacao_por_operacao.md`): `RETURNING id` em
  todos os INSERTs do SB; `UPDATE` de 14 colunas × 3; duas variantes de `INSERT` onde o QJ tem uma;
  `LIMIT 2` redundante. Nenhuma delas mostrou custo de execução relevante isoladamente.
- **Planejamento não explica** (pergunta 3 da coleta 2): o QJ replaneja **mais** que o SB. O
  `= ANY($1)` do QJ é replanejado em quase toda chamada; as 7 aridades de `IN (...)` do SB, não.

## Perguntas específicas da coleta 2/3

| pergunta | resposta |
|---|---|
| 1. O gap é efeito de ordem? | **Não.** Réplicas nas duas pontas diferem ≤ 0,06 ponto de CPU. |
| 2. Quanto custa a validação? | **72–86 % do gap**, conforme a métrica (tabela acima). |
| 3. As 7 aridades de `IN` custam planejamento? | **Não.** São menos replanejadas que o `= ANY($1)` do QJ. |
| 4. Por que blocos por linha diferem? | **Em aberto.** Ver abaixo. |

### Pergunta 4 — o que foi descartado e o que ficou aberto

Blocos por 1.000 linhas varridas no `get_summary` (mediana das amostras do `auto_explain`):

| rodada | amostras | Seq | Index | IdxOnly | blocos/1k linhas |
|---|---|---|---|---|---|
| SB r1 | 77 | 18 | 48 | 11 | 301,6 |
| SB r6 | 94 | 15 | 63 | 16 | 277,1 |
| SB sem val. r3 | 71 | 10 | 51 | 10 | 103,4 |
| SB sem val. r4 | 94 | 9 | 64 | 21 | 88,2 |
| QJ r2 | 75 | 10 | 48 | 17 | 468,2 |
| QJ r5 | 94 | 6 | 74 | 14 | 493,1 |

Três patamares estáveis, replicados. Descartado: **escolha de plano** (mix de nós igual em todas as
rodadas); **HOT update** (`n_tup_hot_upd = 0` em todas, porque os dois `UPDATE` alteram `status`,
que é indexado); **correlação física** (`pg_stats.correlation` de `created_at` após `ANALYZE`:
0,983–0,996 em todas). E **não acompanha a CPU**: o QJ toca mais blocos e consome menos. Todos os
acessos são em cache (`shared_blks_read ≈ 0`). O mecanismo não foi identificado.

## Limites

- Só carga **F1** (48 req/s). O resultado oficial cobre F1, F2 e F3. A fração explicada pela
  validação pode ser outra em taxas mais altas.
- **Uma instância `db.t3.micro` nova**, não a oficial. Esquema, parameter group e imagens iguais
  aos oficiais, mas não é o mesmo host.
- `auto_explain` (2 % de amostragem) e `track_planning` ligados nas coletas 2 e 3: custo pequeno e
  simétrico, mas os tempos absolutos não são os de uma execução sem instrumentação.
- A condição "sem validação" mede o efeito de **desligar** a validação, não o que aconteceria com
  outra configuração de pool (por exemplo, `validation-depth: REMOTE` ou validação só em conexões
  ociosas).

## Fontes

| dado | arquivo |
|---|---|
| coleta 3, por rodada | `coleta3/dados/r*/` (`pg_stat_statements.csv`, `pg_stat_database.tsv`, `estado_*.tsv`, `summary.json`, `meta.json`) |
| agregado por rodada e operação | `coleta3/resultados/por_rodada_por_operacao.csv`, `por_operacao_resumo.txt` |
| CPU/rede do Enhanced Monitoring | `coleta3/resultados/enhanced_monitoring_detalhado.json`, `em_detalhado.txt` |
| `pg_stat_database` | `coleta3/resultados/pg_stat_database_delta.txt` |
| mix de planos do `get_summary` | `coleta3/resultados/get_summary_mix_de_planos.txt`, `coleta3/planos/` |
| coleta 2 (com defeito) | `coleta2/NOTAS_coleta2.md` |
| coleta 1 | `02_comparacao_por_operacao.md`, `03_resposta_direta.md` (resposta parcial, superada por este documento) |
