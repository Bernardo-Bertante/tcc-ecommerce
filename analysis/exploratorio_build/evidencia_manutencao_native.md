# Evidência de manutenção do *build* nativo (P4), levantada no repositório

Exploratório, 04/10/2026. **Não é dado oficial do TCC.** Levantamento somente leitura, sem rodar nada.
Repositório no *commit* `3772b1677dc315814296220c838f6c0fc4824174` (branch `main`).

> **Ressalva:** é evidência anedótica de **um único projeto**, escrito por uma pessoa e com histórico git
> condensado em poucos *commits* grandes. Não serve para generalizar o custo de manutenção do Native Image.

## 1. Arquivos e trechos específicos do *build* nativo

"Linhas não vazias" = `grep -c .`; "linhas" = `wc -l`.

### Order Service (`order-service/quarkus`, Fargate)

| Item | Tipo | Linhas (não vazias) | Exclusivo do Native? | Equivalente JVM |
|---|---|---|---|---|
| `Dockerfile.native` | imagem (base `ubi9/ubi-minimal:9.7`, copia `build/*-runner`) | 13 (9) | sim | `Dockerfile.jvm`, 15 linhas: é substituição, não acréscimo |
| `src/main/java/.../exception/ProblemResponse.java` | `@RegisterForReflection` (anotação + import) | 2 | sim (no JVM a anotação é inócua) | nenhum |
| `scripts/smoke-native-container.sh` | *smoke test* do contêiner nativo | 154 (129) | sim | nenhum (o JVM é validado só por `./gradlew clean test`) |
| `.github/workflows/order-service-quarkus-native.yml` | CI do nativo (`quarkusIntTest` nativo + imagem + *smoke*), `timeout-minutes: 45` | 55 | quase todo (passo 1 valida o JVM) | nenhum *workflow* para o Spring Boot nem para o JVM isolado |
| `infrastructure/aws/scripts/prepare-order-service-images.sh` l.13, 34–36, 66–75, 85, 91, 98 | flags e passo do *build* nativo (`-Dquarkus.package.type=native`, `container-build=true`, `native-image-xmx=6g`) | ~15 | sim | JVM: 1 linha (`./gradlew clean build`) |
| `README.md` (raiz) l.24 e `order-service/quarkus/README.md` (seções "Creating a native executable", "Runtime validation") | documentação de como gerar e validar o nativo | ~20 | sim | — |
| `infrastructure/docker-compose.{test,benchmark}.yml` | serviço `order-service-quarkus-native` | ~5 cada | sim | serviço JVM equivalente |
| `build.gradle` | **nenhum** perfil `native`; o nativo é ativado só por propriedade de linha de comando | 0 | — | — |
| `application.properties` | **nenhuma** propriedade `quarkus.native.*` | 0 | — | — |
| `META-INF/native-image/`, `reflect-config.json`, `resource-config.json` | **não existem** | 0 | — | — |

### Order Processor (`order-processor/quarkus`, Lambda; mesmo módulo gera JVM e Native)

| Item | Tipo | Linhas (não vazias) | Exclusivo do Native? | Equivalente JVM |
|---|---|---|---|---|
| `Dockerfile.native` | imagem local (multi-estágio: `busybox` + `lambda/provided:al2023`, extrai `bootstrap`) | 13 (8) | sim | `Dockerfile.jvm`, 8 linhas. **Obs.:** o caminho oficial na AWS é ZIP (`PackageType: Zip` em `order-processor-stack.yaml`); os Dockerfiles servem ao teste local |
| `src/main/java/.../config/NativeReflectionConfig.java` | classe só para `@RegisterForReflection(targets = {Address, FunctionError, ProcessingItem, ProcessingRequest})` | 20 (16) | sim | nenhum |
| `src/main/resources/application.properties` l.4 | `quarkus.native.additional-build-args=--initialize-at-run-time=...DynamoDbRetryPolicy,--initialize-at-run-time=...FullJitterBackoffStrategy` | 1 (2 classes do AWS SDK forçadas para inicialização em *runtime*) | sim | nenhum |
| `infrastructure/aws/scripts/prepare-order-processor-artifacts.sh` l.25–34 | passo nativo + cópias para contornar o fato de JVM e Native gerarem o **mesmo** `build/function.zip` | ~9 | sim | JVM: 3 linhas |
| `README.md` (raiz) l.151–161, 201 | documentação do passo nativo e do contorno do `function.zip` compartilhado | ~12 | sim | — |
| `infrastructure/docker-compose.processor.yml` l.69–76 | serviço `order-processor-quarkus-native` (perfil `quarkus-native`) | ~8 | sim | serviço JVM equivalente |
| `build.gradle` (exclusão de `apache-client`/`netty-nio-client`, `url-connection-client`, `aws-crt`) | escolha de cliente HTTP do SDK | 5 | **não** — vale para JVM e Native (decisão registrada no guia 08, l.556: mesma configuração nas duas versões Quarkus, seguindo a documentação do Quarkus). Não contado como específico do Native | — |

### Totais (só itens marcados "sim")

- **Código/configuração dentro dos módulos** (o que o desenvolvedor mantém junto da aplicação):
  Order Service 15 linhas (`Dockerfile.native` 13 + 2 de anotação); Order Processor 34 linhas
  (`Dockerfile.native` 13 + `NativeReflectionConfig` 20 + 1 propriedade). Nenhum arquivo de configuração de
  reflexão em JSON; nenhum perfil Gradle.
- **Infraestrutura de *build*/validação em volta** (*scripts*, CI, *compose*, README): ~270 linhas no Order Service
  (dominadas pelo *smoke* de 154 linhas e pelo CI de 55), ~30 no Order Processor.
- Spring Boot: **zero** artefatos equivalentes (não há caminho nativo para ele no projeto).

## 2. Histórico git

O repositório tem **21 *commits*** no total. Busca por assunto (`git log --all -i -E --grep='native|reflection|graal|mandrel|provided.al2023|bootstrap|nativ'`):
**0 *commits***.

Busca por arquivos tocados (`Dockerfile.native`, `NativeReflectionConfig`, `ProblemResponse.java`,
`application.properties` e `build.gradle` do processor, `README` do quarkus):

| Hash | Data | Assunto | O que tem de nativo |
|---|---|---|---|
| `067e5d7` | 2026-04-30 | chore: set initial project structure | `Dockerfile.native` do Order Service |
| `330e13f` | 2026-05-11 | feat: Add integration tests and exception handling for order service | `ProblemResponse` com `@RegisterForReflection`, CI nativo, *smoke* |
| `c4d5b00` | 2026-05-24 | Prepare Order Service and Order Processor for AWS smoke tests | `Dockerfile.native` do processor, `NativeReflectionConfig`, `--initialize-at-run-time` |
| `0097313` | 2026-09-01 | chore: para de versionar order-processor/quarkus/bin (saida de build) | só remoção de saída de build |

**Leitura:** o histórico é condensado (o `c4d5b00` adiciona dezenas de arquivos de uma vez), então **não registra
iterações de tentativa e erro** do *build* nativo. Ele não permite medir esforço histórico: não se pode afirmar nem
que custou pouco nem que custou muito. O que existe é o estado final (seção 1).

## 3. Limitações registradas no repositório e nas notas

- `order-service/quarkus/README.md` (seção "Runtime validation", última frase antes de "Related Guides"):
  *"the explicit `-Dquarkus.native.native-image-xmx=6g` keeps the Mandrel build stable during native image
  generation"*. É a única menção a requisito de memória do *build* nativo. Não diz o que acontecia sem a flag.
- `README.md` (raiz) l.161 e l.201: o Quarkus reutiliza o nome `build/function.zip` para JVM e Native; é preciso
  copiar o ZIP JVM antes do *build* nativo. É um custo de processo, não de tempo.
- Guias em `~/Downloads` (versões mais recentes: `03-methodology_2_`, `07-decisions_1_`, `08-known-problems_27_`):
  **nenhuma** menção a tempo, memória ou biblioteca incompatível no *build* nativo
  (busca por `native-image|mandrel|container-build|xmx|build nativo|tempo de build`).
- `11-plano-redacao-tcc_35_.md` l.126: *"Cortado §3.7.4 'Projeção de custo e build nativo' (Equação $C_{build}$
  incluída — nunca medido)."* e `12-estrutura-final-tcc_29_.md` l.108 e l.412: a seção foi cortada.
- `08-known-problems_27_.md` l.526 e `10-next-steps_4_.md` l.3: pendência "varrer a Introdução em busca de
  '15 a 25 minutos de build' sem fonte e do objetivo (d)".

## 4. A frase dos "15 a 25 minutos"

- `~/Downloads/introducao(6).tex` l.21 (e versões anteriores, `introducao.tex` a `introducao(5).tex`):
  *"…custos operacionais adicionais — como o tempo de \textit{build} de 15 a 25 minutos por artefato — que podem
  inviabilizar sua adoção em determinados contextos."* Refere-se ao *build* **nativo (compilação AOT)**,
  "por artefato", sem fonte.
- **A versão mais recente, `introducao(7).tex` l.21, já não tem a faixa:** diz *"o tempo de \textit{build},
  consideravelmente maior que o de uma compilação JVM convencional \cite{quarkusnativebuild2026}"*.
  O relatório compara a faixa antiga com o medido só como relato; nada foi editado.
