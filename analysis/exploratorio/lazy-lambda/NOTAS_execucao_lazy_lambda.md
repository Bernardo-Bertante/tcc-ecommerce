# NOTAS de execução — teste exploratório "lazy" (Quarkus JVM, Lambda, 1ª chamada)

Exploratório, fora do desenho oficial. Registro cronológico (horário local, -03:00).

## 2026-09-29 — Fase A1 (reconhecimento, só leitura)

- 18:0x `aws sts get-caller-identity --profile pessoal` → conta `776648109551` (ARN root). Confere.
- Função oficial `order-processor-quarkus-jvm` (leitura, `get-function`):
  - `java21`, `x86_64`, 512 MB, timeout 30 s, ephemeral 512 MB, SnapStart `None`, tracing PassThrough.
  - Handler `io.quarkus.funqy.lambda.FunqyStreamHandler::handleRequest`.
  - **`Environment` = null** (nenhuma variável, nem `JAVA_TOOL_OPTIONS`); `Layers` = null; sem VPC.
    O stack CFN declara `PROCESSED_ORDERS_TABLE`/`STOCK_RESERVATIONS_TABLE`/`DYNAMODB_ENDPOINT`, mas a função
    publicada não tem nenhuma; o código usa os defaults `processed_orders`/`stock_reservations` e endpoint padrão.
  - Role `order-processor-lambda-execution-role` (só `dynamodb:PutItem` nas 2 tabelas + logs).
  - `CodeSha256 = qqGaGUSyL1rtWwcwOeIMNhFYfsW+HvIh8QiUTPe+WME=`, `LastModified 2026-06-21T14:14:23Z`, só `$LATEST`.
  - Runtime management: `Auto`; versão atual `arn:...:runtime:1a7a66b2...204e`.
  - Function URL `AuthType NONE`, `BUFFERED`.
- Zip oficial baixado (`get-function` → `Code.Location`): sha256 base64 = `qqGaGUSy…WME=` (confere).
- L1 oficial do QJ (CloudWatch, leitura): sessão 03/07/2026 16:58:49–19:28:49 UTC; `INIT_START Runtime Version:
  java:21.v68` (ARN `...runtime:9545bebf9b674e58101bf1ee53f999b7dd7fed2f7a93b34f48936163a2cdf4cd`).
  Exemplo 17:13: `INIT_START` 42,734 → log Quarkus "started in 1.078s" 44,103 → `START` 44,116 → `END` 49,894.
  Ou seja, o boot do Quarkus (`manualStart`) acontece **no init**, e os ~5,6 s ficam depois do `START`.
- Método do L1 (`benchmark/scenarios/l1_sparse_coldstart.js`): k6 `constant-arrival-rate` 1 req/15 min, 150 min
  (11 pontos), via **Function URL** (HTTP POST), payload `makeProcessingRequestPayload(iteration + 20000)`
  (iteration 0..10), seed 20260512. Cold start por **expiração natural** (todas as 11 têm `Init Duration`).
  Extração: `analysis/lambda/l1/l1_duration_postinit.py` (janela temporal, linhas `REPORT`).
- Código Quarkus (`order-processor/quarkus`, **Gradle 9.3.1**, Quarkus 3.35.2, AWS SDK 2.25.70, aws-crt 0.29.18):
  - `QuarkusOrderProcessorFunction`, `LambdaRequestMapper`, `OrderProcessingService`, repositórios: todos
    `@ApplicationScoped` → proxies; instância criada só na 1ª chamada de método.
  - `DynamoDbClient`: produtor `@Singleton` (`DynamoDbConfig`), `UrlConnectionHttpClient`,
    `DefaultCredentialsProvider`; injetado no construtor dos repositórios → criado só na 1ª chamada ao repositório.
  - Fluxo da chamada: mapper (Jackson `treeToValue`) → validator → calculator → `PutItem` em `processed_orders`
    → 1 `PutItem` por item em `stock_reservations` (1–3 itens).
  - `FunqyStreamHandler`: construtor chama `Quarkus.manualInitialize()`; `handleRequest` chama
    `Quarkus.manualStart()`. Mas o bytecode gerado registra `SnapStartRecorder.register(true)` (full warm-up
    do Quarkus ligado por padrão, mesmo com SnapStart da AWS desligado) → `manualInitialize` já chama
    `manualStart` no init. Também há `PreloadClassesBuildStep$preInit` (pré-carga de classes no static init).
- Build local (worktree `../ecommerce-tcc-exp-lazy`, branch `exp/lazy-lambda`, `./gradlew build -x test
  --offline`, OpenJDK 21.0.7 Debian): zip com sha256 diferente (`YQfCcv1p…hiA=`), mas **303/303 entradas com
  conteúdo idêntico** ao oficial (só metadados de zip diferem). V1/V2 partem do mesmo bytecode.
- Doc AWS "Understanding the Lambda execution environment lifecycle" (lambda-runtime-environment.html,
  consultada 29/09/2026): Init limitado a 10 s (senão é refeito no 1º invoke, com o timeout da função);
  on-demand "might occasionally initialize execution environments ahead of invocation requests".
  **Nenhuma menção a CPU diferente no Init.** H-CPU: não confirmado por fonte oficial até aqui.
- Cotas: Lambda `ConcurrentExecutions` 1000; EC2 On-Demand Standard vCPU 32; nenhuma EC2 ligada;
  nenhum recurso `exp-*` (Lambda, IAM, logs). Tabelas existentes: `processed_orders`, `processing-results`,
  `stock_reservations` (oficiais, não tocar).
- Notas lidas: `RESULTADOS_C2.md`, `exploratorio_cpu_lambda/RESULTADOS.md` (referência),
  `NOTAS_reset_dynamodb_lambda.md` (referência), `08-known-problems_20_.md` #24, #28, #33, #39, Extra A.

## 2026-09-29 — A3 aprovado (Bernardo), com 3 ajustes

1. Fumaça deve provar: gravações só em `exp-lazy-*`, zero `AccessDenied`, nenhuma escrita em tabela oficial.
2. V2: preparação inclui PutItem de item de marcação (chave fixa) em cada tabela exp-lazy, excluído da análise.
   Implementado como `service.process()` de um pedido de marcação com `orderId = 00000000-0000-0000-0000-000000000000`
   (1 PutItem em `exp-lazy-processed-orders` + 3 em `exp-lazy-stock-reservations`), mesmo caminho da 1ª chamada.
3. Registrar versão do runtime (INIT_START) por amostra; se `java:21.v68` for recusada, avisar antes de seguir.
Aprovados: 2 tabelas, invoke direto, v68, cold forçado, wrapper, N=30, custo, teardown.

## 2026-09-29 — A2 variantes (build)

- Worktree `../ecommerce-tcc-exp-lazy` (branch `exp/lazy-lambda`, sem commit). Classes novas em
  `com.tcc.orderprocessor.exp`: `LazyProbe`, `LazyProbeHandler` (wrapper do FunqyStreamHandler), `ProbeInterceptor`
  (ExecutionInterceptor do SDK), `LazyPrep` (`@Observes StartupEvent`, só age com `EXP_LAZY_PREP=1`).
  Marcas nos construtores (função, mapper, service, repositórios), handler, service e produtor do cliente.
- **Decisão:** V1 e V2 usam o **mesmo zip**; V2 difere só por `EXP_LAZY_PREP=1`. Assim V2−V1 isola a preparação.
- Checagem local (RIE `public.ecr.aws/lambda/java:21` + DynamoDB Local, Corretto 21.0.12.1): V1 e V2 funcionam;
  args da JVM incluem `-XX:+TieredCompilation -XX:TieredStopAtLevel=1` (imposto pelo bootstrap), `JAVA_TOOL_OPTIONS`
  vazio. Na V2 o StartupEvent/preparação roda antes de `INIT REPORT` (dentro do init). Tempos locais NÃO valem
  para a Lambda (CPU livre); só validação de código.
- Cargas do L1: `driver/l1_payloads.json` gerado com o próprio `benchmark/lib/data-generator.js`
  (`makeProcessingRequestPayload(20000+k)`, k=0..10, seed 20260512). Conferido por leitura: orderId do k=0 existe em
  `processed_orders` com o mesmo customerId.

## 2026-09-29 — A4 infraestrutura (UTC nos IDs da AWS; ~19:05–19:12 -03:00)

- Snapshot dos oficiais antes de tudo: `infra/oficiais_antes.json` (sha/RevisionId/LastModified das 3 funções,
  status/contagem das tabelas, role).
- Bucket `exp-lazy-results-776648109551` (bloqueio público total, tag). Tabelas `exp-lazy-processed-orders`
  (HASH orderId) e `exp-lazy-stock-reservations` (HASH orderId, RANGE productId), PAY_PER_REQUEST, tag.
  Log groups `/aws/lambda/exp-lazy-qj-{v0,v1,v2}`, retenção 7 dias, tag.
- Role `exp-lazy-role` (trust lambda): PutItem nas 2 tabelas exp-lazy, GetItem só em processed-orders,
  CreateLogStream/PutLogEvents em `/aws/lambda/exp-lazy-*` (`infra/policy-exp-lazy-role.json`).
- Funções (java21, x86_64, 512 MB, 30 s, ephemeral 512, role exp-lazy-role, tag):
  - `exp-lazy-qj-v0`: zip oficial baixado, handler Funqy original, `CodeSha256 qqGaGUSyL1rtWwcwOeIMNhFYfsW+HvIh8QiUTPe+WME=`
    (= oficial).
  - `exp-lazy-qj-v1`/`-v2`: zip instrumentado `RTtmKw35s7nPa1IzWSFMtzk8lznzf9Dy72LqBZdfSn4=`, handler
    `com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest`; V2 com `EXP_LAZY_PREP=1`.
  - Env comum: `PROCESSED_ORDERS_TABLE`, `STOCK_RESERVATIONS_TABLE` (exp-lazy), `COLD_TOKEN`. Sem JAVA_TOOL_OPTIONS.
  - Build: Gradle 9.3.1 wrapper, OpenJDK 21.0.7 (Debian) local, Quarkus 3.35.2, SDK 2.25.70.
- **Runtime fixado:** `put-runtime-management-config --update-runtime-on Manual --runtime-version-arn
  ...runtime:9545bebf…cdf4cd` (java:21.v68, a do L1 de julho) nas 3 — **aceito** pela AWS.
- 22:09Z invocação avulsa de teste da V1 (local, fora da janela de análise): `INIT_START Runtime Version:
  java:21.v68`; Init 1963,19 ms, Duration 5784,08 ms; EXP_LAZY ok; JVM args com `TieredStopAtLevel=1`; cpus=2;
  java 21.0.11.
- Role `exp-lazy-driver-role` + instance profile `exp-lazy-driver-profile` (`infra/policy-exp-lazy-driver.json`
  + `AmazonSSMManagedInstanceCore`). `simulate-principal-policy`: todas as ações em recursos oficiais =
  implicitDeny; em exp-lazy = allowed; exp-lazy-role PutItem/GetItem em tabelas oficiais = implicitDeny.
- EC2 `exp-lazy-driver` = **i-0598e47669b1414b0** (t3.micro, AL2023 ami-0b245cc5f82576748, subnet default
  us-east-1a, IP público, IMDSv2, shutdown→terminate), 22:12:05Z. AWS CLI 2.36.47, Python 3.9.25.
- Driver scripts em `s3://exp-lazy-results-776648109551/_driver/` → `/opt/exp-lazy/`.
- 22:12:45Z fumaça lançada (`systemd-run --unit=exp-lazy-smoke MODE=smoke BLOCKS=3`), RUN_ID `smoke-20260929T221245Z`.

## 2026-09-29 — A8 fumaça (RUN_ID smoke-20260929T221245Z, 22:12:45–22:16:33Z)

- 9/9 frias válidas (3 por variante), todas `java:21.v68`; V0 sha = oficial; 18 REPORT no CloudWatch (0 faltando).
- Verificação do ajuste 1 (`infra/verify_smoke.sh` → `infra/smoke_verificacao.txt`): gravações só em
  `exp-lazy-processed-orders` (4 itens) e `exp-lazy-stock-reservations` (9 itens), incluindo o marcador
  `00000000-…` da V2; pontos `sdk_*` só com `table=exp-lazy-*`; 0 `AccessDenied`/`Exception`/`ERROR` nos 3 log
  groups e no run.log; 0 `sdk_fail`/`prep_fail`; tabelas oficiais `processed_orders`, `stock_reservations`,
  `processing-results` com ConsumedWriteCapacityUnits = 0,0 em todos os minutos da janela (controle positivo:
  as exp-lazy mostram escrita); funções oficiais com sha/RevisionId/LastModified idênticos ao snapshot.
- Extração, análise e upload OK; teardown DRYRUN OK (logs brutos confirmados no S3). O teardown real não foi
  exercitado (só validado por simulate-principal-policy).
- Cópia local: `infra/smoke_smoke-20260929T221245Z/`. Amostras da fumaça NÃO entram na análise final
  (o extract do run full usa RUN_START_MS do run full e os request_ids do samples.jsonl do run full).

## 2026-09-29 — Lançamento da Fase B

- 22:17:55Z `systemd-run --unit=exp-lazy-run MODE=full BLOCKS=30 /opt/exp-lazy/run_all.sh`,
  RUN_ID `full-20260929T221755Z`; STATUS 22:18:19Z "RUNNING sample 2/90" (Fase B começou).
- Cronômetro de segurança: `exp-lazy-safety.timer` → `teardown.sh SAFETY` às 00:17:55Z (30/09).
- Proteção final: `shutdown -h +150` → 00:47:55Z (instância termina; shutdown-behavior=terminate).
- Pendências para a Fase C: apagar `exp-lazy-driver-role` + `exp-lazy-driver-profile`, bucket (após download),
  worktree `../ecommerce-tcc-exp-lazy` e branch `exp/lazy-lambda`; zips em scratchpad (v0.zip = oficial,
  v12.zip = instrumentado) — o zip instrumentado pode ser reconstruído da worktree.

## 2026-09-29/30 — Fase B (sem supervisão) e Fase C

- Fase B: RUN `full-20260929T221755Z`, 22:17:55–22:48:23Z. `DONE`; teardown automático apagou 3 funções,
  2 tabelas, `exp-lazy-role`, 3 log groups (depois de confirmar logs brutos no S3) e terminou a EC2. Cronômetro de
  segurança e `shutdown +150` não chegaram a disparar (a instância terminou antes).
- 30/09 Fase C: resultados baixados para `resultados_full-20260929T221755Z/`. Validação: 90/90 frias válidas na
  1ª tentativa, 180/180 REPORT no CloudWatch, ordem = sorteio, V0 sha = oficial, 90× java:21.v68, 180× status 200.
- Oficiais conferidos de novo: sha/RevisionId/LastModified iguais ao snapshot.
- H-CPU: nova consulta (WebSearch + blog AWS "Understanding and remediating cold starts", 07/08/2025): nenhuma
  fonte oficial compara CPU entre Init e Invoke → mantido como "não documentado".
- Limpeza (aprovada pelo Bernardo em 30/09): conferidos os 54 objetos do bucket contra cópias locais (todos
  idênticos) → `aws s3 rb --force`; `exp-lazy-driver-profile` e `exp-lazy-driver-role` apagados; worktree
  `../ecommerce-tcc-exp-lazy` removida e branch `exp/lazy-lambda` apagada (fonte preservado em
  `variante_v1v2_src/` + `variante_v1v2.patch`); imagem docker local `explazy-v1` removida.
  Verificação 05:47 -03:00: zero recursos `exp-lazy-*` (Lambda, DynamoDB, EC2, volumes, IAM, S3, logs, SSM).
- Relatório: `RESULTADOS_LAZY_LAMBDA.md`.
