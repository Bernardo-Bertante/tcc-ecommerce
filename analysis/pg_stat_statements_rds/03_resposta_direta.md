> **SUPERADO por [`06_resultado_consolidado.md`](06_resultado_consolidado.md).** Esta resposta usou
> só `total_exec_time` (tempo de parede) de uma rodada por versão. As coletas 2 e 3 mostram que a
> maior parte do excesso de CPU vem da validação de pool, não do `get_summary`. Mantido como registro.

# Resposta direta (coleta 1): consulta estruturalmente mais cara, ou a mesma consulta executando mais devagar?

**A segunda.** Na carga F1 medida aqui, 94,1 % da diferença de tempo de execução no banco vem de
consultas que são **textualmente idênticas** entre Spring Boot e Quarkus JVM, chamadas o **mesmo
número de vezes**, com os **mesmos parâmetros**, produzindo o **mesmo plano de execução**, varrendo
o **mesmo número de linhas** — e que ainda assim levam mais tempo no Spring Boot.

## A evidência, em ordem

1. **A diferença total reproduziu o fenômeno oficial.** Tempo de execução acumulado no banco:
   Spring Boot 90.311 ms × Quarkus JVM 65.869 ms = **1,371×**, dentro da faixa de 21–35 % de
   `fase5_rds_cpu_por_rodada.csv`. As cargas foram equivalentes: 43.229 iterações e 48.533
   requisições nas duas, 0 % de falhas, tabela final de 13.958 × 13.944 linhas.

2. **O gap está concentrado em uma operação.** `GET /orders/summary` responde por **94,1 %**
   (+23.007 ms de +24.442 ms). Todo o resto somado — incluindo as 144 mil validações de pool a
   mais — dá 5,9 %.

3. **Nessa operação, a consulta não é diferente.** As 5 agregações de `get_summary` têm texto
   byte a byte igual nas duas versões, são chamadas 864 vezes cada (4.320 no total) nas duas, e
   recebem o mesmo intervalo de datas (`2026-09-22` → `2026-09-25`, diferindo só na forma do
   literal que cada driver envia).

4. **O plano também não é diferente.** Nas duas versões, as 4 agregações pesadas usam
   `Index Scan` sobre `idx_orders_created_at` e o `COUNT(*)` usa `Index Only Scan` sobre o mesmo
   índice. Não há scan sequencial de um lado e índice do outro — em nenhuma das operações do mix.

5. **O volume varrido também não é diferente.** Comparando ao mesmo tempo decorrido de carga
   (as agregações ficam mais caras conforme `orders` cresce), as linhas varridas são praticamente
   iguais: 1.326/1.202, 4.383/4.302, 7.164/6.794, 10.298/10.326, 13.038/12.673.

6. **Sobra o tempo por unidade de trabalho.** Normalizando por linha varrida, o Spring Boot gasta
   mais em 4 das 5 agregações (razões de 1,14×, 1,21×, 1,33× e 1,38×; a quinta dá 0,99×).

## O que isso não explica, e que ficou aberto

Esta coleta mostra **onde** está o custo, não **por que** a mesma consulta com o mesmo plano
custa mais. Dois fatos medidos apontam em direções opostas e não se resolvem com os dados aqui:

- O Spring Boot toca **2,6× menos blocos por linha varrida** que o Quarkus nas agregações
  (≈174 × ≈450 blocos por 1.000 linhas, consistente nas 5 consultas) — ou seja, faz **menos**
  acesso a buffer, todos em cache (`shared_blks_read` = 0) — e mesmo assim gasta mais tempo.
  No agregado da rodada isso aparece invertido: 5,27 M de blocos no SB contra 12,18 M no QJ.
- O Spring Boot emite **o dobro de statements** (288.828 × 144.408), quase todos vindos das
  144.394 validações de pool (`SELECT $1`, 0 blocos, 0,0059 ms cada). Dentro de
  `total_exec_time` isso pesa só 849 ms, mas `pg_stat_statements` **não** mede parse/bind,
  round-trip de protocolo nem ocupação de backend — que é justamente onde esse tipo de tráfego
  cobra caro. Esta coleta não consegue afirmar nem descartar essa via.

Também não foi medido tempo de **planejamento** (`track_planning` está desligado por default,
`plans` e `total_plan_time` vieram zerados). Isso importa especificamente para o achado das
7 aridades distintas de `IN (...)` que o Spring Boot gera contra o `= ANY($1)` único do Quarkus:
o custo dessas 7 entradas separadas, se existir, estaria no planejamento, não na execução.

## Limite metodológico que pesa sobre a resposta

Foi **uma rodada por versão, em ordem fixa** (Spring Boot 00:24–00:40, Quarkus 00:41–00:57),
sem repetição. O sentido do resultado bate com as 15 rodadas oficiais, mas esta coleta sozinha
não separa efeito de framework de efeito de ordem ou de momento. Para fechar isso seria preciso
alternar a ordem e repetir — o que não foi feito aqui.
