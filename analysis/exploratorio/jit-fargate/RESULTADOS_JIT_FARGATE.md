# Nível de compilação JIT no AWS Fargate — Spring Boot × Quarkus JVM

> **Investigação exploratória, fora do desenho experimental oficial do TCC.** Nada aqui substitui ou
> altera dados oficiais. As latências deste teste **não** são comparáveis às oficiais e não são reportadas.

- **Datas:** montagem e fumaça em 29/09/2026; Fase B de 22:49Z (29/09) a 03:06Z (30/09); análise em 30/09/2026.
- **Recursos:** todos com prefixo `exp-jit-` e tag `Projeto=tcc-exp-jit`, listados em `inventario_recursos.txt`.
  Conta 776648109551, us-east-1. Cluster ECS próprio, RDS próprio (db.t3.micro, PG 16.4, us-east-1d) e runner
  m7i-flex.large (us-east-1c).
- **Diferenças em relação ao oficial:**
  1. banco separado e novo (`exp-jit-postgres`), com cache frio e acesso privado;
  2. `-XX:+PrintCompilation` em `JAVA_OPTS_APPEND`, única mudança na JVM;
  3. `awslogs` com `mode=non-blocking` explícito (já era o padrão da conta) e `max-buffer-size=25m`;
  4. senha do banco via Secrets Manager;
  5. ECS Exec ligado (agente SSM dentro da task), usado para o `jcmd` ao fim de cada rodada.

  Diff completo em `taskdefs/taskdef_diff_*.txt`.
- **Imagens:** as mesmas das task defs oficiais, fixadas por digest: SB `276548dd…` (publicada em 21/06/2026)
  e QJ `abec3583…` (16/06/2026). Ambas são anteriores a todas as coletas oficiais, e o CloudTrail, que cobre
  desde 01/07, não registra nenhum `PutImage` (`NOTAS_execucao.md`). O `imageDigest` de cada rodada confere
  (`fase_b/rodadas/*/meta.json`).
- **Flags efetivas** (`jcmd VM.command_line` e `VM.flags`, em `fase_b/rodadas/*/jcmd_vm_bruto.txt`): as oficiais
  mais `-XX:+PrintCompilation`; `CICompilerCount=2` (1 vCPU); nenhuma `TieredStopAtLevel`; compilação em camadas padrão.
- **Carga:** idêntica à oficial (`fase_b/rodadas/*/summary.json`). F1 teve 63.393 iterações no SB
  (26 descartadas) e 63.419 no QJ. F2 teve 216.720 e F3 208.799 nas duas versões; F2-S, 6.479 no SB e 6.480 no QJ.
  Nenhuma falha HTTP. Uma rodada por combinação (N = 1), task fresca e TRUNCATE a cada rodada; no F2-S, 50.000 linhas conferidas.

**Níveis do tiered compilation:**
- 0 = interpretado;
- 1 = C1 sem profiling (final para métodos triviais, como getters);
- 2 = C1 com profiling limitado;
- 3 = C1 com profiling completo (intermediário, a camada compilada mais lenta);
- 4 = C2 (otimizador).

**Método:** o "nível ao fim" é o maior nível entre as versões compiladas **vivas** do método no instante da última
requisição, isto é, compiladas e não marcadas `made not entrant`. Métodos sobrecarregados são agregados pelo nome,
porque o PrintCompilation não imprime a assinatura. Os tempos são contados em segundos desde a primeira requisição
da carga (sem o `setup()` do k6); valores negativos correspondem ao boot.

## 1. Integridade da captura

| verificação | resultado | fonte |
|---|---|---|
| JVMs por log | 1 em todas as rodadas | `fase_b/csv/integridade.csv` |
| ids do `Compiler.codelist` ausentes no log | 0 em 6 rodadas; 1 em F3/SB e 1 em F3/QJ | idem |
| linhas não parseadas | 0 em 6 rodadas; 1 em F2/SB e 1 em F3/QJ | idem |
| n4 pelo log × n4 pelo jcmd | diferença de 0 a 11 métodos (o jcmd roda segundos depois da última requisição) | `nivel_por_rodada.csv` |
| relógio (timestamp do CloudWatch − uptime) | dispersão p05–p95 de 1 ms | `integridade.csv` |

As 3 linhas residuais são do boot: banner do Spring e mensagens de inicialização do Quarkus escritas no meio de
uma linha do PrintCompilation. Os métodos afetados (`CharacterDataLatin1::toLowerCase`, filas do Netty,
`LoggerNode::publish`) não pertencem aos caminhos analisados. Outras intercalações do mesmo tipo foram
recuperadas pelo parser (`linhas_orfas_recuperadas` e `linhas_recombinadas`).

Faltam ids na sequência de compilação (8 a 412 por rodada). Isso não indica perda de log: tarefas de compilação
descartadas da fila nunca imprimem linha. No teste local sem perda possível, a proporção foi maior, cerca de 8% no SB.
A prova de integridade é o codelist. **Conclusão: captura confiável.**

## 2. P1 — métodos por nível ao fim da carga

| cenário | versão | n1 | n2 | n3 | **n4** | n4 (jcmd) | OSR n4 | compilações n4 | 100º n4 (s) | 1.000º n4 (s) | último n4 (s) | último n4 (% da janela) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | SB | 1366 | 1244 | 4319 | **3394** | 3392 | 27 | 4007 | -35.9 | -1.3 | 1371.5 | 95% |
| F1 | QJ | 997 | 340 | 3659 | **1929** | 1931 | 24 | 2259 | -21.5 | 64.4 | 1435.3 | 100% |
| F2 | SB | 1386 | 1926 | 3568 | **3574** | 3585 | 26 | 4123 | -99.4 | -1.8 | 2428.0 | 91% |
| F2 | QJ | 1054 | 600 | 3672 | **2102** | 2104 | 27 | 2473 | -84.6 | 15.4 | 2606.1 | 98% |
| F2S | SB | 1215 | 1089 | 4113 | **2357** | 2357 | 27 | 2767 | -30.3 | -3.8 | 818.2 | 98% |
| F2S | QJ | 926 | 377 | 3254 | **1325** | 1315 | 24 | 1513 | -21.9 | 88.6 | 813.9 | 97% |
| F3 | SB | 1387 | 1828 | 3666 | **3574** | 3581 | 20 | 4135 | -97.6 | -1.9 | 1429.8 | 95% |
| F3 | QJ | 1045 | 446 | 3772 | **2142** | 2146 | 31 | 2513 | -85.7 | 13.6 | 1470.3 | 98% |

Fontes: `fase_b/csv/nivel_por_rodada.csv` e `curva_nivel4.csv`. "compilações n4" conta também recompilações.
"n4 (jcmd)" vem do `Compiler.codelist`, com as versões vivas de nível 4 agregadas por nome de método.

**Curva.** Métodos distintos que já tinham chegado a n4, em % do total final (`curva_nivel4.csv`):

| | aos 5 min | aos 10 min |
|---|---|---|
| SB | 87–89% | 92–97% |
| QJ | 81–84% | 86–95% |

A compilação em nível 4 **não para**: o último n4 ocorre entre 91% e 100% da janela em todas as rodadas.

## 3. P2 — caminho do `GET /orders/summary`

**Chamadas ao summary por rodada** (`integridade.csv`, coluna `chamadas_summary`):

| | F1 | F2 | F2-S | F3 |
|---|---|---|---|---|
| SB | 1.266 | 4.334 | 6.479 | 4.175 |
| QJ | 1.268 | 4.334 | 6.480 | 4.175 |

Cada célula mostra o nível máximo do método. Quando ele chega a n4, a célula traz também o instante do primeiro n4
e o número de chamadas ao summary até ali. "só no fim" significa primeiro n4 depois de 80% da janela.
Fonte: `fase_b/csv/summary_path_nivel.csv`, só métodos com certeza = "certo".

**Spring Boot**

| método | F1 | F2 | F2-S | F3 |
|---|---|---|---|---|
| `controller.OrderController::getSummary` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::getDate` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::getOrderCount` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::getRevenue` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::<init>` | – | n2 | – | n3 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::getCustomerId` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::getOrderCount` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::getTotalSpent` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse::<init>` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getAverageOrderValue` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse::getOrdersByStatus` | n3 | n3 | **n4** 716 s / 5632 ch. (só no fim) | n3 |
| `dto.response.OrderSummaryResponse::getRevenueByDay` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getTopCustomers` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getTotalOrders` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse::getTotalRevenue` | n1 | n1 | n1 | n1 |
| `repository.OrderSummaryRepositoryImpl$DateRange::<init>` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl$DateRange::fromTimestamp` | n1 | n1 | n1 | n1 |
| `repository.OrderSummaryRepositoryImpl$DateRange::toTimestamp` | n1 | n1 | n1 | n1 |
| `repository.OrderSummaryRepositoryImpl::countOrdersByDateRange` | n3 | n3 | **n4** 716 s / 5631 ch. (só no fim) | n3 |
| `repository.OrderSummaryRepositoryImpl::countOrdersByStatusInDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::findRevenueByDay` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::findTopCustomersByRevenue` | n3 | n3 | **n4** 716 s / 5631 ch. (só no fim) | n3 |
| `repository.OrderSummaryRepositoryImpl::initializeStatusCounts` | n3 | **n4** 1923 s / 3072 ch. | **n4** 396 s / 3072 ch. | **n4** 928 s / 3072 ch. |
| `repository.OrderSummaryRepositoryImpl::lambda$countOrdersByDateRange$0` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::lambda$countOrdersByStatusInDateRange$2` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::lambda$countOrdersByStatusInDateRange$4` | n3 | **n4** 1280 s / 1836 ch. | **n4** 146 s / 1066 ch. | **n4** 670 s / 1834 ch. |
| `repository.OrderSummaryRepositoryImpl::lambda$countOrdersByStatusInDateRange$5` | – | – | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::lambda$findRevenueByDay$7` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::lambda$findTopCustomersByRevenue$6` | n3 | **n4** 560 s / 537 ch. | n3 | **n4** 398 s / 536 ch. |
| `repository.OrderSummaryRepositoryImpl::lambda$sumRevenueByDateRange$1` | n3 | n3 | n3 | – |
| `repository.OrderSummaryRepositoryImpl::sumRevenueByDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepositoryImpl::toBigDecimal` | **n4** 527 s / 448 ch. | **n4** 762 s / 843 ch. | **n4** 65 s / 419 ch. | **n4** 374 s / 447 ch. |
| `repository.OrderSummaryRepositoryImpl::toLong` | **n4** 433 s / 359 ch. | **n4** 500 s / 478 ch. | **n4** 48 s / 289 ch. | **n4** 346 s / 366 ch. |
| `repository.OrderSummaryRepositoryImpl::validateAndBuildDateRange` | n3 | **n4** 1110 s / 1510 ch. | **n4** 175 s / 1305 ch. | **n4** 517 s / 1100 ch. |
| `service.OrderService::calculateAverageOrderValue` | n3 | n3 | **n4** 700 s / 5503 ch. (só no fim) | n3 |
| `service.OrderService::fillMissingStatuses` | **n4** 1096 s / 995 ch. | **n4** 841 s / 994 ch. | **n4** 137 s / 995 ch. | **n4** 495 s / 995 ch. |
| `service.OrderService::getSummary` | n3 | n3 | n3 | n3 |
| `service.OrderService::lambda$getSummary$11` | n3 | n3 | n3 | n3 |
| `service.OrderService::normalizeMoney` | **n4** 360 s / 288 ch. | n3 | n3 | **n4** 77 s / 73 ch. |
| `service.OrderService::validateSummaryDateRange` | n3 | n3 | n3 | n3 |

**Quarkus JVM**

| método | F1 | F2 | F2-S | F3 |
|---|---|---|---|---|
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::<init>` | – | – | n3 | – |
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::getDate` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::getOrderCount` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$RevenueByDaySummary::getRevenue` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::<init>` | n3 | **n4** 1296 s / 1870 ch. | n3 | **n4** 678 s / 1870 ch. |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::getCustomerId` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::getOrderCount` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse$TopCustomerSummary::getTotalSpent` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse::<init>` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getAverageOrderValue` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse::getOrdersByStatus` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getRevenueByDay` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getTopCustomers` | n3 | n3 | n3 | n3 |
| `dto.response.OrderSummaryResponse::getTotalOrders` | n1 | n1 | n1 | n1 |
| `dto.response.OrderSummaryResponse::getTotalRevenue` | n1 | n1 | n1 | n1 |
| `repository.OrderSummaryRepository$DateRange::<init>` | – | n3 | – | – |
| `repository.OrderSummaryRepository$DateRange::fromTimestamp` | n1 | n1 | n1 | n1 |
| `repository.OrderSummaryRepository$DateRange::toTimestamp` | n1 | n1 | n1 | n1 |
| `repository.OrderSummaryRepository::countOrdersByDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::countOrdersByStatusInDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::extractTotalOrders` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::extractTotalRevenue` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::findRevenueByDay` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::findTopCustomersByRevenue` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::mapRevenueByDay` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::mapStatusCounts` | n3 | n3 | **n4** 385 s / 2986 ch. | n3 |
| `repository.OrderSummaryRepository::mapTopCustomers` | n3 | **n4** 1283 s / 1842 ch. | **n4** 243 s / 1843 ch. | **n4** 672 s / 1844 ch. |
| `repository.OrderSummaryRepository::sumRevenueByDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository::validateAndBuildDateRange` | **n4** 1179 s / 1074 ch. (só no fim) | **n4** 896 s / 1100 ch. | **n4** 146 s / 1075 ch. | **n4** 512 s / 1074 ch. |
| `repository.OrderSummaryRepository_ClientProxy::arc$delegate` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository_ClientProxy::countOrdersByDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository_ClientProxy::countOrdersByStatusInDateRange` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository_ClientProxy::findRevenueByDay` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository_ClientProxy::findTopCustomersByRevenue` | n3 | n3 | n3 | n3 |
| `repository.OrderSummaryRepository_ClientProxy::sumRevenueByDateRange` | n3 | n3 | **n4** 716 s / 5632 ch. (só no fim) | n3 |
| `resource.OrderResource$quarkusrestinvoker$getSummary_…::invoke` | n3 | n3 | **n4** 716 s / 5631 ch. (só no fim) | n3 |
| `resource.OrderResource::getSummary` | n3 | n3 | n3 | n3 |
| `service.OrderService::calculateAverageOrderValue` | n3 | n3 | n3 | n3 |
| `service.OrderService::fillMissingStatuses` | **n4** 1095 s / 994 ch. | **n4** 841 s / 995 ch. | **n4** 137 s / 995 ch. | **n4** 496 s / 995 ch. |
| `service.OrderService::getSummary` | n3 | n3 | n3 | n3 |
| `service.OrderService::lambda$getSummary$12` | n3 | n3 | n3 | n3 |
| `service.OrderService::normalizeMoney` | **n4** 70 s / 20 ch. | **n4** 104 s / 100 ch. | n3 | **n4** 104 s / 98 ch. |
| `service.OrderService::validateSummaryDateRange` | n3 | n3 | n3 | n3 |
| `service.OrderService_ClientProxy::getSummary` | n3 | n3 | n3 | n3 |

**Leitura:**

- **Métodos centrais, chamados uma vez por requisição** (controller ou invoker, `OrderService::getSummary`, os
  5 métodos de consulta do repositório e os proxies Arc): **não atingem n4 em F1, F2 nem F3, nas duas versões.**
  Ficam em n3.
- **No F2-S, alguns deles atingem n4 só no fim**, aos **716 s de 840 s**, com **5.631–5.632 chamadas**:
  - SB: `countOrdersByDateRange`, `findTopCustomersByRevenue`, `calculateAverageOrderValue`, `getOrdersByStatus`;
  - QJ: o invoker e `OrderSummaryRepository_ClientProxy::sumRevenueByDateRange`;
  - os demais centrais (controller, `OrderService::getSummary`, as outras consultas) terminam o F2-S em n3.
- **Instante idêntico nas duas versões.** O mesmo instante e o mesmo número de chamadas aparecem nas duas versões,
  porque a taxa do F2-S é determinística. Interpretação, não medida: é consistente com `Tier4InvocationThreshold`
  (5.000) checado em múltiplos de 1.024 invocações no código de nível 3 (`Tier3InvokeNotifyFreqLog=10`), somado às
  invocações anteriores à instalação desse código. **Em chamadas ao endpoint, o limiar efetivo observado é de cerca
  de 5.630, não 5.000.**
- **Métodos auxiliares, chamados várias vezes por requisição ou por linha do resultado**, atingem n4 cedo em todos
  os cenários:
  - `fillMissingStatuses` com cerca de 995 chamadas ao summary;
  - `validateAndBuildDateRange` com 1.074–1.510;
  - no SB, `toLong`, `toBigDecimal` e lambdas de mapeamento com 289–843.
  No F1, só chegam a n4 os que cruzam o limiar dentro de cerca de 1.270 chamadas.
- **Getters triviais do DTO** terminam em n1, o nível final para métodos triviais.

**Ressalva de inlining.** Um método em n3 cujo chamador está em n4 pode estar sendo executado *inlined* dentro do
código C2 do chamador. Por exemplo, no `GET /orders/{id}` do QJ, `OrderResource::getOrderById` fica em n3 enquanto
o invoker chega a n4 (`fase_b_caminho_get_order.txt`). No summary isso não muda a leitura em F1–F3: o próprio ponto
de entrada (controller ou invoker) e `OrderService::getSummary` ficam em n3, logo o código da aplicação desse
endpoint executa em C1, exceto os auxiliares já em n4.

## 4. P3 — diferenças SB × QJ, incluindo deopt

| cenário | versão | compilações (total) | made not entrant (total) | durante a carga | de n4 | caminho summary (carga) |
|---|---|---|---|---|---|---|
| F1 | SB | 17608 | 5808 | 3426 | 417 | 8 |
| F1 | QJ | 10790 | 2663 | 1867 | 214 | 6 |
| F2 | SB | 19426 | 7420 | 5018 | 351 | 18 |
| F2 | QJ | 11794 | 3099 | 2256 | 252 | 10 |
| F2S | SB | 14111 | 4052 | 1889 | 274 | 14 |
| F2S | QJ | 8796 | 1819 | 962 | 106 | 8 |
| F3 | SB | 18836 | 6845 | 4622 | 365 | 15 |
| F3 | QJ | 11695 | 2942 | 2161 | 250 | 9 |

Fonte: `fase_b/csv/deopt.csv` e `integridade.csv`.

- **Volume de código compilado.** O SB compila mais e leva mais métodos ao C2: cerca de 1,6 a 1,8 vez o QJ em
  compilações e em métodos n4 ao fim (3.394–3.574 contra 1.929–2.142 em F1/F2/F3). Tem também cerca de 2 a 2,4
  vezes mais linhas `made not entrant`.
- **Ritmo.** O SB já tem o 1.000º n4 antes da primeira requisição (−1,3 a −3,8 s), por causa do boot mais pesado do
  Spring. O QJ chega ao 1.000º n4 entre 14 e 89 s de carga. Relativamente ao próprio total final, os dois têm o
  mesmo formato de curva (seção 2).
- **Caminho do summary.** Em F1–F3, o SB tem mais métodos em n4 (4–8 contra 2–5), mas são os auxiliares de
  mapeamento que o QJ não tem na mesma forma: o QJ mapeia `RowSet` em laço, dentro de `mapStatusCounts` e `mapTopCustomers`.
- **Níveis iguais nos métodos centrais.** Nas duas versões, os métodos centrais estão no **mesmo nível (n3)** em
  F1–F3. Deopts no caminho durante a carga: SB 8–18, QJ 6–10.

## 5. Respostas diretas

**P1.** Sim, o Fargate atinge C2, e em grande escala:
- ao fim da carga, SB tem 3.394–3.574 métodos em n4 e QJ 1.929–2.142 em F1/F2/F3 (F2-S: 2.357 e 1.325);
- 81 a 89% desses métodos já estão em n4 aos 5 min de carga;
- a compilação C2 continua até o fim da janela, então não há um estado "convergido" terminado.

*Certeza alta:* captura validada pelo codelist, N = 1, estado determinístico.

**Caminho do `GET /orders/{id}`** (`fase_b_caminho_get_order.txt`): o handler ou invoker e os métodos de
serviço e mapeamento chegam a n4 entre 47 e 292 s de carga em F1–F3, nas duas versões. Alguns métodos do caminho
ficam em n3, possivelmente *inlined* nos chamadores em n4.

**P2.** Depende do tipo de método:
- **Métodos centrais do summary** (entrada, serviço, consultas, chamados uma vez por requisição): **não atingem C2**
  em F1, F2 nem F3, com 1.266 a 4.334 chamadas por rodada. **No F2-S atingem só no fim, e só alguns**: a partir de
  cerca de 5.630 chamadas (716 s de 840 s); controller e `OrderService::getSummary` terminam em n3. **Uma repetição
  do F2-S é recomendável** (limítrofe pela regra do teste), embora o mecanismo determinístico torne improvável um
  resultado diferente.
- **Métodos auxiliares, chamados várias vezes por requisição:** atingem C2 em todos os cenários, com cerca de
  1.000 chamadas ou menos.

*Certeza alta* nos fatos. O limiar de cerca de 5.630 é observado, e sua decomposição acima é interpretação.

**P3.** Nos métodos centrais do summary, **não há assimetria de nível**: ambos ficam em C1 (n3) em F1–F3. O resíduo
de `get_summary` sob carga alta entre SB e QJ **não pode ser atribuído** a um dos dois atingir C2 e o outro não,
nesses métodos. No geral, o SB compila e desotimiza cerca de 2 vezes mais, coerente com um volume maior de código
de framework quente.

**O que não pode ser concluído:**
- nada sobre latência, throughput ou custo;
- que o código de framework e driver usado pelo summary (Reactor, Netty, Jackson, R2DBC ou Vert.x) esteja em C1: ele
  é compartilhado com os endpoints quentes e em boa parte está em n4, o que não foi quantificado por endpoint;
- quanto do tempo de CPU de cada requisição roda em cada nível (o PrintCompilation dá estado, não perfil de tempo);
- que o F2-S "com JIT plenamente otimizado" tenha existido em algum momento da janela de medição;
- nada sobre variação entre rodadas (N = 1).

## 6. Limitações

- N = 1 por combinação. A pergunta era de estado, e o estado é determinístico dado o número de invocações, mas o
  instante exato de cada n4 depende da carga das filas de compilação.
- Banco separado e novo, cache frio. O F3 pode ter saturado o db.t3.micro como no oficial; isso não foi medido
  aqui, porque não era o objetivo.
- `-XX:+PrintCompilation` e o agente do ECS Exec consomem um pouco de CPU na task de 1 vCPU, o que pode deslocar
  instantes de compilação.
- A agregação por nome junta sobrecargas, e o nível ao fim não enxerga *inlining*.
- 3 linhas de boot não recuperadas (seção 1).
- Nada disso substitui os dados oficiais.

## 7. Implicações para o texto (sem editar; lido em `~/Downloads/*.tex`, versões mais recentes)

1. **`metodologia(50).tex` l.103–123** (`subsubsec:summary-endpoint`, provavelmente o §4.4.2, e a Tabela
   `tab:frequencia-summary`):
   - **Confirmado:** "em F1 e F2 o volume não é suficiente para C2", para os métodos centrais. Vale também para o F3.
   - **Muda:** a frase "métodos de processamento desse endpoint" precisa distinguir os auxiliares (chamados várias
     vezes por requisição), que atingem C2 em todos os cenários.
   - **Muda:** o limiar efetivo observado é de cerca de 5.630 chamadas ao endpoint, não 5.000. A coluna "Tempo para
     C2" (≈87 min, ≈43 min) é uma projeção; o F2 real somou 4.334 chamadas.
2. **`metodologia(50).tex` l.125** (F2-S, "volume acima do limiar", "JIT plenamente otimizado", "nível não
   medido"): **muda**.
   - Com cerca de 6.480 chamadas, só parte dos métodos centrais chega a C2, e só nos últimos cerca de 2 min
     (716 s de 840 s); controller e `OrderService::getSummary` ficam em C1 até o fim.
   - O F2-S não isola o summary sob C2; mede o summary majoritariamente em C1, nos métodos da aplicação.
3. **`fargate(13).tex` §`sec:f2s-complementar` l.191, l.229 e a Tabela da l.305** ("condição mais favorável ao
   JIT", "equivalente mesmo sob a condição mais favorável ao JIT"): **muda a interpretação, não os números.**
   - Continua sendo a condição mais favorável *entre os cenários testados*.
   - Mas não é uma condição de JIT plenamente otimizado. A equivalência QJ × Native no F2-S passa a ser equivalência
     com o código da aplicação majoritariamente em C1.
4. **`fargate(13).tex` l.90** ("dispõe de tempo e volume de invocações para otimizar o código mais executado"):
   **confirmado e agora medido**: milhares de métodos em C2, 81 a 89% deles nos primeiros 5 min.
5. **`discussao(30).tex` l.57** (seção 6.3: "compatível com a convergência do JIT…, nível não medido…; projeção
   abaixo do limiar em F1 e F2"): **muda de hipótese para medido.**
   - Os métodos mais executados atingem C2 em minutos: por exemplo, o caminho do `GET /orders/{id}` em 47 a 292 s.
   - A compilação C2 segue ativa até o fim; "convergência" deve ser lida como aproximação, não estado final.
   - A parte do summary se confirma para os métodos centrais, e vale também no F3.
6. **Novo, útil para a metodologia:** `CICompilerCount=2` em 1 vCPU (uma thread C1 e uma C2 disputando a vCPU com
   a aplicação), medido por `jcmd VM.flags`.

## Arquivos

- `fase_b/`: cópia integral do S3 `s3://exp-jit-results-776648109551/full/` (258 MB), com:
  - `rodadas/<cen>-<rt>/`: `logs.jsonl.gz` (log bruto do CloudWatch), `codelist_bruto.txt`,
    `jcmd_vm_bruto.txt`, `meta.json`, `requests.csv.gz`, `k6_raw.json.gz`, `summary.json`;
  - `csv/`: `nivel_por_rodada`, `curva_nivel4`, `summary_path_nivel`, `deopt`, `integridade`;
  - `driver.log`, `teardown.log`, `STATUS`, `DONE` e `RESULTADOS_JIT_FARGATE_preliminar.md` (automático).
- `fase_b_caminho_get_order.txt`: caminho do `GET /orders/{id}`, extraído dos logs brutos.
- `summary_path_springboot.txt` e `summary_path_quarkus.txt`: listas de A2.
- `runner/`: scripts do driver e da análise.
- `NOTAS_execucao.md`: registro cronológico, com as correções durante a Fase A.
