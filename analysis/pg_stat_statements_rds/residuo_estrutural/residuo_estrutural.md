# Resíduo estrutural SB sem validação × QJ — texto, plano, fetch ou layout? (24/09/2026)

**Investigação exploratória.** Fora do desenho oficial do TCC. Nenhum `.tex`/`.md` do projeto
principal tocado, sem branch. Sem conclusão interpretativa sobre o significado para a tese.

## Pergunta

Com a validação de pool desligada (`SPRING_R2DBC_POOL_VALIDATION_QUERY=""`), sobra um resíduo entre
Spring Boot e Quarkus JVM no RDS. O `get_summary` do SB continua mais lento por chamada. O resíduo vem
de uma **consulta estruturalmente diferente**, de um **plano diferente** ou de um **padrão de busca
(`fetch_size`) diferente** entre os drivers?

## Resposta direta

**Nenhuma das três.**

- **Texto:** as 5 consultas do `get_summary` são byte a byte iguais (5/5 idênticas após a normalização).
- **Plano:** o mesmo nas duas versões: plano genérico, `Index Scan` em `idx_orders_created_at`,
  estimativa de ~74 linhas para ~14,8 mil reais.
- **Fetch:** os dois drivers trazem o resultado inteiro num único `Execute`. O r2dbc-postgresql
  1.0.9 usa `fetchSize = NO_LIMIT` por padrão, e o Vert.x `preparedQuery().execute()` usa `fetch = 0`.
  Nenhuma das apps altera isso.

**A diferença de blocos existe, mas vai no sentido oposto ao da premissa.** No `get_summary`, o
**QJ** toca **~3× mais** blocos por chamada que o SB sem validação (2.820 × 959). A causa não está na
consulta. Está na **ordem física das linhas de `orders` no heap**, que cada framework produz de modo
diferente ao inserir:

| Index Scan forçado sobre a tabela ao fim da rodada (~14,9 mil linhas) | SB sem val. r1 / r4 | QJ r2 / r3 |
|---|---|---|
| blocos, tabela como ficou | 3.426 / 1.375 | 7.095 / 7.196 |
| blocos, depois de `CLUSTER orders USING idx_orders_created_at` | **328 / 328** | **328 / 328** |
| linhas nunca atualizadas: troca de página entre vizinhas na ordem de inserção (xmin) | 0,097 / 0,072 | **0,471 / 0,475** |

Reordenado o heap, o mesmo plano toca exatamente o mesmo número de blocos nas 4 rodadas. No QJ,
pedidos inseridos em sequência caem em páginas alternadas cerca de metade das vezes, e no SB em menos
de 10 %. O `created_at` segue a ordem de inserção nos dois (0,1 % de inversões), então a diferença
não vem do timestamp gerado na app.

**Mecanismo compatível, medido no código-fonte mas não isolado experimentalmente:** no PostgreSQL,
cada backend mantém sua própria página-alvo para INSERT. INSERTs consecutivos feitos pela mesma
conexão tendem a ir para a mesma página, e feitos por conexões diferentes, para páginas diferentes.
Os dois pools escolhem a conexão de formas diferentes:
- `r2dbc-pool` 1.0.2 (`io/r2dbc/pool/ConnectionPool.java:302`): `.idleResourceReuseMruOrder()`, que
  reusa a conexão devolvida por último;
- Vert.x 4.5.26 (`io/vertx/core/net/impl/pool/SimpleConnectionPool.java:86-95`,
  `SAME_EVENT_LOOP_SELECTOR`): primeira conexão livre **do mesmo event loop** da requisição. A JVM
  vê 2 CPUs (`[gc,init] CPUs: 2 total, 2 available` no log das tasks), então há vários event loops.

A proporção exata de 0,47 não foi derivada desse mecanismo. Ele é compatível com o sentido e a ordem
de grandeza, mas não foi testado trocando a política de pool.

**A latência do `get_summary` não é explicada por nenhuma das três hipóteses, nem pelos blocos.** O SB
sem validação toca menos blocos e ainda assim gasta mais tempo por chamada (tabela abaixo). Nesta
coleta a diferença é pequena e ruidosa: r4 (14,7 ms) fica perto de r2 (13,5 ms), e o r1 destoa
também no k6 (mediana de 7,2 ms, contra 4,2–4,4 ms nas outras 3 rodadas). As duas versões disparam as
5 agregações em paralelo, cada uma numa conexão do pool (`Mono.zip` / `Uni.combine().all()`), então
isso também não as distingue. **O mecanismo da diferença de latência do `get_summary` continua não
identificado.**

## Setup (igual ao validado nas coletas anteriores)

| item | valor |
|---|---|
| RDS | `pgss-res-postgres`, db.t3.micro, PG 16.4, 20 GB gp3, us-east-1d (mesma AZ do oficial) |
| parameter group | cópia de `order-service-pg16-custom` + `auto_explain` (`sample_rate=0,02`, analyze/buffers/timing/verbose/nested, JSON) + `track_planning=on`. Grupo oficial não tocado |
| esquema | `../../reproducao_f3_instabilidade/esquema_oficial_schema_only.sql` (sem a linha `SET transaction_timeout`, inexistente no PG 16.4) + baseline do Flyway |
| task defs | `pgss-res-springboot-noval`, `pgss-res-quarkus-jvm`, 1024/2048, **mesmos digests** (`@sha256:276548dd…`, `@sha256:abec3583…`), geradas de `../f2_f3/taskdefs/` trocando só host, família e log group |
| carga | F1 oficial, 48 req/s, 1 min rampa + **15 min** platô + 1 min descida, `f1_low_load.js` do HEAD |
| ordem | palíndromo `1:SB-noval 2:QJ 3:QJ 4:SB-noval`, 2 réplicas por condição |
| por rodada | task fresca → `TRUNCATE` → `VACUUM ANALYZE` → `pg_stat_statements_reset()` → k6 → dump → **app parada** → layout físico (`ctid`, `pageinspect`) → `EXPLAIN` direto → `CLUSTER` → `EXPLAIN` de novo |

4/4 rodadas com k6 rc=0. Chamadas por operação idênticas entre as condições (ex.: `get_summary` 9.210 × 9.210).

## Item 1 — `pg_stat_statements` (soma das 2 réplicas)

| operação | cond | calls | linhas/call | blocos/call | blocos/linha | exec ms/call | plan ms/call |
|---|---|---|---|---|---|---|---|
| get_summary | SB-noval | 9.210 | 3,20 | **959,3** | **299,8** | 16,16 | 0,114 |
| get_summary | QJ | 9.210 | 3,20 | **2.820,1** | **881,3** | 12,42 | 0,153 |
| get_order | SB-noval / QJ | 116.170 | 1,50 | 3,3 / 3,3 | 2,23 / 2,20 | 0,031 / 0,030 | |
| get_orders_by_customer | SB-noval / QJ | 41.490 | 6,46 | 10,1 / 9,9 | 1,56 / 1,53 | 0,063 / 0,050 | |
| create_order | SB-noval / QJ | 89.201 / 89.197 | 1,00 | 9,8 / 9,8 | 9,82 / 9,83 | 0,154 / 0,125 | |
| insert_status_history | SB-noval / QJ | 40.788 / 40.786 | 1,00 | 10,6 / 10,5 | | 0,160 / 0,155 | |
| update_status | SB-noval / QJ | 11.054 / 11.053 | 1,00 | 15,1 / 15,1 | | 0,155 / 0,143 | |

`shared_blks_read` = 0 em tudo (100 % cache). **Fora do `get_summary`, blocos por chamada e por linha
são iguais entre os frameworks.** Por rodada (`resultados/por_rodada_resumo.txt`):

| rodada | get_summary blocos/call | get_summary exec ms/call | active_time ms/s | xact/s | k6 mediana / p95 (ms) |
|---|---|---|---|---|---|
| r1 SB-noval | 1.339,8 | 17,57 | 188,7 | 150,2 | 7,18 / 23,76 |
| r2 QJ | 2.788,1 | 13,49 | 141,8 | 136,4 | 4,33 / 12,57 |
| r3 QJ | 2.852,0 | 11,35 | 131,7 | 136,3 | 4,40 / 11,93 |
| r4 SB-noval | 579,6 | 14,75 | 166,0 | 150,4 | 4,18 / 13,08 |

Observação registrada sem interpretação: mesmo sem validação, o SB faz ~14 transações/s a mais que o QJ.

## Item 2 — planos (auto_explain, 2 %)

`resultados/planos_resumo.md` (assinaturas por texto), `resultados/planos_amostras.csv` (1 linha por
plano), `resultados/get_summary_exemplos_e_faixas.txt` (planos completos).

- **Tipo de scan idêntico em todas as operações.** `get_summary`: `Index Scan` (SB 159 amostras / QJ 111),
  `Index Only Scan` no `COUNT(*)` (15 / 39), `Seq Scan` ocasional (25 / 8), sempre em
  `idx_orders_created_at`. `get_order`/`update_status`: `Index Scan` em `orders_pkey`. Demais: `Bitmap Heap Scan`.
- **Sem `Sort` a mais em nenhum lado.** O único `Sort` está no próprio texto (top customers,
  revenue by day), igual nos dois.
- **Estimado × real:** no `get_summary` a razão estimado/real é ~0,00 nos dois (`rows_plan` 73–74 para
  14,8 mil reais). É o plano genérico, com o mesmo erro de estimativa nas duas versões.
- **Buffers no nó de scan** (mediana por amostra, nós com ≥ 200 linhas): `Index Scan` 0,099 bloco/linha
  (SB) × 0,462 (QJ); `Index Only Scan` 0,032 × 0,122; `Seq Scan` 0,021 × 0,020. A diferença aparece só
  nos acessos ao heap na ordem do índice, e o `Seq Scan` é igual.
- Exemplo lado a lado, `SUM(final_amount)` no fim da rodada, ~14,8 mil linhas:

  ```
  QJ  Index Scan idx_orders_created_at  rows_plan=74 rows_real=14840 hit=7083
      Index Cond: ((orders.created_at >= $1) AND (orders.created_at < $2))
      $1 = '2026-09-23 00:00:00+00', $2 = '2026-09-26 00:00:00+00'
  SB  Index Scan idx_orders_created_at  rows_plan=73 rows_real=14776 hit=3417
      Index Cond: ((orders.created_at >= $1) AND (orders.created_at < $2))
      $1 = '2026-09-23 00:00:00',    $2 = '2026-09-26 00:00:00'
  ```
  O literal do parâmetro difere (sem offset no SB), mas o `Index Cond` não tem cast em nenhum dos
  dois: mesmo tipo inferido, mesmo instante (sessão em UTC).

## Item 3 — texto normalizado

`resultados/textos_por_operacao.md` lista todos os textos com número de chamadas.

| operação | textos SB-noval | textos QJ | idênticos | diferença literal |
|---|---|---|---|---|
| **get_summary** | 5 | 5 | **5** | nenhuma |
| get_order | 2 | 2 | 0 | SB `SELECT orders.* … WHERE orders.id = $1 LIMIT $2`; QJ `SELECT * … WHERE id = $1`; itens: SB projeta as colunas explícitas, QJ `SELECT *` |
| get_orders_by_customer | 10 | 3 | 1 | SB `order_id IN ($1, …, $n)`, um texto por aridade; QJ `order_id = ANY($1)` |
| create_order | 3 | 2 | 0 | SB tem duas variantes de `INSERT INTO orders` (com/sem `shipping_complement`) e `RETURNING id` |
| insert_status_history | 2 | 1 | 0 | SB 4 ou 5 colunas + `RETURNING id`; QJ sempre 5 |
| update_status | 1 | 1 | 0 | SB reescreve as 14 colunas, inclusive `created_at` e `customer_id`; QJ `SET status, updated_at` |

Todas essas diferenças já tinham sido descritas em `../02_comparacao_por_operacao.md`. Nenhuma altera
blocos por chamada (tabela do item 1). Paginação: `LIMIT/OFFSET` nas duas versões.

## Item 4 — `fetch_size` / prefetch

| driver | versão | configuração efetiva | fonte |
|---|---|---|---|
| r2dbc-postgresql (SB) | 1.0.9 | `fetchSize = sql -> NO_LIMIT` (padrão). Com `NO_LIMIT`, um único `Execute` com fetch-all (`fetchAll`); cursor só com `fetchSize > 0` | `PostgresqlConnectionConfiguration.java:372`, `ExtendedQueryMessageFlow.java:98` |
| Vert.x pg client (QJ) | 4.5.26 | `preparedQuery().execute()` cria `ExtendedQueryCommand` com `fetch = 0` (todas as linhas); cursor só via `cursor()`/`createStream()`, que a app não usa | `ExtendedQueryCommand.java:43` |

Nenhuma das apps define `fetchSize`, cursor ou stream (`grep` em `order-service/*/src/main`). O
`get_summary` devolve no máximo 10 linhas por consulta. O número de viagens de busca é o mesmo, e os
`shared_blks_hit` do `pg_stat_statements` são contados no servidor, independentemente de quantos
`Execute` o cliente mande.

## O que isto não cobre

- **Mecanismo da intercalação não isolado.** A ligação "política do pool → qual backend insere →
  página-alvo" vem do código-fonte e da forma do layout. Não houve rodada trocando a política de
  reuso para confirmar.
- **Latência do `get_summary`:** não explicada. Com 2 réplicas e r1 destoando, a coleta não sustenta
  nem descarta uma diferença real por chamada em F1.
- Só F1. `auto_explain` e `track_planning` ligados, simétricos nas duas condições.
- Os "1,33× / 1,52×" citados na pergunta são **bytes de rede** recebidos/enviados pelo RDS (Enhanced
  Monitoring, coleta 3), não blocos de buffer. Esta coleta não mediu rede.

## Arquivos

| caminho | conteúdo |
|---|---|
| `01_pgss.py`, `02_planos.py`, `03_layout.py`, `04_ordem_insercao.py` | análises (itens 1, 2, layout/EXPLAIN, ordem de inserção) |
| `previa_coleta3/` | prévia feita sobre os logs da coleta 3 antes desta coleta |
| `runner/orquestrador_residuo.sh`, `runner/pos_rodada.sql`, `runner/provisiona_rds.sh` | coleta |
| `taskdefs/` | task definitions registradas |
| `dados/r*-*/` | por rodada: `pg_stat_statements.csv`, `layout_orders.csv` (ctid por linha), `paginas_orders.csv` (pageinspect), `explain_direto_*.txt`, `conexoes.tsv`, `summary.json`, `meta.json` etc. |
| `dados/logs_brutos/` | logs do Postgres (auto_explain) baixados do RDS |
| `resultados/` | todas as tabelas acima |
| `inventario_recursos.txt`, `TEARDOWN.md` | recursos criados e desprovisionamento |

Backup: `s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds/residuo_estrutural/`
(`analysis/` + `runner_disco_20260924.tgz`).
