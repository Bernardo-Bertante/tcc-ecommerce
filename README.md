# tcc-ecommerce

Este é o repositório do Trabalho de Conclusão de Curso **"Redução do *cold start* de aplicações Java em ambientes *serverless*: efeitos sobre o desempenho e o custo na AWS"**.

- Autor: Bernardo Bertante Martins.
- Curso: Ciência da Computação, Universidade Federal de Lavras (UFLA), 2026.
- Orientador: Prof. Dr. Bruno de Abreu Silva.

O trabalho compara três versões de dois serviços de um sistema de comércio eletrônico:

- Spring Boot em JVM;
- Quarkus em JVM;
- Quarkus compilado antecipadamente com o GraalVM *Native Image*.

Os dois serviços rodam em ambientes diferentes:

- O *Order Service* roda no Amazon ECS Fargate.
- O *Order Processor* roda no AWS Lambda.

Aqui estão o código das versões, os cenários de carga, os dados de cada cenário, os scripts de análise e as investigações exploratórias, inclusive as que o texto cita.

## Como o experimento foi executado

- **ECS Fargate**
  - Os cenários de carga usaram uma única *task* de 1 vCPU e 2 GB, acessada pelo IP público, sem balanceador de carga nem escalonamento automático.
  - Cada rodada criou uma *task* nova (`stop-task` → `run-task`) e esvaziou as tabelas do RDS (`TRUNCATE`).
  - O banco foi um PostgreSQL `db.t3.micro`.
  - Os scripts versionados que aplicam esse protocolo são `benchmark/run/f1_rerun.sh` (F1) e `benchmark/run/f3_rerun.sh` (F3).
  - O script da coleta de julho, de onde vem o F2, ficava em `/tmp` e se perdeu. O que foi possível reconstituir dele está em `analysis/investigacao_repouso_entre_rodadas/`.
  - A alocação de 1 vCPU e 2 GB aparece nas constantes `CPU_UNITS` e `MEM_MB` dos scripts `analysis/fase5_recursos_*.py` e nos `task_running.json` da reprodução do F3 (`analysis/reproducao_f3_instabilidade/`). A *task definition* da coleta oficial não está versionada; o `infrastructure/aws/fargate-task-def.json` está vazio.
- **AWS Lambda**
  - As funções usaram 512 MB e foram acessadas por *Function URL*.
  - O *runtime* foi `java21` nas versões JVM e `provided.al2023` na versão nativa.
- **Repetições**
  - Os cenários de carga foram repetidos cinco vezes por versão.
  - No L1, foram 11 invocações espaçadas de 15 minutos.
  - O *benchmark* de inicialização do contêiner (H1b) teve dez ciclos `stop-task` → `run-task` por versão, e o último ciclo foi excluído nas três versões.

Alguns arquivos do desenho inicial não correspondem a essa configuração:

- O template `infrastructure/aws/order-service-stack.yaml` cria um balanceador de carga (ALB) e escalonamento automático por CPU. Nenhum dos dois foi usado nas medições do TCC. O mesmo template e o `infrastructure/aws/scripts/deploy-order-service-stack.sh` têm como padrão uma *task* de 8 vCPU e 16 GB.
- O `benchmark/docs/fargate-runbook.md` descreve um dimensionamento anterior: *task* de 8 vCPU e 16 GB, banco `db.t3.medium` e F1 a 30 req/s. O TCC usou 1 vCPU e 2 GB, `db.t3.micro` e F1 a 48 req/s (Seções 3.1, 3.4 e 3.5.2).
- O template `infrastructure/aws/order-processor-stack.yaml` tem 1024 MB como memória padrão das funções, mas o TCC usou 512 MB.

## Mapa do repositório

| Pasta | Conteúdo | No texto |
|---|---|---|
| `order-service/springboot`, `order-service/quarkus` | *Order Service* (REST, PostgreSQL reativo) | Seções 3.2 e 3.3 |
| `order-processor/springboot`, `order-processor/quarkus` | *Order Processor* (função Lambda, DynamoDB) | Seções 3.2 e 3.3 |
| `benchmark/scenarios`, `benchmark/lib` | Cenários do k6 | Seção 3.5 |
| `benchmark/run` | Execução dos cenários no Fargate e no Lambda | Seções 3.1 e 3.5 |
| `analysis/fargate`, `analysis/lambda` | Dados de cada cenário (resumos do k6, latências, *logs* extraídos do CloudWatch) | Capítulo 4 |
| `analysis/reducao` | Script, CSVs e figuras de onde vêm os números e os gráficos do texto | Capítulos 4 e 5 |
| `analysis/exploratorio*`, `analysis/investigacao_*` e outras | Investigações exploratórias (ver a lista abaixo) | Capítulos 3 a 5 |
| `infrastructure/aws` | Templates, políticas e configuração das funções | Seção 3.4 |

### Cenários e dados

| Cenário | Script do k6 | Dados |
|---|---|---|
| F1 | `f1_low_load.js` | `analysis/fargate/fase3-f1-rerun/` (recoleta de agosto) |
| F2 | `f2_high_load.js` | `analysis/fargate/fase3/` (coleta de julho; a pasta também tem F1 e F3 de julho, que não entram no texto final) |
| F3 | `f3_black_friday_controlled.js` | `analysis/fargate/fase3-f3-rerun/` (recoleta de setembro) |
| H1b | — | `analysis/fargate/h1b/` (os nove valores usados e os dez ciclos coletados) |
| L1 | `l1_sparse_coldstart.js` | `analysis/lambda/l1/` |
| L2 | `l2_warm_burst.js` | `analysis/lambda/fase4/` |
| L3 | `l3_concurrency_burst.js` | `analysis/lambda/fase4/` |

Arquivos de versões anteriores que ficaram fora do texto final:

- **F2-S:** o cenário `f2s_summary_only.js` e os dados em `analysis/fargate/fase3b/`.
- **Desenho inicial com escalonamento:** os cenários `f3_burst_autoscaling.js` e `f3s_stress_300.js`.
- **Rampa de descoberta do teto do banco:** os cenários `teto_descoberta*.js`. A rampa é descrita na Seção 3.5.2, mas seus dados não entram nas tabelas.

## Números do texto

Os números das tabelas e das figuras do texto final vêm de `analysis/reducao/`. A exceção é a memória máxima do L1, que vem de `analysis/fase5/fase5_l1_memoria_novo.csv` (ver o `LEIAME.md` da pasta). Para conferir, execute a partir da raiz do repositório (requer `numpy` e `scipy`):

```bash
python3 analysis/reducao/reducao_estatistica.py analysis saida_conferencia
```

Os cinco CSVs gerados devem ser iguais aos de `analysis/reducao/`. O `LEIAME.md` dessa pasta descreve cada arquivo, as fontes e os cuidados ao citar. A seção "Reprodutibilidade", no fim deste README, lista os CSVs de versões anteriores do texto, em `analysis/fase5/`.

## Investigações exploratórias

As investigações abaixo foram conduzidas fora do desenho experimental, com poucas repetições. O texto as trata como indicativas. A tabela lista as seções principais; as citadas são retomadas também nas limitações (Seção 5.4) e na Conclusão.

As notas de cada pasta foram escritas durante o trabalho. Por isso, citam números de seção de versões anteriores do texto (por exemplo, "§6.3") e um registro interno, o `08-known-problems.md`, que não está no repositório.

| Investigação | Pasta | Onde aparece no texto final |
|---|---|---|
| Primeira chamada mais lenta no Lambda, Quarkus JVM | `analysis/exploratorio/lazy-lambda/` | Seções 4.1 e 5.1 |
| Primeira chamada mais lenta no Lambda, Spring Boot | `analysis/exploratorio/lazy-lambda-spring/` | Seções 4.1 e 5.1 |
| Curva de aquecimento por ambiente (L2 e L3) | `analysis/lambda/fase4/warmup_curve/` | Seção 4.2 |
| Cliente HTTP do SDK do DynamoDB (ambiente local) | `analysis/exploratorio_cpu_lambda/` | Seções 4.2 e 5.2 |
| Compilação C1 × C2 no Lambda (ambiente local) | `analysis/exploratorio_c2_lambda/` | Seção 5.2 |
| Nível de compilação JIT no Fargate | `analysis/exploratorio/jit-fargate/` | Seção 5.2 |
| Validação de conexões e carga no RDS | `analysis/pg_stat_statements_rds/` | Seções 4.2, 5.2 e 5.3 |
| Instabilidade do Spring Boot no F3 (reprodução na AWS) | `analysis/reproducao_f3_instabilidade/` | Seções 4.2 e 5.2 |
| Instabilidade do Spring Boot no F3 (reexame documental) | `analysis/investigacao_instabilidade_f3_setembro/` | Seção 4.2 (datas das rodadas), sem citação nominal |
| Custo de *build* e tamanho das imagens | `analysis/exploratorio_build/` | Seções 5.1 e 5.3 |
| Intervalo real entre rodadas no Fargate | `analysis/investigacao_repouso_entre_rodadas/` | Seção 3.1 |
| DynamoDB sem reinicialização entre repetições | `analysis/investigacao_reset_dynamodb_lambda/` | Seção 3.4 |
| Coleta de lixo no F1 e no F3; decomposição da CPU do Spring Boot | `analysis/exploratorio_gc_f1/`, `analysis/exploratorio_gc_f3/`, `analysis/exploratorio_pilha_fargate/` | Não citadas na versão final |

## Desenvolvimento local e implantação

As seções a seguir descrevem como subir as versões localmente e na AWS. Elas foram escritas durante o desenvolvimento.

### Stack local de benchmark do Order Service

O arquivo `infrastructure/docker-compose.benchmark.yml` sobe as três variantes do Order Service ao mesmo tempo, todas conectadas a um PostgreSQL compartilhado:

| Variante | URL local | Health endpoint | Imagem |
| --- | --- | --- | --- |
| Quarkus Native | `http://localhost:8081` | `/q/health` | `order-service-quarkus:native` |
| Quarkus JVM | `http://localhost:8082` | `/q/health` | `order-service-quarkus:jvm` |
| Spring Boot JVM | `http://localhost:8083` | `/actuator/health` | `order-service-springboot:jvm` |
| PostgreSQL compartilhado | `localhost:55434` | `pg_isready` | `postgres:16-alpine` |

Antes de subir o Compose, gere os artefatos que os Dockerfiles copiam para as imagens:

```bash
cd order-service/springboot
./gradlew clean bootJar --no-daemon

cd ../quarkus
./gradlew clean build --no-daemon
./gradlew build -Dquarkus.native.enabled=true -Dquarkus.package.jar.enabled=false -Dquarkus.native.container-build=true -Dquarkus.native.native-image-xmx=6g --no-daemon
```

Depois, a partir da raiz do repositório:

```bash
docker compose -f infrastructure/docker-compose.benchmark.yml up --build -d
```

Verifique a prontidão das três aplicações:

```bash
curl --fail http://localhost:8081/q/health
curl --fail http://localhost:8082/q/health
curl --fail http://localhost:8083/actuator/health
```

Para encerrar e remover o banco efêmero do benchmark:

```bash
docker compose -f infrastructure/docker-compose.benchmark.yml down -v
```

Os cenários em `benchmark/` ainda devem ser executados apontando para uma URL por vez. Use `http://localhost:8081`, `http://localhost:8082` ou `http://localhost:8083` conforme a variante que será medida.

### Fluxo local -> AWS do Order Service

O template `infrastructure/aws/order-service-stack.yaml` vem do desenho inicial. Ele cria uma VPC simples, ALB público, três services ECS/Fargate, RDS PostgreSQL privado para as tasks, log groups do CloudWatch, autoscaling por CPU e uma task one-off para reset do banco. Nas medições do TCC, não foram usados o ALB nem o autoscaling: a carga foi aplicada a uma única task pelo IP público (ver "Como o experimento foi executado", no início deste README).

O pipeline usa três imagens ECR, uma para cada variante:

- `order-service-springboot`
- `order-service-quarkus-jvm`
- `order-service-quarkus-native`

Prepare as imagens localmente sem enviar para AWS:

```bash
./infrastructure/aws/scripts/prepare-order-service-images.sh \
  --image-tag order-service-test
```

Para buildar, criar/validar repositórios ECR, fazer login e enviar as imagens:

```bash
./infrastructure/aws/scripts/push-order-service-images.sh \
  --profile meu-profile \
  --region us-east-1 \
  --image-tag order-service-test
```

O script grava os URIs em `infrastructure/aws/build/order-service/image-uris.env`.

Para fazer push e deploy em uma etapa, informe uma senha para o PostgreSQL RDS e forneça um CIDR de ingresso explícito (não use 0.0.0.0/0):

```bash
./infrastructure/aws/scripts/deploy-order-service-stack.sh \
  --profile pessoal \
  --region us-east-1 \
  --stack-name order-service-benchmark \
  --image-tag order-service-test \
  --database-password 'troque-esta-senha' \
  --db-engine-version 16.14 \
  --benchmark-ingress-cidr "$(curl -s https://checkip.amazonaws.com)/32"
```

Nota: `0.0.0.0/0` deve ser usado apenas temporariamente para *debugging* local e **jamais** como padrão recomendado. Em geral, use o IP público do operador do runner em `/32` ou uma faixa CIDR restrita.

Observação sobre roles de laboratório: alguns ambientes de laboratório fornecem uma role `LabRole` pré-criada; essa é uma opção de compatibilidade para o fluxo *lab-only*. O fluxo de conta pessoal padrão usa descoberta dinâmica do ID da conta via `aws sts` e não deve depender de `LabRole`.

Para reduzir exposição, troque `--benchmark-ingress-cidr` pelo IP/CIDR da máquina que rodará o k6. O script imprime os outputs da stack ao final, incluindo:

- `QuarkusNativeBaseUrl` na porta `8081`
- `QuarkusJvmBaseUrl` na porta `8082`
- `SpringBootBaseUrl` na porta `8083`

Antes do benchmark final, faça smoke curto em AWS:

```bash
FARGATE_VERSIONS="quarkus-native|http://ALB_DNS:8081 quarkus-jvm|http://ALB_DNS:8082 springboot|http://ALB_DNS:8083" \
  SMOKE=true \
  REPETITIONS=1 \
  VERSION_REST_SECONDS=0 \
  FARGATE_SCENARIOS="f1_low_load f2s_summary_only" \
  benchmark/run/run-fargate.sh
```

Para evitar viés no endpoint `GET /orders/summary`, use reset de banco antes dos blocos comparáveis:

```bash
infrastructure/aws/scripts/reset-order-service-db.sh \
  --profile meu-profile \
  --region us-east-1 \
  --stack-name order-service-benchmark
```

No runner, isso pode ser automatizado com `RESET_DB_COMMAND`. No TCC, o F3 foi executado na AWS com task fixa (`benchmark/scenarios/f3_black_friday_controlled.js`, por `benchmark/run/f3_rerun.sh`), sem autoscaling.

### Stack local do Order Processor

O arquivo `infrastructure/docker-compose.processor.yml` sobe o DynamoDB Local, cria as tabelas do processor e expõe as funções Lambda locais para desenvolvimento:

| Serviço | Uso local | Imagem |
| --- | --- | --- |
| DynamoDB Local | `http://localhost:8000` | `public.ecr.aws/aws-dynamodb-local/aws-dynamodb-local:latest` |
| Init das tabelas | `processed_orders` e `stock_reservations` | `public.ecr.aws/aws-cli/aws-cli` |
| Spring Boot Lambda | `http://localhost:9001/2015-03-31/functions/function/invocations` | `order-processor-springboot:lambda` |
| Quarkus Lambda | `http://localhost:9002/2015-03-31/functions/function/invocations` | `order-processor-quarkus:lambda-jvm` |
| Quarkus Native Lambda | `http://localhost:9003/2015-03-31/functions/function/invocations` | `order-processor-quarkus:lambda-native` |

Antes de subir o Compose, gere os artefatos Lambda das variantes Spring Boot e Quarkus JVM:

```bash
cd order-processor/springboot
./gradlew clean build --no-daemon

cd ../quarkus
./gradlew clean build --no-daemon
```

O build Spring Boot gera dois artefatos principais:

- `order-processor/springboot/build/libs/order-processor-springboot-0.0.1-SNAPSHOT.jar`, o JAR fino da aplicação.
- `order-processor/springboot/build/distributions/order-processor-springboot-0.0.1-SNAPSHOT-lambda.zip`, o pacote JVM para Lambda com o JAR e as dependências em `lib/`.

O build Quarkus JVM gera `order-processor/quarkus/build/function.zip`, o pacote JVM para Lambda/Funqy, e `order-processor/quarkus/build/order-processor-quarkus-0.0.1-SNAPSHOT-runner.jar`.

Para compilar a variante Quarkus Native depois da JVM passar, execute em `order-processor/quarkus`:

```bash
./gradlew build \
  -Dquarkus.package.type=native \
  -Dquarkus.native.container-build=true \
  -Dquarkus.native.native-image-xmx=6g \
  --no-daemon
```

A Lambda nativa usa runtime customizado (`provided.al2023`) e o mesmo `build/function.zip`, agora contendo o `bootstrap` e o executável nativo. Como o Quarkus reutiliza esse nome de artefato para JVM e Native, construa/tagueie a imagem JVM antes do build nativo quando precisar das duas variantes locais ao mesmo tempo.

A configuração mínima de handoff das Lambdas Spring Boot, Quarkus JVM e Quarkus Native está em `infrastructure/aws/lambda-config.json`. Ela registra os nomes AWS das três funções, o runtime Java 21 nas variantes JVM, o runtime `provided.al2023` na variante nativa, o handler Spring `org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest`, o handler Quarkus Funqy `io.quarkus.funqy.lambda.FunqyStreamHandler::handleRequest`, a função/export `processOrder`, os artefatos gerados e os artefatos AWS preparados em `infrastructure/aws/build/artifacts/`.

Em AWS, configure `AWS_REGION`, `PROCESSED_ORDERS_TABLE` e `STOCK_RESERVATIONS_TABLE`. Não configure `DYNAMODB_ENDPOINT` na Lambda em produção; sem endpoint customizado, o cliente DynamoDB usa as credenciais padrão da execução Lambda. O `DYNAMODB_ENDPOINT` é apenas para DynamoDB Local, e dentro do Compose deve apontar para `http://dynamodb-local:8000`.

As permissões mínimas para as roles de execução continuam documentadas em `infrastructure/aws/order-processor-springboot-dynamodb-policy.json` e `infrastructure/aws/order-processor-quarkus-dynamodb-policy.json`, mas a stack AWS agora cria automaticamente uma role compartilhada equivalente para as três funções, junto com os log groups do CloudWatch Logs.

As permissões de observabilidade e benchmark ficam separadas em `infrastructure/aws/order-processor-benchmark-operator-policy.json`. Essa policy deve ser usada pela identidade que executa os cenários e coleta métricas, não pela Lambda. Ela permite ler CloudWatch Metrics, ler CloudWatch Logs das funções `order-processor-*`, inspecionar configuração/concurrency/Function URL das Lambdas e invocar funções `order-processor-*` quando o benchmark usar invocação direta via AWS SDK ou Function URL com `AWS_IAM`. Essas permissões suportam a coleta de `Init Duration`, `Duration`, `Max Memory Used`, `Errors` e `Throttles` nos cenários L1/L2/L3.

### Fluxo local -> AWS do Order Processor

O fluxo recomendado separa a validação local do provisionamento real em AWS:

1. Local: validação funcional, smoke test curto e calibração leve.
2. AWS: benchmark oficial, coleta final de métricas e comparação metodológica.

Para manter o método de invocação consistente entre Spring Boot JVM, Quarkus JVM e Quarkus Native, a stack AWS usa **Function URL para as três funções**. O auth type padrão é `NONE`, para simplificar o uso com k6. Se você precisar usar `AWS_IAM`, troque o parâmetro em todas as três ao mesmo tempo.

#### Infraestrutura AWS mínima

O template `infrastructure/aws/order-processor-stack.yaml` cria:

- DynamoDB `processed_orders`
- DynamoDB `stock_reservations`
- uma role IAM compartilhada para as três Lambdas
- log groups do CloudWatch Logs para cada função
- `order-processor-springboot`
- `order-processor-quarkus-jvm`
- `order-processor-quarkus-native`
- uma Function URL por função

#### Pipeline de empacotamento e deploy

Primeiro, congele os artefatos AWS em caminhos estáveis. Esse passo **não precisa de acesso AWS**:

```bash
./infrastructure/aws/scripts/prepare-order-processor-artifacts.sh
```

Esse script resolve o detalhe metodológico do Quarkus: o `build/function.zip` é reutilizado entre JVM e Native, então ele copia o pacote JVM para `infrastructure/aws/build/artifacts/order-processor-quarkus-jvm-function.zip` antes do build nativo, e depois congela o pacote Native em `infrastructure/aws/build/artifacts/order-processor-quarkus-native-function.zip`.

Para empacotar a stack para CloudFormation, use um bucket S3 já existente. Esse passo **precisa de acesso AWS**:

```bash
./infrastructure/aws/scripts/package-order-processor-stack.sh \
  --artifact-bucket meu-bucket-deploy \
  --artifact-prefix order-processor-benchmark
```

O comando acima gera `infrastructure/aws/build/packaged/order-processor-stack.packaged.yaml`.

Para empacotar e fazer o deploy em uma única etapa:

```bash
./infrastructure/aws/scripts/deploy-order-processor-stack.sh \
  --stack-name order-processor-benchmark \
  --artifact-bucket meu-bucket-deploy \
  --artifact-prefix order-processor-benchmark \
  --function-url-auth-type NONE \
  --lambda-memory-size 512 \
  --lambda-timeout-seconds 30 \
  --log-retention-days 14
```

O TCC usou 512 MB nas três funções; o padrão do template é 1024 MB.

O script imprime os outputs da stack ao final, incluindo:

- `SpringBootFunctionUrl`
- `QuarkusJvmFunctionUrl`
- `QuarkusNativeFunctionUrl`

Essas três URLs HTTP(S) são a entrada padronizada recomendada para os cenários k6 em AWS. Não misture Function URL em uma variante e `InvokeFunction` direto em outra.

Os scripts também aceitam `--profile` e `--region` para usar perfis/regiões diferentes do AWS CLI.

Depois, a partir da raiz do repositório:

```bash
docker compose -f infrastructure/docker-compose.processor.yml up --build -d
```

Para invocar a função Spring Boot localmente:

```bash
curl -s -X POST "http://localhost:9001/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "orderId": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "customerId": "8b9d7b5e-9d2a-4b4f-8c5a-8b3d6f5d1a11",
    "items": [
      {
        "productId": "93b6c5c8-0f9a-4c2a-8c4c-6f0f3d6a9c2b",
        "productName": "Mechanical Keyboard",
        "quantity": 2,
        "unitPrice": 199.90
      }
    ],
    "shippingAddress": {
      "zipCode": "37200-000",
      "state": "MG",
      "city": "Lavras"
    },
    "totalAmount": 399.80
  }'
```

As funções aceitam dois formatos de entrada com o mesmo contrato de negócio: o JSON cru usado no RIE/local e o envelope HTTP v2 enviado pela Function URL em AWS. Em Function URL, o k6 deve enviar no corpo HTTP o mesmo JSON de `ProcessingRequest` usado localmente.

Para subir também a variante Quarkus JVM, habilite o profile `quarkus`:

```bash
docker compose -f infrastructure/docker-compose.processor.yml --profile quarkus up --build -d
```

Para subir a variante Quarkus Native, habilite o profile `quarkus-native` depois de gerar o pacote nativo:

```bash
docker compose -f infrastructure/docker-compose.processor.yml --profile quarkus-native up --build -d
```

Para invocar a função Quarkus localmente, use a mesma carga na porta `9002`:

```bash
curl -s -X POST "http://localhost:9002/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "orderId": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "customerId": "8b9d7b5e-9d2a-4b4f-8c5a-8b3d6f5d1a11",
    "items": [
      {
        "productId": "93b6c5c8-0f9a-4c2a-8c4c-6f0f3d6a9c2b",
        "productName": "Mechanical Keyboard",
        "quantity": 2,
        "unitPrice": 199.90
      }
    ],
    "shippingAddress": {
      "zipCode": "37200-000",
      "state": "MG",
      "city": "Lavras"
    },
    "totalAmount": 399.80
  }'
```

Para invocar a variante Quarkus Native localmente, use a mesma carga na porta `9003`.

Para validar equivalência direta entre Spring Boot, Quarkus JVM e Quarkus Native com payloads fixos, use a suíte Python em `analysis/`:

```bash
source .venv/bin/activate
python -m pip install -r analysis/requirements.txt
python -m unittest analysis.test_order_processor_equivalence -v
```

Essa suíte builda os módulos, gera o pacote nativo Quarkus, sobe DynamoDB Local e as três Lambdas, executa payloads MG, SP, RS, BA, AM, múltiplos itens, sem items e `quantity = 0`, compara `fiscalNumber`, `shippingCost`, `taxAmount`, `finalAmount`, `estimatedDeliveryDays` e o número de reservas, e remove os containers ao final. Por padrão ela reutiliza as imagens Docker locais; para forçar rebuild das imagens na ordem correta JVM antes de Native, execute com `ORDER_PROCESSOR_EQUIVALENCE_BUILD_IMAGES=true` quando houver acesso às imagens base necessárias.

Para encerrar e remover o volume local do DynamoDB:

```bash
docker compose -f infrastructure/docker-compose.processor.yml down -v
```

## Reprodutibilidade

Os números do texto final vêm de `analysis/reducao/` (ver "Números do texto", no início deste
README). Os CSVs abaixo, de `analysis/fase5/` e de outras pastas, são de versões anteriores do
texto, que usavam outra análise (correção de Holm e testes globais). Alguns ainda servem de fonte
indireta: o agregado de L2 e L3 e a memória do L1. Eles são gerados pelos scripts abaixo, a partir
dos dados versionados em `analysis/fargate/` e `analysis/lambda/`. Requisitos:
`pip install pandas numpy scipy boto3` (boto3 só para os scripts que consultam a AWS;
`analysis/requirements.txt` hoje lista apenas boto3).

| CSV | Script que gera | Cenário | Entradas | Reprodutível só com o repositório? |
|---|---|---|---|---|
| `analysis/fase5/fase5_estatistica_descritiva_novo.csv` | `analysis/fase5_analise_estatistica.py` (grava como `fase5_estatistica_descritiva.csv`; o `_novo` é cópia byte a byte) | F1, F2, F3, F2-S (Fargate), L1, L2, L3 (Lambda) | `analysis/fargate/fase3/`, `fase3b/`, `analysis/lambda/fase4/`, `analysis/lambda/l1/l1_init_durations.json` | Não: L2/L3 r1–r3 usam os `*-raw.json` (ver `DADOS_GRANDES.md`) |
| `analysis/fase5/fase5_testes_significancia.csv` | `analysis/fase5_analise_estatistica.py` | Comparações par a par, todos os cenários, com correção de Holm | idem | Não (idem) |
| `analysis/fase5/fase5_teste_global.csv` | `analysis/fase5_analise_estatistica.py` | Teste global das três versões, por cenário | idem | Não (idem) |
| `analysis/fase5/fase5_f1_corrigido_estatistica.csv` | `analysis/fase5_f1_corrigido.py` | F1 re-executado a 48 iter/s | `analysis/fargate/fase3-f1-rerun/` | Sim |
| `analysis/fase5/fase5_f1_corrigido_significancia.csv` | `analysis/fase5_f1_corrigido.py` | F1 re-executado | idem | Sim |
| `analysis/fase5/fase5_f1_corrigido_teste_global.csv` | `analysis/fase5_f1_corrigido.py` | F1 re-executado | idem | Sim |
| `analysis/fase5/fase5_f2s_recursos.csv` | `analysis/fase5_recursos_f2s.py` | F2-S: CPU e memória do contêiner no hold | CloudWatch (métricas ECS, period=300) + CloudTrail RunTask, `analysis/fase5/runtasks_july.json` | Não: consulta a conta AWS; métricas de 5 min têm retenção de 63 dias |
| `analysis/fase5/fase5_l1_memoria_novo.csv` | `analysis/fase5_analise_estatistica.py` (grava como `fase5_l1_memoria.csv`; o `_novo` é cópia byte a byte) | L1: memória máxima por invocação | CloudWatch Logs, linhas `REPORT` de `/aws/lambda/order-processor-*` | Não: consulta a conta AWS |
| `analysis/lambda/l1/l1_duration_postinit.csv` | `analysis/lambda/l1/l1_duration_postinit.py` | L1: duração pós-init | CloudWatch Logs (janelas de 02–03/07/2026) | Não: consulta a conta AWS |
| `analysis/exploratorio_build/build_runs.csv` | `analysis/exploratorio_build/run_series.sh` → `run_one.py` (resumos: `analyze.py`) | Exploratório: tempo e memória de build das três versões | Builds locais (Gradle + `native-image`) | Sim, re-executando os builds (o resultado depende da máquina) |

Ordem sugerida:

```bash
python analysis/fase5_analise_estatistica.py   # precisa dos *-raw.json de L2/L3 e de credenciais AWS para L1
python analysis/fase5_f1_corrigido.py
python analysis/fase5_recursos_f2s.py          # credenciais AWS
python analysis/lambda/l1/l1_duration_postinit.py  # credenciais AWS
bash   analysis/exploratorio_build/run_series.sh measured && python analysis/exploratorio_build/analyze.py
```

Os scripts de carga do k6 estão em `benchmark/scenarios/` e `benchmark/lib/`; a execução no
Fargate e no Lambda está em `benchmark/run/`; a infraestrutura (CloudFormation, task definition
e configuração das funções Lambda) está em `infrastructure/aws/`.
