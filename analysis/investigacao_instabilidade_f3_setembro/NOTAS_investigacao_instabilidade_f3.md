# Reexame da investigação de 31/08–06/09/2026 sobre a instabilidade do Spring Boot no F3 (21/09/2026)

**Não é resultado formal do TCC.** Reexame documental, **sem nova carga**: arquivos locais, git,
transcrição da sessão original do Claude Code e telemetria ainda retida na conta AWS
(`--profile pessoal`, 776648109551, us-east-1). Nenhum `.tex` ou `.md` do projeto principal foi
alterado. Mesmo status de `exploratorio_gc_f3/` e `exploratorio_pilha_fargate/`.

## Resposta curta

1. **Não surgiu uma causa nova.** Nenhuma fonte retida mostra algo diferente entre as rodadas ruins
   e as boas, e a resolução disponível hoje (5 min) não resolve um evento de segundos.
2. **O que muda é o enquadramento**, e com evidência:
   - A instabilidade é **agrupada por dia**, não por rodada. Em 02/09 as **5 de 5** rodadas do
     Spring Boot foram ruins (as 3 oficiais **mais** as 2 descartadas: p95 326/1022/874/2108/1145 ms).
     Em 05/09 as **3 de 3** foram limpas (sonda 73, r4 73, r5 94 ms). Em julho as 5 de 5 ficaram
     entre 150 e 1008 ms. Das 13 rodadas de F3 do Spring Boot que existem, **as 3 limpas são todas
     do mesmo bloco (sábado, 05/09, 21:30–23:00 UTC)**. O estado "limpo" é a exceção.
   - Dentro de cada rodada, a degradação é **episódica e aparece na segunda metade do pico**
     (≈ minutos 13–17 de carga). O mesmo ponto aparece, bem mais fraco, nas rodadas boas do Spring
     Boot e no Quarkus. Parece haver duas camadas: um **gatilho comum no fim do pico** e uma
     **amplificação** que é muito maior no Spring Boot e muito maior em 02/09.
3. A frase do guia ("confirmado como variância... pausa de GC / event loop saturado") **não
   reflete o que a investigação original concluiu**. O relatório original chamou isso de inferência
   "sem evidência dura" e apontou como candidato mais provável a variância de host / vizinho
   barulhento do Fargate. Ver seção A.

---

## A. O que a investigação de 31/08–06/09 de fato examinou

### Fontes recuperadas

| fonte | o que tem |
|---|---|
| git (commits de 31/08 a 06/09, todos os branches, reflog, stash) | Nenhum commit, branch ou stash sobre a investigação. Só `6b90310` (`f3_rerun.sh` + guard de taxa) e `3772b16` (extração de CPU/mem). A versão do `f3_rerun.sh` usada em 02/09 (blob `c4a7fb4`) **nunca foi commitada**. A commitada é a de 05/09 (`713bedb`, que acrescenta o timeout de 45 min por rodada). O cenário k6 é o mesmo blob nos dois dias (`0ff2140`). |
| `analysis/fargate/fase3-f3-rerun/saturated-sb-r4-r5/` | As 2 rodadas "engasgadas" de 02/09 (r4: 293 dropped, p95 2108 ms; r5: 743 dropped, p95 1145 ms), arquivadas e preservadas. |
| `analysis/fargate/fase3-f3-rerun/_probe-sb-r4-live-2026-09-05/README.txt` | Única nota escrita da época. Descreve a sonda (p95 73 ms, 0 dropped). |
| **Transcrição da sessão original** (`~/.claude/projects/-home-bernardo-Programming-ecommerce-tcc/2eeda937-….jsonl`, 30/08–06/09) | O diagnóstico completo, de 05/09 às 21:46Z. Resumo abaixo. |

### O que o diagnóstico de 05/09 verificou (transcrição, 21:38–21:46Z)

| verificação | quando / sobre qual estado | resultado reportado |
|---|---|---|
| `ps`, `df`, `ss -tn` no runner | **05/09, runner recém-religado** (não o estado de 02/09) | sem k6/ssh órfãos, 28 GB livres, zero CLOSE_WAIT/TIME_WAIT |
| CPU do runner (CloudWatch EC2) | janelas de 02/09 r1–r5 | 10–12% em todas |
| RDS CPU, CPUCreditBalance, DBConnections, WriteLatency, DiskQueueDepth (1 min) | janelas de pico de 02/09 | CPU 63,7/64,0/66,2 (r1–r3) vs 67,6/67,8 (r4/r5). Saldo de créditos nunca zerou (284→219). 40 conexões em todas. Latência de escrita 0,9 ms em todas. |
| `pg_stat_activity` | **05/09** (não 02/09) | 40 idle, 1 active, sem lock, sem idle-in-transaction |
| Sequência de eventos | 02/09 | task órfã (native r3) criada 3,5 h depois da sb r5, então não interferiu |
| Distribuição de latência julho + 02/09 | arquivos locais | "toda rodada springboot tem cauda de 1–10 s" |
| CPU/mem do container no pico (Container Insights) | 02/09 | 42–66% de CPU, ~1,1 GB |

Texto do veredito original, na íntegra no ponto que interessa:

> "O que engordou a cauda em r4/r5 especificamente: **sem evidência dura**. RDS/runner/container
> todos limpos nas janelas. Candidato mais provável: **variância de host / noisy-neighbor do
> Fargate** nas 2 colocações específicas (não aparece no `CpuUtilized` da própria task), ou só
> timing de GC."

"Pausa de GC / starvation do event loop" entrou como **inferência**: a CPU média estava abaixo de
100% e a latência explodiu, então a app devia estar "parando". Nenhum dado de GC ou de event loop
foi coletado. A sonda limpa confirmou só que o estado ruim **não era persistente**. Ela não
confirmou o mecanismo.

Na mesma sessão, depois das r4/r5 novas, o próprio relatório registrou: *"as 3 rodadas springboot de
02/09 têm cauda gorda; as 2 de 05/09 são quase perfeitas… o set springboot de 5 rodadas não é
homogêneo"*. A CPU de 1 min por rodada (hoje expirada, ficou na transcrição) era **431/634/436**
(r1–r3, 02/09) contra **448/389** (r4–r5, 05/09).

### Divergências entre a época e o que ficou registrado

1. **Composição do conjunto oficial.** O guia diz "as 3 rodadas problemáticas ficaram como estão" e
   "só... as 2 rodadas de springboot que de fato faltavam foram re-executadas". Nos arquivos, as
   2 "que faltavam" são a r4 e a r5 de **02/09**, que rodaram, saíram ruins (com dropped) e foram
   arquivadas e substituídas por rodadas de 05/09. O conjunto oficial do Spring Boot no F3 é,
   portanto, **3 rodadas do dia ruim + 2 do dia bom**. Se o critério de exclusão tivesse sido o p95
   e não os `dropped_iterations`, r1–r3 também teriam caído. Só registro o fato; não é
   recomendação.
2. **"Replicável em julho também"** está correto, e com mais força do que o guia sugere: julho não
   tem nenhuma rodada de F3 do Spring Boot com p95 abaixo de 150 ms.
3. **`exploratorio_gc_f3` partiu de uma premissa errada sobre o protocolo.** Ele diz *"A task **não**
   era reiniciada entre rodadas… a JVM chegava aquecida"* e reproduziu isso localmente
   (TRUNCATE com o app em pé). O protocolo oficial fazia **stop-task → run-task por rodada**
   (`f3_rerun.sh` linhas 18–19, 285–295). O CloudTrail mostra 1 `RunTask` por rodada
   (`cloudtrail_runtask_f3_setembro.txt`) e os logs da app mostram 1 boot de JVM por rodada
   (`logs_ecs_startup_todas_tasks.tsv`). Toda rodada oficial começava com JVM **fria**: ~2 min entre
   "Started" e o início da carga, depois 5 min a 48 it/s antes da rampa. A conclusão sobre a
   magnitude do GC continua de pé, mas a reprodução local **não testou a condição de JVM recém-iniciada**.
4. "Cauda bimodal" (transcrição) não se sustenta. A cauda é contínua de 50 ms a 10 s, sem modos
   (tabela em `rodadas_f3_setembro.csv`, colunas `pct_gt_*`).

---

## B. Telemetria AWS retida para a janela de 02/09

| fonte | estado em 21/09/2026 | detalhe |
|---|---|---|
| RDS Performance Insights | **nunca existiu** | `PerformanceInsightsEnabled=False`, retenção `None` |
| RDS Enhanced Monitoring | **nunca existiu** | `MonitoringInterval=0` |
| Logs do PostgreSQL no RDS | **expirado** | arquivo mais antigo é de 18/09 (retenção de 3 dias na instância). Nunca exportados para o CloudWatch Logs (`EnabledCloudwatchLogsExports=None`). |
| CloudWatch 1 min (AWS/RDS, ECS/ContainerInsights, AWS/EC2 do runner) | **expirado** | consulta period=60 para 02/09 devolve 0 pontos nos três namespaces |
| CloudWatch 5 min (mesmos namespaces) | **existe**, até ~04/11/2026 | period=300 devolve os pontos. Usado abaixo. |
| Container Insights por task (dimensão TaskId) / log de performance | **nunca existiu / expirado** | modo não-enhanced (só `TaskDefinitionFamily`). O log group `/aws/ecs/containerinsights/.../performance` tem retenção de 1 dia e está vazio. |
| Métrica de rede da ENI da task | **nunca existiu** | o Fargate não publica métrica por ENI. Não há VPC Flow Logs na conta. |
| Logs da aplicação `/ecs/order-service-*` | **existe** (retenção "never expire") | ver abaixo |
| CloudTrail | **existe**, até ~01/12/2026 | `RunTask` (task ID, AZ, subnet) e ciclo de vida do runner |
| JSON bruto do k6 (timestamps por requisição) | **não existe** | apagado no runner por desenho após a extração. Runner terminado em 06/09. O `latency.json` local guarda só valores em ordem, sem timestamp. |

### O que as fontes existentes mostram

**Logs da aplicação** (8 tasks do Spring Boot, 02/09 e 05/09): só boot e graceful shutdown. **Nenhum
ERROR, WARN ou exceção durante a carga** em nenhuma rodada, boa ou ruim. A única linha fora disso é
um `Decoding failed … GET /bad-request` de um scanner da internet (a task tem IP público). Ele
aparece uma vez em 02/09 (r3) e uma vez em 05/09 (r4), então não discrimina. A app roda em INFO,
sem DEBUG. Um sinal fraco: o tempo de boot do Spring Boot foi **12,1–15,4 s em 02/09** contra
**10,1–12,1 s em 05/09**, e o `Flyway validate` levou 80–104 ms contra 35–72 ms. Correlação boot×p95
nas 13 rodadas de F3 do Spring Boot: Spearman ρ=0,56 (p=0,047). **Sem o bloco de 05/09, ρ=0,19
(p=0,60)**: o sinal é inteiramente o contraste entre dias, não um preditor por rodada.

**CloudTrail**: todas as tasks dos dois dias (Spring Boot, JVM e Native) foram para
**us-east-1c, `subnet-09021fc5dd37000fc`**. O RDS fica em **us-east-1d**, então **todas** as rodadas
são cross-AZ. A AZ não separa dia bom de dia ruim. O runner é **a mesma instância** nos dois dias
(`i-03d4feffaa1a0b4f4`, m7i-flex.large, us-east-1c), ligada sem parar de 01/09 23:19Z a 05/09 21:19Z
e religada às 21:29Z. O stop/start explica o IP novo e implica host físico novo para o runner.

**CloudWatch 5 min** (`cw_por_rodada_pico_5min.csv`, `cw_serie_5min.txt`):
- Runner: CPU média 10–11,5% e máxima ≤12,4% em todas as 18 janelas. Pacotes e bytes equivalentes.
- RDS nas mesmas posições relativas ao início da carga, dia ruim contra dia bom: CPU 81–84% vs 77%
  (bin do fim do pico). ReadLatency e WriteLatency ~0,5–1 ms, DiskQueueDepth 0,2 e 40 conexões,
  **iguais**. `CPUSurplusCreditBalance`=0 sempre. A conclusão anterior se mantém.
- CPU da task Spring Boot no mesmo offset: **sem diferença sistemática**. A pior rodada (r4 de 02/09,
  p95 2108 ms) usou **menos** CPU (406 u) que a r4 limpa de 05/09 (458 u). Uma leitura inicial deste
  reexame, "o SB gastou 10–40% mais CPU em 02/09", vinha de janelas desalinhadas e **foi descartada**.
- Série de 5 min: a CPU do RDS **sobe ao longo do pico** (~50% → ~80% nas rodadas do Spring Boot,
  ~45% → ~65% nas do Quarkus). A subida coincide com o trecho onde a cauda se concentra.

### Cruzamento com as rodadas ruins (latency.json, perfil por minuto aproximado)

`perfil_por_minuto.csv` usa a posição no stream mapeada pela integral da taxa programada. É preciso
na escala de minuto, não de segundo; ver o aviso em `perfil_rodadas.py`. Fases: 0–5 baseline@48,
5–7 rampa, **7–17 pico@240**, 17–19 rampa, 19–24 recuperação@48.

| rodada | minutos com p95/min > 1 s | pior minuto (p95 / % reqs > 1 s) |
|---|---|---|
| SB r1 02/09 (oficial) | 13, 17 | min 17: 3,4 s / 25% |
| SB r2 02/09 (oficial) | 10, 15, 16, 17 | min 16: 3,2 s / 38% |
| SB r3 02/09 (oficial) | 12, 16, 17 | min 16: 2,7 s / 31% |
| SB r4 02/09 (descartada) | 14–17 | min 16: 6,8 s / 31% |
| SB r5 02/09 (descartada) | 6, 14, 16, 17 | min 16: 7,0 s / 38% |
| SB sonda 05/09 | 13 | min 13: 1,3 s / 6,5% |
| SB r4 05/09 (oficial) | — | min 15: 0,67 s / 2,2% |
| SB r5 05/09 (oficial) | 16 | min 16: 1,5 s / 8,3% |
| QJ r2 02/09 (controle) | — | min 15: 0,78 s / 3,6% |

Fora do pico o Spring Boot fica em 18–30 ms nos dois dias. O problema **não** é lentidão sustentada.
São episódios de 1–3 minutos, concentrados nos minutos 13–17, com o maior quase sempre no 16 ou no
17 (o fim do pico).

---

## C. Hipóteses ainda não descartadas nem testadas para a instabilidade

O que precisa ser explicado: **(i)** por que os episódios caem no fim do pico, **(ii)** por que o
Spring Boot os amplifica tanto mais que o Quarkus, e **(iii)** por que 02/09 (e julho) amplificam e
05/09 não.

### Já descartado como diferença entre dias (este reexame + anteriores)

AZ e subnet (idênticas), task definition, imagem (mesmo digest `276548dd`), tamanho da task,
parâmetros de VUs, cenário k6 (mesmo blob), instância e AZ do runner, CPU do runner, CPU, latência,
IO, conexões e créditos do RDS em 1 e 5 min, estado do banco (TRUNCATE por rodada), erros na app
(nenhum), magnitude de pausa de GC (`exploratorio_gc_f3`), proxy/reflexão (só o gap médio,
`exploratorio_pilha_fargate`).

### Restantes

| # | hipótese | explica | a favor | contra / lacuna | por que segue aberta |
|---|---|---|---|---|---|
| 1 | **Heterogeneidade ou contenção do host Fargate** (geração de CPU, steal, vizinho barulhento), por colocação ou por período do dia | (iii) | Efeito agrupado por dia. Boot da JVM ~25% mais lento em 02/09. A cauda >1 s do Native também é ~2× maior em 02/09 (0,38–0,51% vs 0,15–0,22%; n=2 vs 3). Era o candidato principal do relatório original. | Não há registro do modelo de CPU nem de steal. O boot não prediz o p95 dentro de um mesmo dia. | Nunca foi instrumentado. Retroativamente impossível. |
| 2 | **Throttling de CFS na cota de 1 vCPU** em rajadas sub-segundo | (ii), (iii) em conjunto com #1 | Pico de 1 min do SB ~0,72 vCPU. Rajadas de 100 ms podem bater a cota. Um host mais lento aproxima a app do joelho. | O Container Insights não expõe `nr_throttled`/`throttled_usec`. O `gc_f3` local com `--cpus=1` não reproduziu o estado ruim, mas lá o host era outro e o banco não pressionava. | Nunca medido no Fargate. |
| 3 | **Custo crescente das consultas durante o pico**: tabelas partem de zero (TRUNCATE) e crescem. O `get_summary` (2% do mix, ~5/s no pico) agrega `orders` inteira no intervalo de datas (`OrderSummaryRepositoryImpl.java:95–135`). Autoanalyze com naptime 15 s e scale 0,05 pode trocar planos durante a rodada. | (i) | A CPU do RDS sobe de ~50% para ~80% ao longo do pico. Os episódios ficam no fim do pico em todos os runtimes. O `gc_f3` local (banco a 14%, sem TLS, sem rede) **eliminou essa pressão e não reproduziu**. | Média de 5 min não mostra saturação sub-minuto. Não há log de autovacuum nem plano de 02/09 (logs do RDS expirados, `log_autovacuum_min_duration`=10 s). | "CPU do RDS igual entre rodadas" descarta o RDS como **diferença entre dias**, não como **gatilho** comum. |
| 4 | **Fila de aquisição no pool R2DBC** (40 conexões, sempre cheio no RDS) | (ii) | 40 conexões em todas as 18 rodadas, inclusive Quarkus. Se o gatilho #3 alonga o tempo de posse da conexão, a fila do `r2dbc-pool` pode se comportar diferente da fila do pool do Vert.x. | Tempo de aquisição e tamanho da fila nunca medidos. Os dois lados têm pool 40. | Não testado. O `pilha_fargate` local usou pool 20. |
| 5 | **Topologia de event loops sob 1 vCPU**: o SB separa HTTP (`reactor-http-epoll`) e banco (`reactor-tcp-epoll`, 64% da CPU), com TLS para o RDS no loop de banco. O Quarkus usa um grupo só. | (ii) | Estrutural e documentado (`NOTAS_pilha_fargate.md`, "Diferença de topologia de threads"). | O `pilha_fargate` explicitamente "não isolou o custo do salto entre threads". Rodou sem TLS e com pool 20. | Não testado para cauda. |
| 6 | **JVM recém-iniciada no pico**: estado de JIT/deopt ~7–12 min após o boot, com `CICompilerCount=2` disputando 1 vCPU com a app | (ii), talvez (iii) com #1 | Cada rodada oficial tinha JVM fria (seção A.3). Primeiro minuto elevado em várias rodadas (SB r2: 572 ms). | As rodadas de 05/09 também tinham JVM fria e saíram limpas. | Não testado: o `gc_f3` reproduziu JVM aquecida. |
| 7 | **Latência de rede task→RDS cross-AZ (1c→1d) variável por período** | (iii) | Todas as rodadas são cross-AZ, com TLS. A CPU do RDS não capturaria esse efeito. | Nada no Flyway validate além do sinal fraco (80–104 vs 35–72 ms). Sem medição de RTT. | Não medido. Sem flow logs. |
| 8 | **Estado do runner em 02/09** (ligado desde 01/09 23:19Z) | (iii) | O runner mudou de host físico entre os dias. | O Quarkus rodou limpo no mesmo runner, no mesmo dia, depois do SB. CPU 11% em todas as janelas. A inspeção `ps`/`ss`/`df` foi feita **só em 05/09, depois do restart**. | Parcialmente coberto. Prioridade baixa. |
| 9 | **Diferença não verificável entre as versões do `f3_rerun.sh`** (`c4a7fb4` em 02/09, nunca commitada, vs `713bedb`) | (iii) | — | Pela transcrição, a mudança foi só o `timeout` de 45 min. O cenário é o mesmo blob. | Prioridade muito baixa. |
| 10 | **Throttling de rede ou PPS da ENI da task** | (iii) | — | ~1 MB/s e ~170k pacotes em 5 min, ordens de grandeza abaixo de qualquer limite. `http_req_connecting` máx. 19–42 ms nos dois dias. | Praticamente descartável, mas sem métrica sub-minuto. |

Leitura conjunta, **não** conclusão: #3 é o candidato mais simples para **quando** acontece;
#4, #5 e #6 para **por que o Spring Boot amplifica**; #1 e #2 para **por que um dia difere do outro**.
Nenhuma das três partes tem dado suficiente para ser afirmada.

### O que um teste futuro precisaria capturar (fica registrado, não foi feito)

No Fargate, e não localmente: `/proc/cpuinfo` (modelo) e `cpu.stat` do cgroup (`nr_throttled`,
`throttled_usec`) no início e no fim de cada rodada. Métricas do `r2dbc-pool` (acquired, pending).
`log_autovacuum_min_duration=0` e `auto_explain` no RDS, com export para o CloudWatch Logs. Guardar o
JSON bruto do k6 (timestamp por requisição e tag de operação). Várias rodadas do Spring Boot
**intercaladas** com Quarkus em dias diferentes, para separar efeito de dia de efeito de runtime.

---

## Arquivos

| arquivo | conteúdo |
|---|---|
| `perfil_rodadas.py` | gera `rodadas_f3_setembro.csv` (18 rodadas: oficiais + 2 descartadas + sonda) e `perfil_por_minuto.csv` |
| `cw_por_rodada.py` → `cw_por_rodada_pico_5min.csv` | RDS / Container Insights / EC2 do runner na janela de pico, period=300 (rodar da raiz do repo) |
| `cw_serie_5min.py` → `cw_serie_5min.txt` | série de 5 min de CPU da app e do RDS relativa ao início da carga |
| `logs_ecs_startup_todas_tasks.tsv` | todas as log streams `/ecs/order-service-*`: boot, Flyway validate, contagem de WARN/ERROR |
| `cloudtrail_runtask_f3_setembro.txt` | RunTask de 02/09 e 05/09: task ID, AZ, subnet |
| `cloudtrail_ec2_runner.txt` | ciclo de vida do runner (29/08–08/09) |
