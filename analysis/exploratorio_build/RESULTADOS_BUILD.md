# Custo de *build*: Spring Boot × Quarkus JVM × Quarkus Native

> **Investigação exploratória, fora do desenho experimental oficial do TCC. Não é dado oficial.**
> Uma máquina local, n = 5 por versão, estatística só descritiva.
> *Commit* medido: `3772b1677dc315814296220c838f6c0fc4824174` (cópia limpa via `git worktree`, sem alterações).
> Data: 04/10/2026, série medida das 10:48:04 às 11:29:19 (BRT).

Arquivos brutos (todos nesta pasta):

| Arquivo | Conteúdo |
|---|---|
| `build_runs.csv` | Uma linha por fase (`gradle`, `image`, `total`) de cada execução: fumaça, aquecimento e medidas (37 execuções, 93 linhas) |
| `samples/<run>.csv` | Amostrador a 1 Hz: memória, swap, CPU do sistema, RSS da árvore de processos, memória e CPU dos contêineres |
| `logs/<run>.log` | Saída completa do Gradle, do `native-image` e do `docker build` |
| `profiles/<run>.html` | `gradle --profile`: tempo por tarefa |
| `resumo_por_versao.csv`, `razoes_mediana.csv`, `tarefas_gradle.csv`, `analise.txt` | Saídas do `analyze.py` |
| `image_layers.txt` | `docker history` das imagens medidas e das oficiais (20260616-160138) |
| `serie/` | Log da série, dos *pulls* e lista das imagens removidas |
| `run_one.py`, `run_series.sh`, `analyze.py` | Código da medição e da análise |
| `evidencia_manutencao_native.md` | P4 |
| `NOTAS_execucao_build.md` | Diário com os comandos, horários e correções |

## 1. Máquina e ambiente

- Linux 6.17.6 (Lux 2), **x86_64** (o mesmo alvo da AWS; sem emulação).
- Intel i7-13620H com 16 *threads*, 15,3 GiB de RAM e 5 GiB de swap, NVMe.
- Na tomada, perfil de energia `balanced`, *governor* `powersave` (intel_pstate).
- Na série, o Firefox e outros aplicativos estavam fechados. O VS Code continuou aberto (a sessão roda nele). A CPU em repouso ficou em 0,30–0,42 núcleo (mediana 0,35), medida na pausa de 30 s antes de cada *build*.
- OpenJDK 21.0.7 (Debian). Gradle *wrapper*: 8.14.4 nos módulos Spring Boot, 9.3.1 nos Quarkus. Quarkus 3.35.2, Spring Boot 3.5.14.
- Docker Engine 29.8.2 nativo, cgroup v2. O Docker Desktop estava parado e não foi usado.
- Builder nativo: `quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-25`, que resolveu para **Mandrel 25.0.4.1-Final**. O artefato oficial de 17/08 usou 25.0.4.0; a diferença é só de *patch*. O `native-image` rodou com `-Xmx6g` e 16 *threads*.
- Cache do Gradle quente: nenhum download em nenhum *log*. Imagens-base baixadas antes da série.

## 2. O que foi medido

Foram usados os comandos dos *scripts* oficiais (`infrastructure/aws/scripts/prepare-order-service-images.sh` e `prepare-order-processor-artifacts.sh`), sempre com `clean`, `--no-daemon`, `--profile` e `--console=plain`. As imagens foram feitas com `docker build --no-cache`.

| Versão | Comando Gradle | Testes | Artefato | Imagem |
|---|---|---|---|---|
| OS-SB | `clean bootJar` | não roda testes (como no oficial) | JAR | `Dockerfile` |
| OS-QJ | `clean build` | sim (unitários + `OrderResourceIT` com Postgres via Testcontainers) | `build/quarkus-app/` | `Dockerfile.jvm` |
| OS-QN | `clean build -Dquarkus.package.type=native -Dquarkus.native.container-build=true -Dquarkus.native.native-image-xmx=6g` | sim (os mesmos, na JVM, antes do `native-image`) | `*-runner` | `Dockerfile.native` |
| OP-SB | `clean build` (inclui `lambdaZip`) | sim (unitários) | ZIP | — (o oficial é ZIP) |
| OP-QJ | `clean build` | sim (inclui DynamoDB Local em contêiner) | `function.zip` | — |
| OP-QN | `clean build` + as flags nativas | sim | `function.zip` com `bootstrap` | — |

Alguns pontos do protocolo:
- **Native:** foi medido sozinho, com `clean` (decisão do autor). O *script* oficial roda o Native logo depois do JVM, sem `clean`; essa sequência **não** foi medida.
- **Repetições:** 1 aquecimento descartado e 5 medidas por versão.
- **Ordem:** rotação cíclica das 6 versões. Em cada rodada a ordem é deslocada de uma posição, de modo que cada versão ocupa cada posição uma vez. Tudo sequencial, com 30 s de pausa antes de cada *build*.
- **Resultado:** 30/30 execuções medidas com código 0. Nenhuma falha e nenhuma nova tentativa.

## 3. Tabela principal (execuções medidas, n = 5 por versão)

Os tempos são de parede, do início do Gradle ao fim da imagem (ou do ZIP). As colunas de recursos:
- **CPU (s):** CPU-s do sistema inteiro durante o *build*, menos a taxa de repouso. Inclui contêineres.
- **CPU host:** `user+sys` dos processos filhos (Gradle, JVMs de teste). Não enxerga o `native-image`, que roda em contêiner.
- **CPU média:** percentual das 16 *threads*.
- **Mem. pico:** pico de memória do sistema (MemTotal − MemAvailable) acima da linha de base. Mediana [máx].

### Camada 1: Order Service (Fargate)

| Versão | Mediana | Mín–máx | Média ± DP | CV | CPU (s) | CPU host (s) | CPU média | Mem. pico acima da base | Artefato | Imagem (camada da app) |
|---|---|---|---|---|---|---|---|---|---|---|
| Spring Boot | **9,0 s** | 7,4–10,5 | 9,2 ± 1,2 | 13,4% | 27 | 24 | 18% | 667 MB [736] | JAR 33,4 MB | 608,8 MB (33,4 MB) |
| Quarkus JVM | **29,9 s** | 28,4–38,0 | 31,4 ± 3,8 | 12,1% | 108 | 104 | 24% | 2.143 MB [2.270] | `quarkus-app/` 45,1 MB | 630,8 MB (≈45,5 MB) |
| Quarkus Native | **159,9 s (2 min 40 s)** | 151,4–162,8 | 158,5 ± 4,3 | 2,7% | 1.563 | 110 | 63% | **6.201 MB [6.452]** | binário 94,2 MB | 278,4 MB (94,2 MB) |

### Camada 2: Order Processor (Lambda, ZIP)

| Versão | Mediana | Mín–máx | Média ± DP | CV | CPU (s) | CPU host (s) | CPU média | Mem. pico acima da base | ZIP |
|---|---|---|---|---|---|---|---|---|---|
| Spring Boot | **6,9 s** | 6,9–7,0 | 6,9 ± 0,1 | 1,0% | 31 | 32 | 26% | 798 MB [845] | 29,3 MB |
| Quarkus JVM | **16,8 s** | 16,3–21,5 | 18,3 ± 2,5 | 13,4% | 68 | 63 | 26% | 1.928 MB [1.957] | 30,7 MB |
| Quarkus Native | **80,8 s (1 min 21 s)** | 80,1–83,8 | 81,2 ± 1,6 | 1,9% | 815 | 67 | 65% | **4.047 MB [4.129]** | 21,2 MB |

### `native-image` (do *log* do próprio Mandrel)

| Versão | Tempo de geração (mediana [mín–máx]) | *Peak RSS* | *CPU load* (núcleos) | Maior pico de cgroup do contêiner |
|---|---|---|---|---|
| OS-QN | 110 s [109–115] | 4,96 GB [4,91–5,07] | 12,8 | 4.914 MB (máx 5.196) |
| OP-QN | 58,3 s [56,9–60,0] | 2,84 GB [2,81–2,89] | 12,4 | 3.107 MB (máx 3.178) |

### Razões pela mediana (`razoes_mediana.csv`)

| | Tempo total | CPU do sistema | Pico de memória acima da base |
|---|---|---|---|
| OS: Native ÷ Quarkus JVM | **5,3×** | 14,4× | 2,9× |
| OS: Native ÷ Spring Boot | **17,8×** | 58,5× | 9,3× |
| OS: Quarkus JVM ÷ Spring Boot | 3,3× | 4,0× | 3,2× |
| OP: Native ÷ Quarkus JVM | **4,8×** | 12,0× | 2,1× |
| OP: Native ÷ Spring Boot | **11,7×** | 26,6× | 5,1× |
| OP: Quarkus JVM ÷ Spring Boot | 2,4× | 2,2× | 2,4× |

**Cuidado com as razões contra o Spring Boot na camada 1.** O OS-SB oficial (`bootJar`) **não roda testes**, enquanto o OS-QJ e o OS-QN rodam. Só a tarefa `:test` leva ~13–15 s nos dois Quarkus (seção 4). A razão Native ÷ Quarkus JVM compara caminhos que rodam os mesmos testes, e por isso é a mais limpa das três.

## 4. Fases

**Gradle × imagem** (mediana, em s; `build_runs.csv`, fases `gradle` e `image`):

| Versão | Gradle | Imagem (`docker build --no-cache`) |
|---|---|---|
| OS-SB | 5,2 | 3,8 |
| OS-QJ | 25,2 | 7,0 |
| OS-QN | 143,2 | 14,9 |

A imagem do Native é a mais lenta de montar porque o `Dockerfile.native` tem um `RUN chown` sobre a `ubi-minimal`. Mesmo assim, ela é a menor fração do total.

**Dentro do Gradle** (mediana, `tarefas_gradle.csv`):

| Versão | `:test` | `:quarkusAppPartsBuild` (no Native contém o `native-image`) | `:compileJava` | Execução de tarefas, total |
|---|---|---|---|---|
| OS-SB | — | — (`bootJar` 0,28) | 0,86 | 1,2 |
| OS-QJ | 15,2 | 2,3 | 0,94 | 20,7 |
| OS-QN | 13,1 | **120,5** | 0,92 | 138,6 |
| OP-SB | 0,7 | — (`lambdaZip` 0,71) | 0,72 | 2,6 |
| OP-QJ | 7,7 | 1,9 | 0,63 | 12,3 |
| OP-QN | 6,7 | **66,3** | 0,59 | 76,5 |

No Native, a geração do binário (`quarkusAppPartsBuild`) responde por 84% do tempo de Gradle do Order Service (75% do total, que inclui a imagem) e por 82% do total do Order Processor. A compilação Java é igual nas três versões (< 1 s).

## 5. O que vira a faixa "15 a 25 minutos" do texto

- A frase está em `introducao.tex` até `introducao(6).tex`, l.21: *"o tempo de build de 15 a 25 minutos por artefato"*, sem fonte. Ela **já não está** em `introducao(7).tex`, que diz "consideravelmente maior que o de uma compilação JVM convencional \cite{quarkusnativebuild2026}". Nada foi editado.
- **Medido nesta máquina**, da fonte limpa ao artefato implantável, com testes:
  - Native do Order Service: **2 min 31 s a 2 min 43 s** (mediana 2 min 40 s);
  - Native do Order Processor: **1 min 20 s a 1 min 24 s**.
- Só a etapa `native-image` leva 1 min 49 s a 1 min 55 s e 57 s a 60 s, respectivamente.
- **Nesta máquina e neste projeto, a faixa de 15–25 min fica 5,6 a 9,4× acima da mediana medida no Order Service (900 s e 1.500 s ÷ 159,9 s).**
- Esse número absoluto vale para 16 *threads*, 15 GiB e cache quente. Não diz nada sobre um *runner* de CI com 2 a 4 vCPU. O `native-image` usou ~12,5 núcleos em média (*CPU load* do *log*), então ele escala com o número de núcleos, e numa máquina menor o tempo seria maior. Isso **não foi medido**. Para referência, o CI do próprio repositório (`.github/workflows/order-service-quarkus-native.yml`) define `timeout-minutes: 45`, que é um limite configurado e não uma medição.

## 6. Evidência de manutenção (P4, resumo de `evidencia_manutencao_native.md`)

**Ressalva: é um projeto só, de um autor, com histórico git condensado. É evidência anedótica.**

- **Dentro dos módulos**, o Native exige:
  - Order Service: 15 linhas, que são o `Dockerfile.native` e um `@RegisterForReflection` em `ProblemResponse`.
  - Order Processor: 34 linhas, que são o `Dockerfile.native`, a classe `NativeReflectionConfig` com 4 classes registradas para reflexão e 1 propriedade `quarkus.native.additional-build-args` forçando duas classes do AWS SDK para inicialização em *runtime*.
  - Não há perfis Gradle, JSON de reflexão nem `META-INF/native-image`.
- **Em volta dos módulos:** ~270 linhas no Order Service (o *smoke* do contêiner nativo tem 154 linhas e o CI só do Native tem 55) e ~30 no Order Processor (passo nativo e contorno do `function.zip` compartilhado entre JVM e Native).
- **Spring Boot e Quarkus JVM:** nenhum artefato equivalente.
- **Histórico:** 21 *commits* no total e **0** com assunto ligado ao nativo. O código nativo entrou em 3 *commits* grandes (`067e5d7`, `330e13f`, `c4d5b00`). O histórico **não registra tentativas e erros**, então não permite medir quanto esforço o nativo custou.
- **Notas e guias:** a única limitação escrita é o `README` do Quarkus, que diz que `-Dquarkus.native.native-image-xmx=6g` "keeps the Mandrel build stable". A seção "Projeção de custo e build nativo" (§3.7.4) foi cortada por "nunca medido" (`11-plano-redacao-tcc_35_.md` l.126).

## 7. Limitações

- **n = 5 por versão, sem teste de hipótese.** Os CVs ficam entre 1% e 13%. Os Native são os mais estáveis (CV ≤ 2,7%); OS-SB, OS-QJ e OP-QJ variam ~12–13% por causa de execuções isoladas mais lentas (até 38,0 s no OS-QJ e 21,5 s no OP-QJ).
- **Uma máquina de desenvolvimento, não um servidor de CI.** 16 *threads* e NVMe. **Os tempos absolutos não se transpõem** para outro ambiente. As razões entre versões são mais confiáveis, mas mesmo elas dependem do número de núcleos: o `native-image` paraleliza bem (~12,5 núcleos), enquanto o Gradle e os testes usaram 18–26% das 16 *threads*. Com menos núcleos, a razão Native ÷ JVM provavelmente **aumenta**, mas isso não foi medido.
- **Cache quente** (dependências e imagens-base). Não houve execução de cache frio (decisão do autor). O primeiro *pull* do builder Mandrel (1,93 GB) levou 49 s nesta rede (`serie/pulls.log`), o que é um custo único fora da medição.
- **Testes** rodaram como no caminho oficial: o OS-SB não roda testes e os outros cinco rodam. **O Ryuk do Testcontainers foi desligado** e o Postgres dos testes veio de um espelho local, ambos por bloqueio de rede ao Docker Hub (ver NOTAS). Isso deve ter tirado ~1–2 s de cada versão que usa Testcontainers.
- **Native medido sozinho, com `clean`**, e não como no *script* oficial (JVM e depois Native sem `clean`). O custo incremental dessa sequência não foi medido.
- **Memória e swap.**
  - No OS-QN, o sistema chegou a ~11 GB usados de 15,3 GiB (baseline ~4,7–5,6 GB + 5,6–6,5 GB do *build*).
  - O kernel moveu páginas ociosas para o swap só durante os *builds* OS-QN (+381 MB no aquecimento, +512 MB em r1, depois +47, +40, +6 e +1 MB).
  - Não houve falha. O r1 com +512 MB de swap (158,1 s) não destoou da mediana.
  - Em máquinas com 8 GB, o `-Xmx6g` do `native-image` mais o Gradle e o sistema provavelmente não caberiam. Isso **não foi testado**.
- **CPU.** O `getrusage` não enxerga processos em contêiner, por isso há duas colunas. A "CPU (s)" do sistema inclui ruído de fundo (descontado pela taxa de repouso) e qualquer outra atividade da máquina.
- **Possível *throttling* térmico:** não foi monitorado diretamente. Os tempos do Native subiram pouco ao longo da série (OS-QN: 158,1 / 151,4 / 159,9 / 160,4 / 162,8 s), o que é compatível com aquecimento leve, mas não é prova.
- **Artefato nativo não reprodutível byte a byte:** o ZIP do OP-QN variou de 21,177 a 21,221 MB entre execuções.
- **Tamanho da imagem:** inclui a base. A camada da aplicação está entre parênteses na tabela (`image_layers.txt`). Os tamanhos batem com as imagens oficiais de 16/06 (camada da app idêntica: 33,4 / ≈45,5 / 94,2 MB).

## 8. Inconsistências e erros meus (notas datadas)

- **04/10/2026 10:48.** O `native-image` escreve números com vírgula decimal (locale pt_BR), e o *regex* original do `run_one.py` só aceitava ponto. Por isso, nas linhas do aquecimento, `native_peak_rss_gb` e `native_cpu_load` ficaram vazios no `build_runs.csv`. O tempo foi lido certo. O *regex* foi corrigido antes da série medida, e o `analyze.py` relê esses campos dos *logs*.
- **04/10/2026 ~10:35.** Ao investigar o erro de *pull*, imprimi `~/.docker/config.json` no terminal da sessão. O arquivo contém tokens de ECR, provavelmente já expirados. Nada foi enviado para fora da máquina.
- **04/10/2026.** Horários do diário escritos com placeholder ("10:4x") e corrigidos no mesmo dia para os horários reais (10:35, 10:37, 10:38:52).

## 9. Respostas curtas

- **P1 (tempo).**
  - Order Service: Spring Boot 9,0 s, Quarkus JVM 29,9 s, Quarkus Native 159,9 s (medianas). O Native leva 5,3× o JVM e 17,8× o Spring Boot (este sem testes).
  - Order Processor: 6,9 / 16,8 / 80,8 s. O Native leva 4,8× o JVM e 11,7× o Spring Boot.
  - O mais rápido é o Spring Boot nas duas camadas, e o mais lento é o Native nas duas.
- **P2 (recursos).** Confirmado: o Native exige muito mais.
  - Pico de memória acima da base: 6,2 GB no Order Service (`native-image` com *Peak RSS* de 4,96 GB) e 4,0 GB no Order Processor. Os JVM ficaram em 2,1 / 1,9 GB e os Spring Boot em 0,7 / 0,8 GB.
  - CPU: 1.563 CPU-s (≈26 CPU-min) por *build* nativo do Order Service, contra 108 do Quarkus JVM e 27 do Spring Boot. O Native usou em média 63–65% das 16 *threads*; os outros ficaram em 18–26%.
- **P3 (tamanho).** Order Service: JAR 33,4 MB / `quarkus-app` 45,1 MB / binário 94,2 MB. Imagens: 608,8 / 630,8 / 278,4 MB. ZIPs do Order Processor: 29,3 / 30,7 / 21,2 MB. O binário nativo é maior que o JAR, mas a imagem e o ZIP nativos são menores porque não carregam JVM.
- **P4 (manutenção).** O nativo exige 15 linhas (Order Service) e 34 linhas (Order Processor) de código e configuração dentro dos módulos, mais ~300 linhas de *scripts*, CI e documentação em volta. O histórico não permite medir esforço. É evidência de um projeto só.
