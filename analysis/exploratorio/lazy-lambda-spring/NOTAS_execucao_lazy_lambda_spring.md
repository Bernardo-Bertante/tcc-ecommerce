# NOTAS de execução — teste exploratório "lazy" do Spring Boot (Lambda, 1ª chamada)

Exploratório, fora do desenho oficial. Réplica do teste do Quarkus JVM
(`../lazy-lambda/RESULTADOS_LAZY_LAMBDA.md`, `../lazy-lambda/NOTAS_execucao_lazy_lambda.md`).
Registro cronológico; horários locais -03:00 salvo indicação (Z = UTC).

## 2026-09-30 — Fase A1 (reconhecimento, só leitura)

- `aws sts get-caller-identity --profile pessoal` → `776648109551` (root). Confere.
- Resíduos do teste do Quarkus: nenhum recurso `exp-*` em Lambda, DynamoDB, EC2, volumes, IAM (roles e
  instance profiles), S3, logs `/aws/lambda/exp-*` e SSM.
- Cotas: EC2 On-Demand Standard vCPU = 32 (nenhuma instância ligada); Lambda ConcurrentExecutions = 1000
  (unreserved 1000). Folga ampla.
- Arquivos do Quarkus lidos: `RESULTADOS_LAZY_LAMBDA.md`, `NOTAS_execucao_lazy_lambda.md`, `driver/`, `infra/`,
  `variante_v1v2_src/`. Obs.: o relatório do Quarkus (linha 6) ainda aponta para `NOTAS_execucao.md`, mas o
  arquivo foi renomeado para `NOTAS_execucao_lazy_lambda.md` (ponteiro quebrado; não corrigido aqui).
- Código (`order-processor/springboot`, **Gradle 8.14.4** wrapper, Spring Boot 3.5.14, Spring Cloud Function
  4.1.3 (`spring-cloud-function-adapter-aws`), AWS SDK 2.25.70, `aws-lambda-java-core` 1.2.3):
  - Handler `org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest`; manifest do jar
    `Start-Class: com.tcc.orderprocessor.OrderProcessorApplication`.
  - Todos os componentes são singletons Spring comuns (sem `@Lazy`, sem `spring.main.lazy-initialization`):
    `SpringOrderProcessorFunction` (`@Bean Function<JsonNode, ProcessingResult> processOrder`),
    `LambdaRequestMapper` (`@Component`), `OrderProcessingService` (`@Service`), repositórios (`@Repository`),
    `DynamoDbClient` (`@Bean` em `DynamoDbConfig`, `DefaultCredentialsProvider`, **sem** `httpClientBuilder` →
    cliente HTTP padrão do SDK; `apache-client-2.25.70.jar` está no pacote; `netty-nio-client` também, só para
    cliente assíncrono, não usado), `ObjectMapper` próprio em `JacksonConfig` + `BeanPostProcessor` que configura o
    `JacksonMapper` do Spring Cloud Function.
  - `application.properties`: `spring.cloud.function.definition=processOrder`, `web-application-type=none`,
    tabelas via `PROCESSED_ORDERS_TABLE`/`STOCK_RESERVATIONS_TABLE` (default `processed_orders`/`stock_reservations`).
  - Mesmo domínio, mapper, service e repositórios do Quarkus (1 PutItem em processed + 1 por item em stock).
- `FunctionInvoker` 4.1.3 (lido por `javap`, sem fontes no cache): construtor sem argumento → `this(String)` →
  `start()`: `SpringApplicationBuilder(...).run()` (contexto completo), `JacksonMapper.configureObjectMapper`,
  `FunctionCatalog.lookup("processOrder")`, `setSkipOutputConversion`. `handleRequest`:
  `AWSLambdaUtils.generateMessage` (lê o evento; loga "Received: …" em INFO) → `FunctionInvocationWrapper.apply`
  (conversão da mensagem para `JsonNode` + chamada da função) → `AWSLambdaUtils.generateOutputFromObject` →
  cópia para o OutputStream.
- **Onde o contexto Spring sobe: no init.** Confirmado por código e pelo log do L1 oficial (02/07/2026, stream
  `…7017c9d7`): `INIT_START` 19:42:56.117Z → "Started OrderProcessorApplication in 2.952 seconds (process running
  for 3.71)" 19:42:59.846 → "Located function: 'processOrder'" 19:42:59.855 → `START` 19:42:59.860 →
  "AWSLambdaUtils : Received: {…}" 19:43:00.034 → `END` 19:43:02.535; REPORT Duration 2.674,70 ms, Init
  3.739,61 ms, Max Memory 224 MB. Logo o `DynamoDbClient` já é construído no init (diferente do Quarkus).
- Função oficial `order-processor-springboot` (leitura): `java21`, x86_64, **512 MB**, timeout 30 s, ephemeral
  512 MB, SnapStart None, PassThrough, Handler `FunctionInvoker::handleRequest`, role
  `order-processor-lambda-execution-role`, **`Environment` = null** (nenhuma variável, nem `JAVA_TOOL_OPTIONS`),
  sem camadas, sem VPC, só `$LATEST`, sem aliases, runtime management `Auto` (versão atual
  `…runtime:4ba7745a…a57c`), Function URL `AuthType NONE`.
  `CodeSha256 = ODLvR0a13wdABKP6LvMTo/xvKxTpEUz3H79fgDg0bbg=`, `LastModified 2026-06-21T14:14:06.878Z`.
- Zip oficial baixado (`get-function` → `Code.Location`): sha256 base64 `ODLvR0a1…bbg=` (confere).
- **Runtime do L1 do SB:** as 11 invocações da sessão 02/07 19:40–22:15Z têm `INIT_START Runtime Version:
  java:21.v68` (ARN `…runtime:9545bebf9b674e58101bf1ee53f999b7dd7fed2f7a93b34f48936163a2cdf4cd`) — **a mesma do
  L1 do Quarkus e do teste do Quarkus**. Sem confundidor de versão de runtime entre os dois relatórios.
- Build local (worktree `../ecommerce-tcc-exp-lazy-sb`, branch `exp/lazy-lambda-sb`, `./gradlew lambdaZip
  --offline`, OpenJDK 21.0.7 Debian): **77/77 entradas; 76 idênticas; o jar da aplicação difere só em metadados
  (33/33 entradas internas com conteúdo idêntico)**. Mesmo resultado registrado em `RESULTADOS_C2.md`.
- Preços (AWS Price List API, `aws pricing get-products`, us-east-1, consultados 30/09/2026):
  Lambda x86 Tier-1 US$ 0,0000166667/GB-s (pub. 2026-09-19); requests US$ 0,20/milhão; EC2 t3.micro Linux
  US$ 0,0104/h (pub. 2026-09-25); IPv4 público US$ 0,005/h (pub. 2026-09-17); DynamoDB on-demand
  US$ 0,625/milhão WRU (pub. 2026-09-11).

## 2026-09-30 — A3 aprovado (Bernardo)

Aprovado o plano com os padrões herdados + posição balanceada (6 permutações × 5, seed 20260930). Lembretes do
Bernardo: (1) a fumaça deve provar, em `infra/smoke_verificacao.txt`, gravações só em `exp-lazy-sb-*` (com o
marcador da V2), zero AccessDenied/sdk_fail/prep_fail, oficiais com WCU = 0 (com controle positivo), oficiais =
snapshot, V0 com o sha oficial, runtime v68 em todas, e V2 com a preparação terminando antes do fim do init;
(2) **se o Init da V2 na fumaça passar de 8 s, parar e avisar antes da Fase B**; (3) o resíduo da V2 no caminho de
conversão do Spring Cloud Function fica como está (registrar o valor; nenhuma variante nova sem perguntar).

## 2026-09-30 — A2 variantes (build) e driver

- Worktree `../ecommerce-tcc-exp-lazy-sb` (branch `exp/lazy-lambda-sb`, sem commit). `exp/LazyProbe.java` e
  `exp/ProbeInterceptor.java` copiados sem mudança do Quarkus. Novos: `exp/LazyProbeHandler.java` (wrapper do
  `FunctionInvoker`; pontos `init_wrapper_clinit`, `init_spring_in`, `init_end`, `w_in`, `w_out`) e
  `exp/LazyPrep.java` (`@Component` + `@EventListener(ApplicationReadyEvent)`; ponto `init_ready_event`; com
  `EXP_LAZY_PREP=1` faz os 5 passos do Quarkus; passo 1 só busca os beans já existentes, via `getBean`).
  Marcas nos mesmos lugares do Quarkus: `ctor_function` (método `@Bean processOrder`), `h_in`/`h_mapped`/`h_out`
  (dentro da lambda), `ctor_mapper`, `ctor_service`, `svc_*`, `ctor_repo_*`, `client_build_in/out` + interceptor.
- RIE local (`public.ecr.aws/lambda/java:21` + DynamoDB Local; tempos NÃO valem): V1 e V2 funcionam; na V1
  `client_build_in/out` tem `inv=0` (o cliente nasce no init, como os logs do L1 indicavam); na V2 a preparação
  inteira (`init_ready_event` → `prep_out` → `init_end`) sai antes de `INIT REPORT`; `JAVA_TOOL_OPTIONS` vazio;
  args com `-XX:+TieredCompilation …` impostos pelo bootstrap.
- Driver: cópia de `../lazy-lambda/driver` com nomes `exp-lazy-sb-*`, `/opt/exp-lazy-sb`, seed 20260930 e
  **ordem balanceada** (6 permutações × 5 sorteadas; smoke usa os 3 primeiros blocos da mesma lista). `extract.py`
  ganha os pontos de log `scf_received` ("AWSLambdaUtils : Received:", ms) e `spring_started` ("Started … in X
  seconds"). `analyze.py`: referência L1 `springboot`; controle só no Duration (≤ 10%); sinal V1×V0 > 5%;
  marcas do Spring (START→Received→h_in); tabela automática "mesmas operações" (V1 invoke × V2 init).
  Testado offline sobre os dados do Quarkus: reproduz 3,87× / 3,58× / 4,60× do relatório dele.
- `infra/verify_smoke.sh` reescrito com as provas pedidas (inclui runtime por amostra, sha da V0, e na V2
  `prep_out` ≤ INIT_START + Init Duration, antes do START, e Init ≤ 8.000 ms).

## 2026-09-30 — A4 infraestrutura (horários UTC)

- Snapshot dos oficiais antes de tudo: `infra/oficiais_antes.json` (3 funções: sha/RevisionId/LastModified/Env;
  3 tabelas: status/contagem/esquema; role). Esquema confirmado por leitura: `processed_orders` HASH orderId;
  `stock_reservations` HASH orderId + RANGE productId.
- 22:29Z bucket `exp-lazy-sb-results-776648109551` (bloqueio público, tag); tabelas `exp-lazy-sb-processed-orders`,
  `exp-lazy-sb-stock-reservations` (PAY_PER_REQUEST, tag); log groups `/aws/lambda/exp-lazy-sb-{v0,v1,v2}`
  (7 dias, tag); role `exp-lazy-sb-role` (`infra/policy-exp-lazy-sb-role.json`).
- Funções (java21, x86_64, 512 MB, 30 s, ephemeral 512, role exp-lazy-sb-role, tag `Projeto=tcc-exp-lazy-sb`):
  - `exp-lazy-sb-v0`: zip oficial, handler `FunctionInvoker::handleRequest`,
    `CodeSha256 ODLvR0a13wdABKP6LvMTo/xvKxTpEUz3H79fgDg0bbg=` (= oficial).
  - `exp-lazy-sb-v1`/`-v2`: zip instrumentado `L404Qp+XeWSAaSujHlNAfXB5lGJOeaOJxCkHlkbwSKI=`, handler
    `com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest`; V2 com `EXP_LAZY_PREP=1`.
  - Env: `PROCESSED_ORDERS_TABLE`, `STOCK_RESERVATIONS_TABLE` (exp-lazy-sb), `COLD_TOKEN`; oficial não tem nenhuma
    variável, então nada a replicar. Sem JAVA_TOOL_OPTIONS.
  - Build: Gradle 8.14.4 wrapper, OpenJDK 21.0.7 (Debian) local, Spring Boot 3.5.14, SCF 4.1.3, SDK 2.25.70.
  - **Runtime fixado em java:21.v68** (Manual, ARN `…9545bebf…cdf4cd`) nas 3 — **aceito** pela AWS.
- Role `exp-lazy-sb-driver-role` + profile `exp-lazy-sb-driver-profile` (`infra/policy-exp-lazy-sb-driver.json` +
  `AmazonSSMManagedInstanceCore`). `simulate-principal-policy` → `infra/simulate_policy.txt`: tudo oficial
  implicitDeny; exp-lazy-sb allowed; exp-lazy-sb-role PutItem/GetItem em tabelas oficiais implicitDeny.
- 22:34:25Z EC2 `exp-lazy-sb-driver` = **i-0a3e61312d3fe7b7e** (t3.micro, AL2023 ami-0b245cc5f82576748, subnet
  default us-east-1a, IP público, IMDSv2, shutdown→terminate). Driver em `s3://…/_driver/` → `/opt/exp-lazy-sb/`.
- ~22:35Z fumaça lançada (`systemd-run --unit=exp-lazy-sb-smoke MODE=smoke BLOCKS=3`).

## 2026-09-30 — A8 fumaça (RUN_ID smoke-20260930T223447Z, 22:34:47–22:38:35Z)

- 9/9 frias válidas (3 por variante), todas `java:21.v68`; V0 sha = oficial; 18 REPORT no CloudWatch (0 faltando).
- `infra/smoke_verificacao.txt` (saída de `infra/verify_smoke.sh`): gravações só em
  `exp-lazy-sb-processed-orders` (4 itens) e `exp-lazy-sb-stock-reservations` (9 itens), com o marcador
  `00000000-…` da V2; pontos `sdk_*` só com `table=exp-lazy-sb-*`; 0 AccessDenied/Exception/ERROR/sdk_fail/prep_fail
  nos 3 log groups e no run.log; tabelas oficiais com ConsumedWriteCapacityUnits = 0,0 em todos os minutos da
  janela (controle positivo: exp-lazy-sb com 7/7 e 9/21 WCU); funções oficiais com sha/RevisionId/LastModified
  iguais ao snapshot; na V2, `prep_out` ≤ fim do init (INIT_START + Init Duration) e antes do START nas 3 amostras;
  **Init da V2 na fumaça: 4.427,45 / 3.864,96 / 4.405,90 ms (máx. 4,43 s < 8 s)** → lançamento liberado pela regra.
- Relatório preliminar coerente (controle Duration −2,9%; V1×V0 +3,8%, abaixo do sinal de 5%). n = 3, não interpretado.
- **Autocorreção:** o rótulo da linha de referência em `analyze.py` estava fixo como "L1 oficial QJ" (herança do
  Quarkus), embora os valores já fossem do SB (filtro `runtime == "springboot"`). Corrigido para "L1 oficial SB" e a
  chave `l1_official_qj` → `l1_official_sb`; reenviado ao S3 e à EC2 antes do run completo (sha256 dos 5 scripts na
  EC2 = locais). O relatório preliminar da fumaça mantém o rótulo antigo.
- Cópia local: `infra/smoke_smoke-20260930T223447Z/`. Amostras da fumaça NÃO entram na análise final.

## 2026-09-30 — Lançamento da Fase B

- 22:40:07Z `systemd-run --unit=exp-lazy-sb-run MODE=full BLOCKS=30 /opt/exp-lazy-sb/run_all.sh`,
  RUN_ID `full-20260930T224007Z`; STATUS 22:40:30Z "RUNNING sample 2/90" (Fase B começou).
- Cronômetro de segurança: `exp-lazy-sb-safety.timer` → `teardown.sh SAFETY` às 00:00:07Z (01/10).
- Proteção final: `shutdown -h +110` → 00:30:07Z (01/10); shutdown-behavior=terminate.
- Pendências para a Fase C: `exp-lazy-sb-driver-role` + `exp-lazy-sb-driver-profile`, bucket (após conferir
  objetos), worktree `../ecommerce-tcc-exp-lazy-sb` e branch `exp/lazy-lambda-sb` (preservar fonte das variantes),
  imagem docker local `explazysb-v1` e a rede docker `explazysb-net`/contêineres de teste.

## 2026-09-30 — Fase B (sem supervisão) e Fase C

- Fase B: RUN `full-20260930T224007Z`, 22:40:07–23:10:51Z. `DONE`; o teardown automático apagou 3 funções,
  2 tabelas, `exp-lazy-sb-role` e 3 log groups (depois de confirmar os logs brutos no S3) e terminou a EC2.
  O cronômetro de segurança (00:00:07Z) e o `shutdown +110` não chegaram a disparar.
- Fase C (~23:30Z em diante): resultados baixados para `resultados_full-20260930T224007Z/`. Validação: 90/90 frias
  válidas na 1ª tentativa + 90 quentes; 180/180 REPORT no CloudWatch (todos os request_id batem); 180× status 200
  sem FunctionError; ordem executada = sorteio; cada variante 10× em cada posição; V0 sha = oficial (30/30);
  90× `java:21.v68`; oficiais iguais ao snapshot.
- Amostra atípica registrada: V1 bloco 29 (última do run), Init 2.452,73 / Duration 1.670,15 ms, com a mesma
  razão CPU/tempo (0,99 init; 0,29 inv1) — compatível com host mais rápido; mantida.
- Limpeza (aprovada pelo Bernardo, "prossiga fase c"): 54/54 objetos do bucket idênticos às cópias locais →
  `aws s3 rb --force`; `exp-lazy-sb-driver-profile` e `exp-lazy-sb-driver-role` apagados; fonte das variantes
  conferido (4 classes + patch idênticos à worktree) → worktree `../ecommerce-tcc-exp-lazy-sb` removida e branch
  `exp/lazy-lambda-sb` apagada; imagem `explazysb-v1`, rede `explazysb-net` e contêineres de teste removidos.
  Verificação 30/09 20:35 -03:00: zero recursos `exp-lazy-*` (Lambda, DynamoDB, EC2, volumes, IAM, S3, logs, SSM).
- H-CPU: busca de documentação não repetida (duas buscas no teste do Quarkus, 29 e 30/09, sem resultado).
- `.tex` lidos (só leitura) para a seção 9: `lambda(10).tex` (30/09 18:33) e `discussao(29).tex` (30/09 17:46);
  a frase citada no pedido ("como a mesma verificação não foi feita para o Spring Boot nem para o Native") não
  existe nessas versões — trechos descritos pelo conteúdo.
- **Autocorreção do relatório:** a faixa de `PutItem` da 1ª chamada da V2 saiu como 18,6–21,3 ms em um lugar
  (H-interpretado); o correto pelas medianas de `intervals.csv` é 18,4–21,3 ms (18,6 era de outro intervalo).
  Corrigido e uniformizado nas duas ocorrências.
- Relatório: `RESULTADOS_LAZY_LAMBDA_SPRING.md`.
