# Reprodução exploratória na AWS da instabilidade de p95 do Spring Boot no F3 (21/09/2026)

**Não é resultado formal do TCC.** Nada daqui substitui ou altera os CSVs oficiais nem os capítulos.
Mesmo status de `exploratorio_gc_f3/` e `investigacao_instabilidade_f3_setembro/`. Nenhum `.tex`/`.md`
do projeto principal foi tocado. Sem branch.

Hipóteses em teste (do reexame de setembro): (1) custo de consulta crescendo durante o pico com a
tabela `orders` crescendo; (2) amplificação do SB em 1 vCPU real (fila no pool R2DBC, JVM fria);
(3) AZ / vizinho barulhento.

## 1. Ambiente (montado em 21/09/2026, 21:10–21:30 UTC)

Inventário completo para o teardown em `inventario_recursos.txt`. Todos os recursos novos têm a tag
`projeto=tcc-repro-f3`. **Nada oficial foi alterado.** O RDS oficial `order-service-postgres` (1d)
continua de pé e intocado; só li o esquema dele (`pg_dump --schema-only`).

| item | oficial | reprodução | observação |
|---|---|---|---|
| task SB | `order-service-springboot:12`, 1024/2048, `:latest` | `repro-f3-springboot:1`, 1024/2048, `@sha256:276548dd…` | mesmo digest (índice); diferenças em `taskdef_diff_springboot.txt` |
| task QJ | `order-service-quarkus-jvm:10`, `20260616-160138` | `repro-f3-quarkus-jvm:1`, `@sha256:abec3583…` | mesmo digest do tag |
| env | — | só host do banco trocado + `JAVA_OPTS_APPEND` | QJ: a imagem já traz `JAVA_OPTS_APPEND=-Dquarkus.http.host=0.0.0.0`; mantido no início do valor, senão a app escutaria só em localhost |
| log group | `/ecs/order-service-*` | `/ecs/repro-f3-*` | para não misturar com os logs oficiais |
| cluster | `order-service-cluster` (CI enabled) | `repro-f3-cluster` (CI enabled) | lógico; sem efeito de desempenho |
| rede da task | subnet 1c, SG `order-service-fargate-sg`, IP público | idem | task confirmada em us-east-1c, platform 1.4.0 |
| RDS | t3.micro, PG 16.4, 20 GB gp3 3000/125, `order-service-pg16-custom`, subnet group `default`, público, sem backup, sem criptografia | **idem**, AZ escolhida pela AWS: **us-east-1f** | cross-AZ de novo (task 1c ↔ RDS 1f). `AutoMinorVersionUpgrade=false` para travar 16.4 durante o teste |
| esquema | criado fora do Flyway (histórico só tem `<< Flyway Baseline >>`; `db/migration` vazio nas duas apps) | copiado do oficial via `pg_dump` (`esquema_oficial_schema_only.sql`) | diff de colunas/índices/flyway = idêntico |
| `pg_stat_statements` | pré-carregado, extensão não criada | pré-carregado, extensão criada | o custo de rastreamento existe nos dois (hook carregado); a extensão só expõe a view |
| runner | m7i-flex.large, AL2023, 1c, `k6-runner-sg`, k6 v0.45.0 | `i-095b252567fbdadfb`, idem, us-east-1c (use1-az4) | cenário no runner = blob `0ff2140` (mesmo das coletas oficiais) |
| orquestrador | `f3_rerun.sh` no **notebook**, k6 via SSH | `runner/orquestrador.sh` **no runner** via `systemd-run`, IAM role da instância | mesmo fluxo por rodada: stop → run-task → health → TRUNCATE → k6 |

Diferenças inevitáveis, declaradas: RDS novo (cache frio, sem histórico de créditos de CPU; t3 em modo
unlimited não estrangula), orquestração no runner em vez do notebook, amostradores leves durante a
carga (ver §2).

### Configuração real da JVM no Fargate (dos logs de boot, não suposta)

`run-java.sh` monta: `-XX:MaxRAMPercentage=80.0 -XX:+UseParallelGC -XX:MinHeapFreeRatio=10
-XX:MaxHeapFreeRatio=20 -XX:GCTimeRatio=4 -XX:AdaptiveSizePolicyWeight=90 -XX:+ExitOnOutOfMemoryError`,
heap máx. 1640 MB, "Using Parallel". Vale para SB e QJ (mesma imagem base). Registro factual: o
`exploratorio_gc_f3` anotou `UseSerialGC {ergonomic}` a partir de `java -XX:+PrintFlagsFinal`
executado direto, sem o `run-java.sh`. O coletor dos processos oficiais é o Parallel.

## 2. Instrumentação (ligada e confirmada coletando antes de qualquer carga)

| instrumento | config | confirmação (21/09, sem carga) |
|---|---|---|
| Performance Insights | Database Insights **standard**, retenção 7 d | `pi get-resource-metrics db.load.avg` period 1 s devolve pontos |
| Enhanced Monitoring | **1 s** (mínimo), role `repro-f3-rds-monitoring` | `RDSOSMetrics/db-6YS6HH4RVDLLF3GYEWRKEPPNEA` a 1 s; já mostra **steal 3–7 % com o RDS ocioso** |
| Log do Postgres → CloudWatch | export `postgresql` | checkpoints chegando (`log_checkpoints=1`, `log_autovacuum_min_duration=10s` do param group oficial) |
| VPC Flow Logs | VPC inteira, agregação 60 s, formato v7 com `tcp-flags`, `az-id`, `flow-direction`, `ecs-task-id` | registros task↔RDS:5432 com o `ecs-task-id` preenchido |
| log de GC | `-Xlog:async -Xlog:gc*,safepoint:stdout:time,uptime,level,tags` | linhas `[gc…]`/`[safepoint]` no log group da task (SB e QJ) |
| Container Insights | cluster `repro-f3-cluster` | `CpuUtilized` 1 min por família |
| métricas da app (5 s) | SB: `/actuator/metrics/r2dbc.pool.{acquired,pending,idle,allocated}`, `process.cpu.usage`, `system.load.average.1m`, `jvm.threads.live`; QJ: `/q/metrics` | SB: todas expostas. **QJ não expõe métrica do pool** (só CPU/load/threads) |
| Postgres (5 s / 60 s) | `pg_stat_activity` agrupado por wait event + `n_live_tup`; `pg_stat_statements` top 25 | — |
| sonda TCP (1 s) | runner → RDS:5432 e runner → task:8081, tempo de connect | — |

Desvios do log de GC em relação ao `exploratorio_gc_f3`: saída em **stdout** (o arquivo dentro da task
Fargate não é recuperável sem ECS Exec, que exigiria mudar a task) e `-Xlog:async`, para a escrita no
stdout não bloquear a JVM se o driver `awslogs` atrasar.

**Limites a registrar já:** VPC Flow Logs **não medem latência** (não há campo de RTT). A latência de
rede vem só da sonda TCP do runner, que está na mesma AZ da task (1c → 1f), ou seja, é um proxy do
caminho, não o caminho da própria task. O Fargate não expõe steal nem throttling de CPU da task por
fora. Isso só seria visível com um sidecar lendo `/proc/stat` e o endpoint de stats, o que muda a task.
**Não foi feito.**

Métricas de 5 s adicionam ~7 req/5 s no SB (≈0,6 % da taxa de pico). É intrusão declarada.

## 3. Teste de desacoplamento (item 6)

`systemd-run` (unit de sistema, `--uid=ec2-user`) com um heartbeat a cada 2 s:
1. `kill -9` no cliente SSH que disparou: heartbeat continuou.
2. `sudo loginctl terminate-user ec2-user` (derruba todas as sessões e o sshd delas; a conexão caiu
   com "closed by remote host"): a unit continuou `active`, heartbeat de 24 → 33 linhas, última
   escrita 1 s antes da checagem.

## 4. Execução (21/09/2026)

- Validação de ~2 min (21:38Z): 3549/3550 iterações, 0 dropped, 0 falha; todos os instrumentos
  com dados. Arquivada em `runner_out/_smoke_validacao/`, fora da análise.
- Carga real disparada às 21:43:48Z via `systemd-run`. **Só SB r1–r3 completaram.** Às 23:06Z o ECS
  devolveu `ServerException: Internal Error` em todo `RunTask` por ~70 s (CloudTrail, 15 chamadas).
  O orquestrador não esperava para tentar de novo: SB r4, r5 e QJ r1–r3 falharam sem iniciar
  carga, e ele saiu. O autostop parou o RDS às 01:07:50Z e o runner logo depois, como previsto.
  Corrigido no orquestrador: `RunTask` com até 10 tentativas e backoff.
- **Não há controle Quarkus nesta reprodução.**

| rodada | início da carga (UTC) | iters | dropped | p50 | p95 | p99 | max (ms) | % > 1 s |
|---|---|---|---|---|---|---|---|---|
| SB r1 | 21:45:59 | 208.652 | 147 | 15,2 | **2403** | 4789 | 8965 | 12,3 |
| SB r2 | 22:13:45 | 208.717 | 82 | 11,8 | **825** | 3592 | 9397 | 4,3 |
| SB r3 | 22:40:55 | 208.129 | 670 | 12,7 | **3149** | 6739 | 11229 | 11,0 |

**O problema reproduziu nas 3 de 3 rodadas**, na mesma faixa das oficiais ruins (326–2108 ms).

## 5. Análise cruzada (item 9) — `analisa.py` → `minuto_a_minuto.csv`, `pi_wait_events.csv`

Minuto 0 = início da carga; pico a 240 it/s nos minutos 7–16.

### O que acontece, em ordem

1. **O custo das consultas de resumo cresce com a tabela.** `orders` cresce ~4.700 linhas/min no
   pico (14 mil no min 7 → 55 mil no min 16). As 5 agregações de `get_summary` (`SUM/COUNT ... FROM
   orders WHERE created_at >= $1 AND created_at < $2`, ~95 % do tempo de execução do banco) vão de
   **~3–7 ms/chamada no min 2 para ~100 ms no min 8, ~290 ms no min 12-13 e 1,2–1,5 s no min 16-17**
   (deltas por minuto do `pg_stat_statements`, r1 e r3 iguais).
2. **A CPU do RDS sobe junto até saturar.** Enhanced Monitoring (1 s): 49 % no min 7 → 80 % no
   min 12 → **92–99 % nos min 14–16**. PI: carga média ativa (AAS) de ~1 no início do pico →
   **13–30 no fim, em uma instância de 2 vCPU**, quase toda em `CPU` (≈10–12 AAS). Esperas não-CPU
   pequenas (`LWLock:WALWrite` ~1,4, `ClientRead` ~0,9, `IO:WALSync` ~0,4). Não é lock nem disco.
3. **Com o banco saturado, o pool R2DBC esgota.** `r2dbc.pool.pending` fica em 0 até o min 12,
   depois 18–150 (min 13), 450–650 (14–15), **1200–1600 (16–17)**. É aí que o p95/min salta:
   r1 374 ms (min 13) → 2,3 s (14) → 5,8 s (16); r3 183 ms → 1,7 s → 6,7 s. Exatamente a janela
   "minutos ~13–17" das rodadas oficiais.
4. **Recuperação imediata** quando a taxa cai para 48 (min 18): CPU do RDS 52 %, p95 27–50 ms,
   pool 0, apesar de a tabela já ter 62 mil linhas. A 48 it/s o custo por chamada (~300–400 ms)
   cabe na CPU; a 240, não.

### O que foi descartado nesta reprodução

| hipótese | evidência |
|---|---|
| GC | pausas máx. de 20–95 ms até o min 15; as de 340–570 ms aparecem só **no min 16–17**, depois do início da degradação (min 14): são efeito do acúmulo de requisições na heap, não gatilho |
| CPU da task / 1 vCPU | `CpuUtilized` 480–750 de 1024 unidades no pico; não satura |
| rede / cross-AZ | sonda TCP runner→RDS p50 0,9–1,0 ms, estável; máx. por minuto sem pico na janela ruim; Flow Logs sem RST/SYN anômalo |
| vizinho barulhento no RDS | steal médio 2,7–4,0 %, sem subida na janela ruim |
| créditos de CPU do RDS | instância nova em modo unlimited com `CPUCreditBalance` 0 e surplus 2–40: não há estrangulamento no unlimited |

### Comparação com o oficial (CloudWatch `CPUUtilization` do RDS no pico)

- Reprodução: 1 min, média min 7–16 = **62 %** nas 3 rodadas; min 12–16 = 77–79 %, máx. 90–92 %.
- Oficial 02/09, SB ruim (5 min): 66–77 %. Oficial 05/09, SB limpo: **63–65 %**. QJ e QN: **50–58 %**.

A reprodução **não** foi mais pesada que o oficial; a carga média no banco está na mesma faixa. A
leitura anterior de "CPU do RDS igual entre rodadas boas e ruins" usava a **média do pico**, que
esconde o joelho: o sistema passa a maior parte do pico abaixo da saturação e só a cruza nos
últimos 3–4 min, quando a tabela já está grande. Perto de 100 %, poucos pontos de CPU a mais ou a
menos decidem se a fila explode ou não.

### Interpretação (inferência, não medida diretamente)

Mecanismo proposto para a instabilidade: **consultas agregadas sobre uma tabela que cresce durante
o pico levam a CPU do db.t3.micro ao limite no fim do pico; o SB, que gera ~1,2–1,3× mais CPU no
RDS que o Quarkus (memória `rds-cpu-por-rodada` e tabela acima), fica na borda da saturação. O
Quarkus fica abaixo dela.** Pequenas variações de dia/instância (steal do host do RDS, colocação)
empurram o SB para um lado ou para o outro. Isso é compatível com o agrupamento por dia. É a
hipótese 1 do plano, com a 2 como amplificador (fila no pool) e a 3 sem suporte.

Limites: (a) sem controle Quarkus nesta reprodução, a afirmação "o QJ fica abaixo do joelho" vem só
dos dados oficiais; (b) 3 rodadas, um dia, uma instância RDS; (c) não medi por que o SB custa mais
CPU no banco (número de consultas por requisição? prepared statements?); (d) não verifiquei
diretamente se as 5 consultas de resumo varrem a tabela inteira (`EXPLAIN` não coletado).

## 6. Dia 2 (22/09/2026) — refazer as 8 rodadas

As 3 rodadas do dia 1 ficam preservadas (`runner_out/` local, `runner_out_dia1/` no S3, raw em
`/var/tmp/dia1/` no runner). O dia 2 grava em `runner_out_dia2/`.

Proteções acrescentadas ao orquestrador depois do incidente de 21/09:
- Toda chamada AWS passa por `awsr` (até 9 tentativas, 10–80 s) mais o retry nativo do CLI
  (`AWS_RETRY_MODE=adaptive`, `AWS_MAX_ATTEMPTS=10`). Testado com um `aws` falso que falha 3 vezes
  (recupera) e 99 vezes (desiste limpo).
- **Rodada só é refeita por falha de infraestrutura antes da carga** (RDS indisponível, task não
  sobe, health, TRUNCATE que não zera `orders`): até 6 tentativas com 2, 4, 6, 8, 10 min de espera.
  A tentativa falha é arquivada (`_tentativa_falha_*`), não apagada. **Uma rodada em que o k6 rodou é
  sempre registrada**, mesmo ruim ou com a task morta no meio (fica um AVISO). Refazer rodada ruim
  enviesaria o resultado para o lado do que se quer medir.
- Task que vai para `STOPPED` não é esperada de novo: o motivo (`stoppedReason`) vai para o log.
- Marcador `DONE` por rodada. Serviço com `Restart=on-failure`; o autostop de uma execução anterior é
  desarmado ao iniciar; `trap` em TERM/INT garante parar as tasks e armar o autostop.

Validação (09:17–09:31Z), com SB **e QJ** em taxa baixa: 3549/3550 iterações cada, 0 dropped,
0 falha; amostrador `/q/metrics` do QJ confirmado. **Na primeira task do SB aconteceu uma falha real
de infra**: `CannotPullContainerError ... not found` para o digest `276548dd…`, que existe e está
íntegro no ECR (sem lifecycle policy nem remoção no CloudTrail; o pull seguinte funcionou). Foi
transitório do ECR, e o retry de rodada recuperou sozinho.

Carga real do dia 2 disparada às 09:34:47Z.

### Resultado do dia 2 (8/8 rodadas, todas na 1ª tentativa, 09:36–13:11Z)

| rodada | iters | dropped | p50 | p95 | p99 | max (ms) | % > 1 s |
|---|---|---|---|---|---|---|---|
| SB r1 | 208.799 | 0 | 11,3 | 134 | 880 | 3039 | 0,80 |
| SB r2 | 208.661 | 138 | 11,3 | 337 | 3582 | 9378 | 3,67 |
| SB r3 | 208.799 | 0 | 11,2 | **56** | 646 | 2826 | 0,49 |
| SB r4 | 208.799 | 0 | 10,4 | **51** | 373 | 3000 | 0,24 |
| SB r5 | 208.526 | 273 | 11,8 | **1848** | 4675 | 10392 | 7,10 |
| QJ r1 | 208.799 | 0 | 5,3 | 31,5 | 441 | 3798 | 0,30 |
| QJ r2 | 208.799 | 0 | 5,2 | 20,9 | 275 | 3739 | 0,41 |
| QJ r3 | 208.799 | 0 | 5,2 | 15,6 | 139 | 894 | 0,00 |

Zero falha de HTTP em todas. **Os dois eixos da instabilidade oficial se reproduziram:** variação
entre rodadas do mesmo dia (51 → 1848 ms com tudo igual) e efeito de dia (dia 1 inteiro pior).

## 7. Diagnóstico com as 11 rodadas (8 SB + 3 QJ) — `resumo_pico_por_rodada.csv`

Agregados da janela de pico (min 7–17), CPU do RDS pelo Enhanced Monitoring de 1 s:

| dia | rodada | p95 | CPU RDS máx | min ≥95 % | AAS máx | pool pend. máx | p95 get_summary | GC máx | steal |
|---|---|---|---|---|---|---|---|---|---|
| 1 | SB r1 | 2403 | 99,8 | 2 | 29,4 | 1197 | 3622 | 484 | 2,5 |
| 1 | SB r2 | 825 | 97,1 | 1 | 26,3 | 1284 | 3687 | 341 | 3,7 |
| 1 | SB r3 | 3149 | 98,7 | 1 | 30,0 | 1595 | 4641 | 568 | 2,8 |
| 2 | SB r5 | 1848 | 96,4 | 1 | 23,8 | 1467 | 4089 | 608 | 0,22 |
| 2 | SB r2 | 337 | 93,9 | 0 | 19,1 | 1390 | 3561 | 54 | 0,13 |
| 2 | SB r1 | 134 | 92,0 | 0 | 14,6 | 358 | 2399 | 56 | 0,38 |
| 2 | SB r3 | 56 | 90,8 | 0 | 12,2 | 349 | 2192 | 51 | 0,06 |
| 2 | SB r4 | 51 | 91,8 | 0 | 11,4 | 254 | 2023 | 60 | 0,14 |
| 2 | QJ r1 | 31,5 | **79,0** | 0 | 7,9 | — | 2081 | 22 | 0,31 |
| 2 | QJ r2 | 20,9 | **80,9** | 0 | 9,4 | — | 2706 | 6 | 0,29 |
| 2 | QJ r3 | 15,6 | **76,8** | 0 | 5,3 | — | 350 | 4 | 0,34 |

Spearman do p95 nas 8 rodadas SB: **AAS máx ρ=0,98**, CPU RDS máx 0,93, p95 do `get_summary` 0,93,
minutos ≥95 % 0,86, fila do pool 0,83, GC máx 0,76, CPU da task 0,57.

**1. O gatilho é a CPU do banco, não a aplicação.** As agregações de `get_summary` são 100 % servidas
do cache (`blks_read` = 0 em todas as rodadas): é trabalho de CPU puro sobre a tabela que cresce. O
custo por chamada segue a mesma curva em todas as rodadas até o min ~10 (30 ms no min 6 → ~130 ms no
min 10) e só então diverge, quando a CPU satura: no min 17 é 485 ms na melhor rodada e 1620 ms na
pior. A CPU da task nunca passa de 750 de 1024 unidades.

**2. O Quarkus fica abaixo do joelho — agora com controle medido.** CPU do RDS máxima de 77–81 % e
AAS de 5–9, contra 91–100 % e 11–30 do Spring Boot, na **mesma** taxa e no mesmo banco. Nenhuma
rodada QJ chegou a 90 %. Isso confirma no ambiente do teste o que os dados oficiais sugeriam
([[rds-cpu-por-rodada]]): o SB gera mais CPU no banco e opera na borda da saturação; o Quarkus, não.

**3. Existe um limiar visível.** Nenhuma rodada com CPU máxima < 95 % passou de p95 337 ms; todas as
4 rodadas com algum minuto ≥95 % ficaram entre 825 e 3149 ms. A degradação é de fila, não linear.

**4. O efeito de dia acompanha o steal do host do RDS.** Dia 1: steal médio 2,5–3,7 %, 3 de 3 rodadas
ruins. Dia 2 (mesma instância, parada e religada entre os dias, portanto outro host físico): steal
0,05–0,38 %, 1 de 5 claramente ruim. É correlação com n=2 dias, não prova: o steal reduz a folga de
CPU de uma instância que já opera perto do limite. Dentro do dia 2 o steal **não** ordena as rodadas,
então ele explica o deslocamento entre dias, não a variação entre rodadas.

**5. GC segue descartado como causa.** Correlação alta (0,76) mas ordem temporal invertida: na SB r5,
o p95 do minuto 16 já é 3600 ms com pausa máxima de 58 ms; a pausa de 608 ms só aparece no minuto 17.
Pausa grande é consequência do acúmulo de requisições na heap.

**6. `automatic analyze` não é gatilho.** Aparece nas 4 piores rodadas e em nenhuma boa, o que parece
um sinal forte — mas o Postgres só registra as execuções acima de `log_autovacuum_min_duration` (10 s,
do param group oficial), e os eventos caem no min ~17, depois do início da degradação. É marcador de
banco saturado. Checkpoints ocorrem a cada 5 min em todas as rodadas, boas e ruins, sem relação.

**7. Rede e AZ seguem sem suporte.** Sonda TCP runner→RDS (cross-AZ, 1c→1f) com p50 de 0,83–0,96 ms
em todas as rodadas; sem pico nas janelas ruins; Flow Logs sem RST nem anomalia.

### Conclusão (exploratória)

A instabilidade do p95 do Spring Boot no F3 é **saturação de CPU do `db.t3.micro`**, provocada pelas
agregações de `get_summary` sobre a tabela `orders` que cresce durante o pico. O Spring Boot opera
perto do joelho dessa curva e o Quarkus não, então pequenas variações de folga — entre dias, por
contenção no host do RDS, e entre rodadas — decidem se a fila explode. A leitura anterior de que "a
CPU do RDS era igual entre rodadas boas e ruins" vinha de médias do pico, que escondem o joelho.

**O que isto não fecha:** (a) por que o SB custa 1,2–1,3× mais CPU no banco que o Quarkus (número de
consultas por requisição? prepared statements? não medido); (b) o efeito de dia tem n=2; (c) não
rodei `EXPLAIN` nas consultas de resumo, então "varre a tabela inteira" segue inferência a partir do
custo crescer com as linhas; (d) 3 rodadas de Quarkus, um dia só.
