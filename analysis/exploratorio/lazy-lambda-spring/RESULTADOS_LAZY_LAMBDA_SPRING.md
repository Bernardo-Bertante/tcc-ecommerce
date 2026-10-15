# De onde vem o custo da primeira chamada do Spring Boot na Lambda (réplica do teste "lazy")

**EXPLORATÓRIO — fora do desenho experimental oficial. Não substitui nem altera os dados oficiais do L1.**

- **Execução:** 30/09/2026, 22:40:07–23:10:51 UTC (RUN_ID `full-20260930T224007Z`).
- **Fumaça:** no mesmo dia (`smoke-20260930T223447Z`, 9 amostras, fora da análise).
- **Registro completo:** `NOTAS_execucao_lazy_lambda_spring.md`.
- **Réplica de:** `../lazy-lambda/RESULTADOS_LAZY_LAMBDA.md` (Quarkus JVM), com o mesmo método, os mesmos scripts adaptados e os mesmos nomes de pontos.
- **Conta e região:** `776648109551`, us-east-1.
- **Recursos criados** (todos `exp-lazy-sb-*`, com a tag `Projeto=tcc-exp-lazy-sb`):
  - as 3 funções `exp-lazy-sb-v0`, `-v1` e `-v2`;
  - as tabelas DynamoDB `exp-lazy-sb-processed-orders` e `exp-lazy-sb-stock-reservations`;
  - as roles `exp-lazy-sb-role` e `exp-lazy-sb-driver-role`, mais o *instance profile* `exp-lazy-sb-driver-profile`;
  - a EC2 `exp-lazy-sb-driver` (`i-0a3e61312d3fe7b7e`);
  - o bucket `exp-lazy-sb-results-776648109551`;
  - 3 *log groups*.
- **Todos já foram apagados.**
  - O *teardown* automático removeu funções, tabelas, `exp-lazy-sb-role` e *log groups* e terminou a EC2.
  - A Fase C removeu a role e o *instance profile* do driver e o bucket; os 54 objetos foram conferidos contra as cópias locais, todos idênticos.
  - Verificação final em 30/09/2026, 20:35 -03:00: nenhum recurso `exp-lazy-*` em Lambda, DynamoDB, EC2, volumes, IAM, S3, logs ou SSM.
- **Dados** (em `resultados_full-20260930T224007Z/`):
  - `samples.jsonl` e `samples_final.csv`: uma linha por invocação;
  - `invocations.csv`: linhas `REPORT` e `INIT_START` do CloudWatch;
  - `points.csv`: linhas `EXP_LAZY`, mais as marcas de log do Spring `scf_received` e `spring_started`;
  - `intervals.csv`, `phases.csv` e `summary.json`: agregados gerados por `analyze.py`;
  - `raw/logs_*.jsonl.gz`: todos os eventos brutos do CloudWatch;
  - referência oficial: `l1_duration_postinit.csv`, cópia de `analysis/lambda/l1/`, só lida.
- **Origem dos números:** todos saem desses arquivos. Salvo indicação, são **medianas, com n = 30 por variante**. Os números do Quarkus JVM vêm do relatório dele.

## Diferenças em relação ao L1 oficial

| Aspecto | L1 oficial SB (02/07/2026) | Este teste |
|---|---|---|
| Função e tabelas | `order-processor-springboot`; `processed_orders`/`stock_reservations` | Cópias `exp-lazy-sb-*`; tabelas `exp-lazy-sb-*` (mesmo esquema, lido das oficiais); role própria |
| Variáveis de ambiente | nenhuma (`Environment` = null; sem `JAVA_TOOL_OPTIONS`) | `PROCESSED_ORDERS_TABLE`, `STOCK_RESERVATIONS_TABLE`, `COLD_TOKEN` (V2: + `EXP_LAZY_PREP=1`) |
| Runtime | java:21.v68 (Auto; as 11 invocações) | java:21.v68 fixado (Manual), conferido no `INIT_START` das 90 amostras. **Mesma versão do teste do Quarkus.** |
| Cold start | Expiração natural, 1 chamada a cada 15 min | **Forçado:** troca de `COLD_TOKEN`, espera por `Successful` (mediana 2,24 s), invocação |
| Invocação | Function URL (k6) | `Invoke` direto da API, com evento no formato Function URL |
| Payload | `makeProcessingRequestPayload(20000+k)`, k = 0..10 | O mesmo, gerado pelo próprio `data-generator.js`; o bloco b usa k = b mod 11 |
| Amostragem | n = 11 | 30 blocos V0/V1/V2 com **posição balanceada** (as 6 ordens × 5, sorteadas com seed 20260930; cada variante 10× em cada posição), concorrência 1, mais 1 chamada quente por amostra |
| Código | zip oficial | V0 = zip oficial (mesmo sha256); V1/V2 = mesmo bytecode + instrumentação (zip próprio) |

## 1. Variantes

- **V0 (controle).** O pacote publicado, com o handler original `org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest`. `CodeSha256 ODLvR0a13wdABKP6LvMTo/xvKxTpEUz3H79fgDg0bbg=`, igual ao da função oficial.
- **V1 (instrumentada).** Parte de um build local que reproduz o oficial: 77/77 entradas. O único jar que difere é o da aplicação, e só nos metadados; as 33 entradas internas têm conteúdo idêntico. Ferramentas: Gradle 8.14.4 e OpenJDK 21.0.7; Spring Boot 3.5.14, Spring Cloud Function 4.1.3 e AWS SDK 2.25.70. Sobre esse build entram:
  - as classes `LazyProbe` e `ProbeInterceptor` do teste do Quarkus, sem mudança;
  - um *wrapper* fino do `FunctionInvoker` (`LazyProbeHandler`);
  - marcas nos mesmos lugares do Quarkus.

  `CodeSha256 L404Qp+XeWSAaSujHlNAfXB5lGJOeaOJxCkHlkbwSKI=`. Nenhuma flag de JVM foi adicionada. As 60 amostras V1/V2 registram `JAVA_TOOL_OPTIONS` vazio e os argumentos que a Lambda impõe, inclusive `-XX:+TieredCompilation -XX:TieredStopAtLevel=1`.
- **V2 (preparação antecipada).** O mesmo zip da V1, com `EXP_LAZY_PREP=1`. Um `@EventListener(ApplicationReadyEvent)` roda dentro de `SpringApplication.run`, que o construtor do `FunctionInvoker` chama no init. A preparação repete os passos do Quarkus, na mesma ordem:
  1. busca os beans, que já existem porque são singletons criados na subida do contexto; nada é criado de novo;
  2. faz `readTree` + `toProcessingRequest` de um evento de marcação;
  3. faz 1 `GetItem` de uma chave inexistente;
  4. faz `service.process()` de um pedido de marcação com `orderId 00000000-0000-0000-0000-000000000000`, o que dá 1 `PutItem` em processed-orders e 3 em stock-reservations, no mesmo caminho da primeira chamada. Os itens de marcação não entram em nenhuma métrica;
  5. serializa o resultado.

  Ficou de fora da preparação o caminho de conversão do Spring Cloud Function (`generateMessage`, `FunctionInvocationWrapper`, `generateOutputFromObject`). Por decisão do Bernardo, esse resíduo foi mantido e só medido (seção 6).
- **Código-fonte:** `variante_v1v2_src/` e `variante_v1v2.patch`.

## 2. Resultados por variante (ms)

Mediana [Q1–Q3], mín.–máx.; n = 30 (L1: n = 11).

| Variante | Init Duration | Duration | Init + Duration (= Billed) | Duration da 2ª chamada |
|---|---|---|---|---|
| V0 | 3.834,0 [3.704,7–4.379,9] 3.244,3–4.844,7 | 2.751,8 [2.664,2–2.803,1] 2.524,3–2.996,6 | 6.630,5 [6.369,8–7.154,1] 5.855,7–7.841,3 | 83,1 [63,3–100,6] 48,8–139,0 |
| V1 | 3.839,0 [3.646,9–4.252,9] 2.452,7–4.759,3 | 2.729,7 [2.626,8–2.806,4] 1.670,2–2.949,1 | 6.588,4 [6.292,8–6.964,7] 4.122,9–7.693,1 | 111,1 [75,2–126,0] 45,1–176,3 |
| V2 | 4.539,0 [4.434,1–4.941,7] 4.188,2–5.447,7 | 304,0 [266,4–329,7] 233,9–382,3 | 4.832,1 [4.736,1–5.270,1] 4.449,2–5.810,4 | 106,3 [80,4–118,0] 50,6–171,0 |
| L1 oficial SB | 3.768,9 [3.668,6–3.821,2] 3.105,5–4.153,7 | 2.773,7 [2.693,1–2.815,7] 2.569,0–3.058,7 | 6.509,2 [6.330,8–6.643,1] 5.879,2–7.212,4 | — |

Outros dados:
- **Billed Duration:** igual a `Init + Duration` arredondado em todas as amostras (medianas: V0 6.631, V1 6.589, V2 4.832,5 ms).
- **Max Memory Used:** V0 224, V1 225 e V2 225 MB; no L1, 224 MB.
- **Intervalo entre o fim do init e o `START`:** mediana de 3,85–3,95 ms nas três variantes. Não houve pré-inicialização.
- **Amostra atípica:** a mínima da V1 (bloco 29, a última do run) tem todas as fases mais rápidas: Init 2.452,7 ms e Duration 1.670,2 ms. A razão CPU/tempo de parede é a mesma das outras (0,99 no init e 0,29 na 1ª chamada), o que é compatível com um *host* mais rápido. Ela não foi excluída, e as medianas não dependem dela.

## 3. Validação

**Integridade:**
- 90/90 cold starts válidos na 1ª tentativa, e as 90 chamadas quentes também. As 180 invocações retornaram 200, sem `FunctionError`.
- As 180 linhas `REPORT` foram encontradas no CloudWatch, e todos os `request_id` bateram.
- As 90 amostras frias rodaram na `java:21.v68`. A V0 tem o `CodeSha256` oficial nas 30 amostras.
- A ordem executada é igual ao sorteio, com cada variante 10× em cada posição.
- Zero ocorrências de `AccessDenied`, `sdk_fail` e `prep_fail`.
- As funções oficiais continuam iguais ao snapshot anterior ao teste (`infra/oficiais_antes.json`), conferido de novo na Fase C.

**Fumaça (`infra/smoke_verificacao.txt`):**
- gravações só nas tabelas `exp-lazy-sb-*`, com o marcador da V2;
- zero AccessDenied, Exception, ERROR, sdk_fail e prep_fail;
- ConsumedWriteCapacityUnits = 0,0 nas tabelas oficiais durante toda a janela, com controle positivo nas `exp-lazy-sb`;
- na V2, a preparação terminou dentro do init e antes do `START`, com Init máximo de 4,43 s (abaixo do limite de 8 s definido pelo Bernardo);
- isolamento das roles provado com `simulate-principal-policy` (`infra/simulate_policy.txt`).

**Controle, V0 × L1 oficial.** A regra pré-definida na A3 era |diferença das medianas de Duration| ≤ 10%. **Resultado: OK.**
- Duration: 2.751,8 × 2.773,7 ms, ou −0,8%. O intervalo bootstrap 95%, [−97,6; +88,6], inclui zero.
- Init (só reportado): 3.834,0 × 3.768,9 ms, ou +1,7%. O intervalo [−68,1; +585,4] inclui zero. A V0 tem cauda superior mais pesada: o Q3 de 4.379,9 ms passa do máximo do L1 (4.153,7 ms), como aconteceu no Quarkus. Aqui, porém, a diferença de medianas fica menor (+1,7% contra +5,2%).

**Instrumentação, V1 × V0.** A regra era sinalizar se passasse de 5% no Duration. **Resultado: não sinalizado.**
- Duration: −22,1 ms (−0,8%), bootstrap [−88,9; +47,0].
- Init: +4,9 ms (+0,1%).
- Soma: −42,2 ms (−0,6%).
- Na chamada quente, a V1 fica +28,0 ms acima (bootstrap [+0,7; +42,2]), compatível com o custo de imprimir as linhas `EXP_LAZY`. No Quarkus foram +23,1 ms.

## 4. Onde está o contexto Spring e o que sobra para a primeira chamada

**O contexto Spring é criado no init.** Isso foi confirmado de três formas:
- **Código:** o construtor do `FunctionInvoker` chama `start()`, que roda `SpringApplicationBuilder.run()` e depois `FunctionCatalog.lookup("processOrder")`.
- **Log do L1 oficial:** a sequência é "Started OrderProcessorApplication in 2.952 seconds" → "Located function 'processOrder'" → `START`.
- **Este teste:** o log "Started … in X seconds" marca mediana de 2,94 s na V0 e 2,90 s na V1. Os construtores dos beans e o `DynamoDbClient` têm `inv = 0` (init).

**Decomposição do init da V1** (fase `init`, 3.358,7 ms de parede):

| Trecho do init | Tempo (ms) | Classes | JIT (ms) | CPU da thread (ms) |
|---|---|---|---|---|
| Subida do Spring até o 1º bean da aplicação (`init_spring_in → ctor_mapper`) | 2.302,8 | 3.965 | 744 | 1.360,0 |
| **Construção do `DynamoDbClient`** (`client_build_in → out`) | **744,3** | 1.749 | 121 | 549,8 |
| Demais beans até o `ApplicationReadyEvent` (`ctor_function → init_ready_event`) | 219,3 | 276 | 64,5 | 156,0 |
| Lookup da função até o fim do init (`init_ready_event → init_end`) | 12,3 | 11 | 4 | 7,8 |

- Antes da fase: `INIT_START` → início da JVM, 147 ms; JVM → carga do *wrapper*, 428,5 ms.
- `init_spring_in → init_ready_event`: V1 3.348,0 ms e V2 3.392,4 ms.

**Decomposição da primeira chamada (V1)** (fonte: `intervals.csv`, fase `inv1`). A fase `w_in → w_out` dura 2.689,0 ms de parede e cobre 98% do Duration; antes dela (`START → w_in`) passam 2,0 ms, e depois (`w_out → fim`) 39,2 ms.

| Trecho da 1ª chamada | Tempo (ms) | % da fase | Classes | JIT (ms) | CPU da thread (ms) |
|---|---|---|---|---|---|
| Spring Cloud Function, entrada (`w_in → h_in`: `generateMessage` + conversão para `JsonNode`) | 215,6 | 8,0% | 138 | 3 | 62,5 |
| Jackson do mapper (`h_in → h_mapped`) | 182,5 | 6,8% | 120 | 5 | 48,0 |
| 1º `PutItem`: repositório → `beforeExecution` | 262,9 | | 266 | 1 | 67,5 |
| 1º `PutItem`: `beforeExecution → beforeTransmission` (serialização, credenciais, assinatura) | 384,6 | | 392 | 3 | 103,2 |
| 1º `PutItem`: **transmissão HTTP** (`beforeTransmission → afterTransmission`) | **1.347,5** | 50,1% | 899 | 226 | 256,9 |
| 1º `PutItem`: `afterTransmission → afterExecution` | 89,0 | | 71 | 0 | 23,5 |
| **1º `PutItem` completo** (os 4 trechos acima) | **2.084,0** | **77,5%** | | | |
| Spring Cloud Function, saída (`h_out → w_out`) | 104,3 | 3,9% | 28 | 45 | 20,6 |
| 2º `PutItem` (só a transmissão) | 21,0 | | 0 | 0,5 | 2,4 |

As porcentagens são a soma das medianas de cada trecho sobre a mediana da fase, que não é exatamente a mediana da soma. Resumo:
- **Framework (Spring Cloud Function):** 319,9 ms, 11,9% da primeira chamada. Pelas marcas de log (ms), `w_in → "Received:"` dura 162,5 ms e `"Received:" → h_in`, 59,0 ms. Na V0, código oficial, `START → "Received:"` dura 170,0 ms.
- **Cliente do SDK:** o objeto já está construído no init (744,3 ms). Na chamada, o que pesa é a **primeira requisição**: 2.084,0 ms, 77,5%, dos quais 1.347,5 ms na primeira transmissão HTTP.
- **Aplicação:** Jackson do mapper, 182,5 ms (6,8%). O serviço e o cálculo levam menos de 1 ms.
- **Totais da fase `inv1`:**
  - 1.916 classes carregadas;
  - 324,5 ms de JIT acumulado;
  - **223,5 ms de GC**, dos quais 181 ms dentro da primeira transmissão;
  - CPU da thread principal 595,1 ms e CPU do processo 770 ms.

## 5. Deslocamento para o init (V2 × V1)

| | V1 | V2 | Diferença (bootstrap 95%) |
|---|---|---|---|
| Init Duration | 3.839,0 | 4.539,0 | **+700,0** (+18,2%) [+484,2; +898,6] |
| Duration | 2.729,7 | 304,0 | **−2.425,7** (−88,9%) [−2.485,9; −2.371,6] |
| Init + Duration | 6.588,4 | 4.832,1 | **−1.756,3** (−26,7%) [−2.009,2; −1.506,8] |
| Duration da 2ª chamada | 111,1 | 106,3 | −4,8 (−4,3%) [−22,3; +21,3] |

**O custo migrou para o init e a soma caiu 26,7%.** A queda é menor que a do Quarkus (−52,2%) porque, no Spring Boot, só uma parte menor do trabalho estava na primeira chamada: o cliente já nascia no init. O trabalho em si não diminuiu; a CPU consumida é praticamente a mesma:
- **CPU do processo na V1, primeira chamada:** 770 ms.
- **CPU do processo na V2:** +715 ms no init (4.020 ms contra 3.305 ms na V1) mais 70 ms na primeira chamada, total de 785 ms.
- **Tempo de parede da preparação no init:** `prep_in → prep_out` levou 707,0 ms (611,7–816,3). A fase de init da V2 ficou 757,1 ms mais longa que a da V1.

**As mesmas operações nas duas fases** (V1 no invoke × V2 no init; `summary.json`, `same_ops_v1_invoke_vs_v2_init`):

| Operação | Invoke V1 (ms) | Init V2 (ms) | Razão | CPU da thread (invoke × init, ms) |
|---|---|---|---|---|
| Repositório → 1º `beforeExecution` | 262,9 | 67,1 | 3,92× | 67,5 × 56,4 |
| Serialização, credenciais e assinatura | 384,6 | 97,4 | 3,95× | 103,2 × 89,7 |
| 1ª transmissão HTTP | 1.347,5 | 362,8 | 3,71× | 256,9 × 233,1 |
| Pós-transmissão | 89,0 | 21,0 | 4,24× | 23,5 × 20,3 |
| Jackson (mapper) | 182,5 | 81,9 | 2,23× | 48,0 × 69,6 |

A 1ª transmissão compara o `PutItem` da V1 com o `GetItem` da V2; as duas carregam ~900 classes (899 e 895). A razão do Jackson é menor, e a CPU da thread nesse trecho é maior no init. Isso é compatível com o passo 2 da V2 incluir também o `readTree` do evento, que na V1 acontece dentro do Spring Cloud Function.

**CPU/tempo de parede** (`phases.csv`):

| Fase | V1 | V2 |
|---|---|---|
| Init | 0,99 (IQR 0,95–0,99) | 0,98 |
| 1ª chamada | 0,29 (IQR 0,28–0,29) | 0,30 |

O valor esperado a 512 MB é 512/1769 = 0,29 vCPU. Pelo `/proc/stat`, a fração ocupada é 0,47 de 2 vCPUs no init e 0,12 na primeira chamada; o `steal` fica em ~0.

**O que sobra na V2** (Duration 304,0 ms; fase `w_in → w_out` de 249,5 ms):
- **Resíduo do Spring Cloud Function** (não exercitado pela preparação; mantido e só medido, por decisão do Bernardo):
  - entrada `w_in → h_in` de 114,2 ms, sendo 48,5 ms até "Received:" e 63,0 ms de "Received:" até `h_in`;
  - saída `h_out → w_out` de 40,1 ms;
  - **total de 154,3 ms**, contra 319,9 ms na V1 e ~2 ms na 2ª chamada da V1.
- **Cada `PutItem`:** 18,4–21,3 ms (medianas por chamada), o tempo de regime (na 2ª chamada da V1, 18,8–22,1 ms).
- **`w_out` → fim:** 41,3 ms.
- **GC:** 0 ms. A preparação já coletou no init: 248,0 ms de GC no init da V2, contra 177,0 ms no da V1.

## 6. Resposta às hipóteses

| Hipótese | Veredito | Certeza | Números |
|---|---|---|---|
| **H-lazy**: componentes criados só no 1º uso | **Sustentada, na forma de "1º uso do SDK", não de "criação tardia do cliente"** | Alta (no escopo exploratório) | O `DynamoDbClient` já é construído no init (744,3 ms). Ainda assim, a **primeira requisição** deixa para a 1ª chamada 2.084,0 ms (77,5%). Esse trabalho interno do SDK e da pilha HTTP só acontece no 1º uso: carrega 899 classes na transmissão, mais 392 e 266 antes dela. Com a preparação no init, o Duration cai 88,9% (2.729,7 → 304,0) e o custo aparece no Init (+700,0). |
| **H-spring**: o contexto Spring / Spring Cloud Function fica para a 1ª chamada | **Não sustentada como causa principal** | Alta | O contexto sobe no init ("Started … in" mediana 2,90 s na V1), e o lookup da função também. Na 1ª chamada, o caminho de conversão do Spring Cloud Function custa 319,9 ms (11,9%): entrada 215,6 e saída 104,3. Em regime, custa ~2 ms. É um custo de 1º uso real, mas secundário. Na V2, que não o exercita, sobram 154,3 ms. |
| **H-classes**: carregamento de classes na 1ª chamada | **Sustentada como componente, não separável de H-lazy** | Média | 1.916 classes na 1ª chamada da V1 contra 50 na V2. Só a 1ª transmissão carrega 899. As classes carregam porque o SDK e a pilha HTTP são usados pela primeira vez. Sem JFR ou log de classes (fora do escopo), não dá para separar o tempo de carregar do tempo de executar. |
| **H-interpretado**: código ainda interpretado/C1 | **Não sustentada como causa principal; contribuição residual não separável** | Média | Na V2, os caminhos executados uma vez na preparação rodam em regime na 1ª chamada: `PutItem` de 18,4–21,3 ms contra 18,8–22,1 ms na 2ª chamada da V1. A 2ª chamada fica igual (111,1 × 106,3). O JIT acumula 324,5 ms na 1ª chamada da V1 e disputa a CPU com a thread principal, sem quantificação isolada. |
| **H-rede**: DNS/TCP/TLS na 1ª conexão (cliente Apache) | **Não sustentada como causa principal; resíduo não separável** | Média | A 1ª transmissão leva 1.347,5 ms no invoke e 362,8 ms no init, escalando 3,71× como os trechos puros de CPU (3,92–4,24×). As transmissões seguintes levam ~13–22 ms (medianas por chamada). A latência de rede em si deve ser da ordem de dezenas de ms; medi-la exigiria captura de pacotes na Lambda. |
| **H-CPU**: init com mais CPU que o invoke | **Sustentada empiricamente; mecanismo não documentado pela AWS** | Alta para o fenômeno, baixa para a causa | CPU/tempo de parede: 0,99 no init contra 0,29 na 1ª chamada (V1); 0,98 contra 0,30 (V2). As mesmas operações rodam 3,7–4,2× mais rápido no init com CPU de thread semelhante. É o mesmo fenômeno do Quarkus (0,98 contra 0,29). A busca por documentação não foi repetida (duas buscas no teste do Quarkus, sem resultado), então o mecanismo continua "não documentado". É um confundidor direto de V2 × V1: a queda da soma vem da mudança de fase, não de menos trabalho. |

**O que continua sem explicação:**
- quanto dos 2.084,0 ms do primeiro `PutItem` é carregamento de classes, quanto é JIT disputando a CPU, quanto é execução interpretada e quanto são os 181 ms de GC dentro da transmissão;
- a latência de rede exata do primeiro handshake TLS com o cliente Apache;
- os 154,3 ms do Spring Cloud Function que sobram na V2;
- a cauda superior do Init da V0 acima do máximo do L1;
- a amostra atípica rápida da V1 (seção 2).

## 7. Comparação descritiva com o Quarkus JVM

Os números do Quarkus vêm de `../lazy-lambda/RESULTADOS_LAZY_LAMBDA.md`, com o mesmo protocolo, o mesmo runtime (java:21.v68) e o mesmo tamanho de memória (512 MB). Medianas em ms.

| Variante | QJ Init | SB Init | QJ Duration | SB Duration | QJ Init + Duration | SB Init + Duration |
|---|---|---|---|---|---|---|
| V0 (zip oficial) | 1.454,8 | 3.834,0 | 5.500,8 | 2.751,8 | 6.968,3 | 6.630,5 |
| V1 (instrumentada) | 1.459,6 | 3.839,0 | 5.432,5 | 2.729,7 | 6.904,3 | 6.588,4 |
| V2 (preparação no init) | 2.927,2 | 4.539,0 | 347,1 | 304,0 | 3.298,0 | 4.832,1 |

**Decomposição da primeira chamada (V1):**

| Trecho | Quarkus JVM | Spring Boot |
|---|---|---|
| Construção do cliente do SDK | 2.759,7 ms **na 1ª chamada** (~51%) | 744,3 ms **no init** (0 na chamada) |
| 1º `PutItem` completo | 2.101,9 ms (~39%) | 2.084,0 ms (77,5%) |
| — só a 1ª transmissão HTTP | 1.255,7 ms (831 classes; `UrlConnectionHttpClient`) | 1.347,5 ms (899 classes; `ApacheHttpClient`) |
| Framework (Funqy / Spring Cloud Function), entrada + saída | 47,4 + 122,1 ms | 215,6 + 104,3 ms |
| Jackson do mapper | 201,0 ms | 182,5 ms |
| Classes carregadas na 1ª chamada | 3.331 | 1.916 |
| CPU/tempo de parede, init × 1ª chamada | 0,98 × 0,29 | 0,99 × 0,29 |
| Mesma operação no init (build do cliente, V2) | 730,7 ms | 756,3 ms (V2; V1: 744,3) |

**O que muda e o que não muda na ordem do Billed** (`Init + Duration`), sem concluir "quem é melhor":
- **Configuração publicada (V0/V1):** a ordem do L1 oficial se mantém. O Spring Boot fica abaixo do Quarkus JVM (V0: 6.630,5 × 6.968,3 ms, SB −4,8%). A razão principal é onde cada build cria o cliente do SDK: o Spring Boot no init, com ~1 vCPU; o Quarkus na 1ª chamada, com ~0,29 vCPU. O custo da primeira requisição é parecido nos dois (2.084,0 × 2.101,9 ms).
- **Com a preparação antecipada nos dois (V2):** a ordem se inverte. O Quarkus JVM fica abaixo (3.298,0 × 4.832,1 ms, SB +46,5%). Com o trabalho de primeiro uso no init, o que sobra é essencialmente o init de cada framework, e o do Quarkus é menor.
- **Ressalva:** a V2 não é a configuração oficial de nenhuma das duas versões, e a amostra é exploratória. Isso mostra que a ordem do Billed Duration no cold start depende de **em que fase** o trabalho de preparação cai, não uma propriedade fixa dos *runtimes*. Nada aqui vale para o Native.

## 8. Limitações

- Amostra exploratória: n = 30 por variante, uma sessão, um dia. Os intervalos bootstrap são descritivos, não confirmatórios.
- As cópias diferem da função oficial em vários pontos:
  - usam outras tabelas (mesmo esquema) e outra role (com `GetItem` a mais);
  - têm variáveis de ambiente que a oficial não tem;
  - são invocadas diretamente, sem Function URL;
  - o cold start é forçado, não por expiração natural.

  V0 × L1 mostra que isso preserva o Duration (−0,8%) e o Init (+1,7%, com cauda superior maior).
- V1/V2 trocam o Handler por um *wrapper* e acrescentam instrumentação. V1 × V0 mostra efeito de 0,8% no Duration e +28,0 ms na chamada quente.
- As marcas do Spring Cloud Function ("Received:", "Started") têm resolução de milissegundo (timestamp do logback), não de nanossegundo.
- A CPU por fase foi medida de dentro da VM (razão CPU/tempo de parede e `/proc/stat`). A política de alocação da AWS não é documentada e pode mudar.
- Mesma versão de runtime do teste do Quarkus (java:21.v68), mas em outro dia (29/09 × 30/09) e sem controle do hardware do *host*. Há uma amostra atípica rápida na V1.
- O teste é só sobre o Spring Boot. A comparação com o Quarkus JVM é descritiva e **nada aqui se aplica ao Native**.
- Nada disso substitui os dados oficiais do L1, que não foram tocados.

## 9. Implicação para o texto (sem editar)

Versões mais recentes em `~/Downloads`: `lambda(10).tex`, de 30/09 18:33, e `discussao(29).tex`, de 30/09 17:46 (o `discussao(30).tex` é mais antigo, de 28/09). A frase "como a mesma verificação não foi feita para o Spring Boot nem para o Native", citada no pedido, **não aparece** nessas versões. Os trechos vão identificados pelo conteúdo e pela linha em que estão nesses arquivos.

1. **`lambda(10).tex`, linha 49** (parágrafo que descreve a investigação exploratória só do Quarkus JVM: "cliente do SDK… 2,8 s… 5.432,5 → 347,1 ms… 0,98 × 0,29"). Pode ganhar uma frase sobre o Spring Boot:
   - no Spring Boot, o contexto e o cliente do SDK já são criados no init;
   - a primeira chamada (~2,7 s) é dominada pela primeira requisição ao DynamoDB (~2,1 s, ~78%), com ~12% no caminho de conversão do Spring Cloud Function;
   - antecipar o trabalho reduz o Duration em ~89% e a soma em ~27%;
   - a mesma razão de CPU entre fases aparece (0,99 × 0,29).
2. **`lambda(10).tex`, linha 67** (trecho final: "A inversão entre Spring Boot e Quarkus JVM refere-se, porém, à configuração avaliada, e não aos runtimes em si… a soma do Quarkus JVM caiu… de 6.904,3 ms para 3.298,0 ms"). Hoje só há o dado do Quarkus. Com este teste, o texto pode afirmar, com ressalva exploratória, o seguinte:
   - com a preparação antecipada nas duas versões, a soma do Spring Boot cai de 6.588,4 para 4.832,1 ms;
   - a ordem do Billed se inverte (QJ 3.298,0 × SB 4.832,1);
   - a inversão observada no L1 depende da fase em que cada build faz o primeiro uso do SDK.
3. **`discussao(29).tex`, linha 99** (descarte da *lazy initialization* para o regime aquecido: "Ela de fato ocorre no Quarkus JVM…").
   - O argumento continua válido e ganha um segundo caso: no Spring Boot, a preparação também não muda a 2ª chamada (111,1 × 106,3 ms).
   - A frase "ocorre no Quarkus JVM" pode ser ampliada: o custo de primeiro uso existe nas duas versões, mas está em lugares diferentes (criação do cliente no Quarkus; só a primeira requisição no Spring Boot).
   - A segunda explicação descartada no mesmo parágrafo (Funqy × Spring Cloud Function) segue intacta para o regime aquecido: o Spring Cloud Function custa ~2 ms por chamada em regime e ~320 ms só na primeira.
4. **`discussao(29).tex`, linha 170**, final do parágrafo ("A da origem do custo da primeira chamada do Quarkus JVM no Lambda… restringiu-se a essa versão… Repeti-las… com as demais versões e outros tamanhos de memória…").
   - A restrição "a essa versão" deixa de valer para o Spring Boot. Continua valendo para o Native, para outros tamanhos de memória e para o cold start por expiração natural.
   - A ressalva de CPU não documentada pela AWS se mantém.
5. **Sugestão para `08-known-problems`:** registrar como complemento da entrada do teste do Quarkus, com a mesma ressalva de escopo.
