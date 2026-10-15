# Comparação por tipo de consulta — Spring Boot × Quarkus JVM (item 8)

**Investigação exploratória.** Não é resultado formal do TCC, não altera nenhum CSV oficial nem
capítulo. Mesmo status de `exploratorio_gc_f3/` e `reproducao_f3_instabilidade/`. Sem branch,
nenhum `.tex`/`.md` do projeto principal tocado.

## Como foi coletado

Uma rodada por versão, no mesmo RDS (`repro-f3-postgres`, db.t3.micro, PG 16.4, param group cópia
do oficial), task Fargate fresca 1024/2048, `TRUNCATE` das três tabelas e
`pg_stat_statements_reset()` antes de cada uma. Carga F1, 48 req/s, mix oficial de endpoints,
1 min de rampa + 14 min de platô + 1 min de descida.

| | Spring Boot | Quarkus JVM |
|---|---|---|
| janela (UTC) | 00:24:28 → 00:40:38 | 00:41:28 → 00:57:35 |
| iterações k6 | 43.229 | 43.229 |
| requisições HTTP | 48.533 | 48.533 |
| falhas | 0,00 % | 0,00 % |
| `orders` ao final | 13.958 linhas | 13.944 linhas |
| p50 / p95 HTTP | 5,3 / 18,0 ms | 2,8 / 10,2 ms |

As cargas são equivalentes no nível da requisição: mesmo número de iterações, mesmo número de
requisições, mesma tabela final. `auto_explain` com configuração idêntica nas duas
(`auto_explain_settings.txt` de cada rodada é byte a byte igual).

## Resultado agregado

Tempo total de execução dentro do banco, somando todas as consultas da rodada:

| | chamadas | tempo de execução | blocos lidos | consultas distintas |
|---|---|---|---|---|
| Spring Boot | 288.828 | **90.311 ms** | 5.272.963 | 27 |
| Quarkus JVM | 144.408 | **65.869 ms** | 12.183.621 | 22 |
| razão SB/QJ | 2,00× | **1,371×** | 0,43× | — |

O 1,371× cai dentro da faixa de 21–35 % dos dados oficiais (`fase5_rds_cpu_por_rodada.csv`), o que
indica que esta rodada exploratória reproduziu o fenômeno que se queria investigar.

## Decomposição da diferença

Diferença absoluta: 24.442 ms.

| operação | SB (ms) | QJ (ms) | delta | % do gap |
|---|---|---|---|---|
| **get_summary** | 74.408,3 | 51.401,1 | **+23.007,2** | **94,1 %** |
| infra_pool_validacao | 849,4 | 0,0 | +849,4 | 3,5 % |
| create_order | 7.165,2 | 6.726,9 | +438,3 | 1,8 % |
| insert_status_history | 3.730,1 | 3.550,7 | +179,4 | 0,7 % |
| get_order | 2.044,3 | 1.890,1 | +154,2 | 0,6 % |
| get_orders_by_customer | 1.180,8 | 1.179,7 | +1,1 | 0,0 % |
| update_status | 923,5 | 976,8 | −53,3 | −0,2 % |
| infra_rds_monitoramento | 0,0 | 136,1 | −136,1 | −0,6 % |

## Número de chamadas por operação

**Todas as operações funcionais têm contagem de chamadas idêntica nas duas versões:**

| operação | SB | QJ |
|---|---|---|
| get_order | 54.490 | 54.490 |
| create_order | 41.832 | 41.832 |
| get_orders_by_customer | 19.440 | 19.440 |
| insert_status_history | 19.128 | 19.128 |
| update_status | 5.184 | 5.184 |
| get_summary | 4.320 | 4.320 |
| **infra_pool_validacao** | **144.394** | **4** |

A única diferença de contagem está fora do mix de endpoints: a consulta de validação de conexão
do pool. Ela sozinha responde pelo dobro de chamadas totais do Spring Boot.

## Diferenças estruturais na consulta em si

Independentes de tempo — são diferenças de texto/forma do SQL gerado.

### 1. Validação de conexão do pool: 144.394 × 4

| | consulta | chamadas | tempo total | blocos |
|---|---|---|---|---|
| SB | `SELECT $1` | 144.394 | 849,4 ms | 0 |
| QJ | `SELECT $1` | 4 | 0,0 ms | 0 |

O pool R2DBC do Spring Boot valida a conexão a cada aquisição; o cliente reativo do Quarkus não.
São ~149 statements por segundo a mais, com 0 blocos lidos e 0,0059 ms de execução média cada.
O custo dentro de `total_exec_time` é pequeno (3,5 % do gap); o custo de ida-e-volta de protocolo
e de ocupação de backend **não** está medido aqui.

### 2. `order_items` por lista: 7 statements no SB, 1 no QJ

No fluxo `GET /orders/customer/{id}`, os dois buscam os itens dos pedidos da página em lote.

- **SB** gera `... WHERE order_id IN ($1, $2, ..., $n)` — **um texto de consulta diferente para cada
  aridade da lista**. Aparecem 7 no dump: 2.457, 1.520, 1.158, 827, 301, 184 e 33 chamadas.
  Cada aridade é um `queryid` distinto, planejado e cacheado separadamente.
- **QJ** gera `SELECT * FROM order_items WHERE order_id = ANY($1)` — **um único statement**,
  qualquer que seja o tamanho da lista.

Total de chamadas é o mesmo (6.480), e o custo agregado da operação é praticamente idêntico
(1.180,8 ms × 1.179,7 ms). A diferença é de forma, não de custo, nesta carga.

### 3. `UPDATE orders`: linha inteira × 3 colunas

- **SB**: `UPDATE orders SET customer_id = $1, status = $2, total_amount = $3, discount_amount = $4,
  final_amount = $5, shipping_zip_code = $6, shipping_street = $7, ... WHERE id = $n` — reescreve
  as 14 colunas, inclusive `customer_id`, que é indexado (`idx_orders_customer_id`).
- **QJ**: `UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3`.

Apesar da diferença, o custo é o mesmo: 0,178 ms × 0,188 ms de média, mesmo plano
(`Index Scan` em `orders_pkey`), 3 blocos. **SB é ligeiramente mais barato aqui** (−53,3 ms no total).

### 4. `INSERT`: variantes a mais no SB

- `INSERT INTO orders`: SB usa **dois** textos distintos (9.296 + 4.648 chamadas); QJ usa **um** (13.944).
- `INSERT INTO order_status_history`: SB usa **dois** (4 colunas sem `previous_status`, 13.944; e
  5 colunas com `previous_status`, 5.184); QJ usa **um** de 5 colunas para os dois fluxos (19.128).
- SB acrescenta `RETURNING id` em todos os seus INSERTs; QJ não usa `RETURNING`.

Totais idênticos (13.944 e 19.128). Custo: create_order 1,07×, insert_status_history 1,05× — ambos
pequenos em valor absoluto.

### 5. `GET /orders/{id}`: um `LIMIT` a mais no SB

- **SB**: `SELECT orders.* FROM orders WHERE orders.id = $1 LIMIT 2`
- **QJ**: `SELECT * FROM orders WHERE id = $1`

`id` é chave primária, então o `LIMIT 2` é redundante. Os dois usam `Index Scan` em `orders_pkey`,
`dur_p50` de 0,029 ms nas duas. Sem efeito mensurável.

### 6. `GET /orders/summary`: consultas **idênticas**

As 5 agregações têm **texto byte a byte igual** nas duas versões (conferido por comparação de
conjuntos: `SB: 5, QJ: 5, idênticos: True`), com o mesmo número de chamadas (864 cada, 4.320 no total).

Os parâmetros também são o mesmo instante:

```
springboot   74x  $1 = '2026-09-22 00:00:00',    $2 = '2026-09-25 00:00:00'
quarkus-jvm  74x  $1 = '2026-09-22 00:00:00+00', $2 = '2026-09-25 00:00:00+00'
```

(diferença apenas na forma do literal enviado pelo driver — mesmo ponto no tempo; a janela cobre
toda a tabela produzida durante a rodada.)

## Planos de execução (auto_explain, `sample_rate = 0,02`)

10.527 planos capturados dentro das janelas. Detalhe completo em `resultados/planos_por_operacao.txt`;
uma linha por plano em `resultados/amostras_planos.csv`; planos JSON íntegros em `planos/`.

| operação | plano SB | plano QJ | dur p50 SB | dur p50 QJ |
|---|---|---|---|---|
| get_order (orders) | `Index Scan` / `orders_pkey` | `Index Scan` / `orders_pkey` | 0,029 ms | 0,029 ms |
| get_order (items) | `Bitmap Heap Scan` | `Bitmap Heap Scan` | 0,023 ms | 0,021 ms |
| create_order | INSERT (sem scan) | INSERT (sem scan) | 0,200 ms | 0,192 ms |
| by_customer (orders) | `Bitmap Heap Scan` / `idx_orders_customer_id` | idem | 0,061 ms | 0,056 ms |
| by_customer (count) | `Index Only Scan` / `idx_orders_customer_id` | idem | 0,029 ms | 0,030 ms |
| by_customer (items) | `Bitmap Heap Scan` | `Bitmap Heap Scan` | 0,049–0,082 ms | 0,049 ms |
| update_status | `Index Scan` / `orders_pkey` | `Index Scan` / `orders_pkey` | 0,122 ms | 0,125 ms |
| get_summary (4 agregações) | `Index Scan` / `idx_orders_created_at` | `Index Scan` / `idx_orders_created_at` | 12,3–17,0 ms | 9,8–11,7 ms |
| get_summary (`COUNT(*)`) | `Index Only Scan` / `idx_orders_created_at` | `Index Only Scan` / `idx_orders_created_at` | 3,3 ms | 3,5 ms |

**Nenhuma operação tem escolha de plano diferente entre os frameworks.** Não há scan sequencial de
um lado e índice do outro: os mesmos operadores, sobre os mesmos índices, nos dois.

## O `get_summary` em detalhe (94 % do gap)

Como o custo dessas agregações cresce com a tabela ao longo da rodada, a comparação só vale a
tamanho de tabela equivalente. Agrupando as amostras de plano por tempo decorrido desde o início
da carga:

| faixa (s) | SB n | SB linhas varridas | SB dur | QJ n | QJ linhas varridas | QJ dur | razão dur |
|---|---|---|---|---|---|---|---|
| 0–200 | 16 | 1.326 | 1,68 ms | 22 | 1.202 | 2,07 ms | 0,81 |
| 200–400 | 22 | 4.383 | 12,20 ms | 22 | 4.302 | 7,80 ms | 1,56 |
| 400–600 | 15 | 7.164 | 11,32 ms | 14 | 6.794 | 8,30 ms | 1,37 |
| 600–800 | 19 | 10.298 | 22,33 ms | 19 | 10.326 | 23,51 ms | 0,95 |
| 800–1000 | 22 | 13.038 | 34,34 ms | 15 | 12.673 | 24,60 ms | 1,40 |

**As linhas varridas são praticamente iguais em cada faixa** — a tabela cresce do mesmo jeito nas
duas rodadas e as duas varrem o mesmo volume. O que difere é o tempo.

Blocos por linha varrida (mediana por amostra, agregações de summary acima de 2.000 linhas):

| consulta | SB blocos/1k linhas | QJ blocos/1k linhas | SB µs/linha | QJ µs/linha |
|---|---|---|---|---|
| `status, COUNT(*)` | 175,0 | 446,0 | 1,735 | 1,520 |
| `customer_id, SUM, COUNT` | 173,9 | 462,6 | 2,105 | 1,735 |
| `CAST(... AS DATE), SUM` | 172,6 | 461,5 | 2,153 | 1,620 |
| `COUNT(*)` | 48,8 | 118,1 | 0,621 | 0,449 |
| `SUM(final_amount)` | 174,1 | 440,1 | 1,778 | 1,790 |

O Spring Boot toca **2,6× menos blocos por linha varrida** e ainda assim gasta mais tempo por
linha em 4 das 5 consultas. Todos os acessos são `shared_blks_hit` (cache), `shared_blks_read` = 0.

## Limites desta medição

- **Uma rodada por versão, em ordem fixa** (SB primeiro, QJ depois). Não há repetição, então
  não dá para separar efeito de versão de efeito de ordem/momento dentro desta coleta. O sentido
  do resultado coincide com o das 15 rodadas oficiais, mas isso é coincidência de sentido, não
  replicação.
- `pg_stat_statements` mede tempo **dentro da execução do statement**. Não inclui parse/bind/
  round-trip de protocolo, tempo de conexão ociosa, nem o custo de backend por statement. As
  144 mil validações do pool aparecem aqui como 849 ms, o que **não** é o custo total que elas
  impõem ao servidor.
- `track_planning` está desligado (default), então `plans` e `total_plan_time` vêm zerados: esta
  coleta **não mede tempo de planejamento**. Isso importa para o item das 7 aridades de `IN`.
- Planos são amostra de 2 % (`auto_explain.sample_rate`), escolhida para não contaminar os tempos
  do `pg_stat_statements` — ver `01_desenho_instrumentacao.md`. Para `get_summary` são ~90 planos
  por versão, o que é pouco para regressão (as regressões de duração por linha ficaram com r entre
  0,10 e 0,92 e sinal inconsistente; por isso a comparação acima é por faixa, não por ajuste).
- A instância é `db.t3.micro` (2 vCPU). A carga F1 a 48 req/s deixa o banco longe da saturação
  (tempo de execução acumulado / tempo de parede ≈ 0,09 para SB e 0,07 para QJ), diferente do
  cenário F3 onde a CPU do RDS satura.
