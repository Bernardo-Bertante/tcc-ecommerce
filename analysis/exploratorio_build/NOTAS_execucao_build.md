# Diário — teste exploratório de *build* (SB × Quarkus JVM × Quarkus Native)

Exploratório, fora do desenho oficial. Horários em BRT (-03:00).

## 04/10/2026 — Fase A (somente leitura)

- 10:31 Repositório original: `git rev-parse HEAD` = `3772b1677dc315814296220c838f6c0fc4824174`, branch `main`.
  `git status --short`: 36 linhas, todas `??` (não rastreados: exploratórios em `analysis/`, resultados em
  `benchmark/`, `.bak` em `infrastructure/aws/`, `scripts/warmup_curve/`). Nenhum arquivo rastreado modificado.
- Máquina: Linux 6.17.6-lux-amd64 (Lux 2 "Bellatrix"), **x86_64**, Intel i7-13620H (16 threads), 15 GiB RAM +
  5 GiB swap (swappiness 60), NVMe com 197 GB livres. Na tomada (`ADP0/online=1`), `platform_profile=balanced`,
  governor `powersave` (intel_pstate). Uptime 22 h, loadavg ~2,8 em repouso com Firefox, VS Code e 3 language
  servers Java abertos; ~10 GiB usados, 4,6 GiB disponíveis no momento.
- Toolchain: OpenJDK 21.0.7 (Debian) como `JAVA_HOME`; Gradle via *wrapper* (8.14.4-bin nos módulos Spring,
  9.3.1-all nos Quarkus), ambos já em `~/.gradle/wrapper/dists`. Não há Maven nem `native-image` local.
  `/usr/bin/time` **não está instalado** → CPU de usuário/sistema será medida por `getrusage(RUSAGE_CHILDREN)`
  em um *runner* Python (equivalente, só para processos filhos; não enxerga contêineres).
- Docker: o contexto ativo é `desktop-linux` (Docker Desktop, VM 6 CPU/6 GiB), mas o Desktop **não está rodando**.
  O Docker Engine nativo (`/var/run/docker.sock`, 29.8.2, 16 CPU, 15,3 GiB, cgroup v2) está ativo e é onde estão
  as imagens oficiais (`order-service-springboot:20260616-160138`, `…quarkus-jvm/native:20260616-160138` com
  tag de ECR). Plano: usar `DOCKER_HOST=unix:///var/run/docker.sock` só no ambiente do teste (sem trocar contexto).
  `~/.testcontainers.properties` aponta para o socket do Desktop → sobrescrever por variável de ambiente
  (`TESTCONTAINERS_DOCKER_CLIENT_STRATEGY`/`DOCKER_HOST`) só no processo do teste, sem editar o arquivo.
- Builder nativo: o binário oficial mais recente (`order-processor/quarkus/build/quarkus-artifact.properties`,
  17/08/2026) foi gerado com **Mandrel 25.0.4.0-Final (JDK 25)** via `container-build`. A imagem do builder
  **não está** baixada localmente hoje, nem `ubi9/openjdk-21-runtime:1.24`, `ubi9/ubi-minimal:9.7` ou
  `postgres:16-alpine` (Docker Hub). Precisam ser baixadas antes da série (fora da medição).
- `quarkus.package.type=native` (flag do *script* oficial) ainda é aceito no Quarkus 3.35.2:
  `io/quarkus/deployment/configuration/ConfigCompatibility.class` o mapeia para `quarkus.native.enabled`.
- Sem `~/.gradle/gradle.properties`; nenhum `org.gradle.caching` nos módulos → sem *build cache*, `clean` força
  recompilação real. `~/.gradle/caches` = 477 MB.
- Base a priori encontrada (carimbos de tempo do *build* oficial do Order Processor, 17/08/2026): Spring Boot
  terminou 16:21:46; passo Quarkus JVM ~16:21:46→16:22:06 (~20 s); passo nativo 16:22:06→16:23:41 (~95 s), com os
  **testes rodando de novo dentro do passo nativo** (XML de teste regravados às 16:22:20). Não há base para o
  Order Service (o `build/` atual está parcialmente limpo).
- Evidência de manutenção salva em `evidencia_manutencao_native.md`.

## 04/10/2026 — Aprovação e Fase B

- Decisões do autor (AskUserQuestion): **camadas 1 e 2**; **5 repetições medidas** + 1 aquecimento; **sem cache
  frio**; Native medido como `./gradlew clean build` + flags nativas do *script* oficial, sozinho (não encadeado
  após o JVM). Estimativa aprovada só da série: C1 ~42 min + C2 ~27 min = **~69 min** → *guard* em ~104 min
  (1,5×). Total com preparo ~1h30 (1h10–2h).
- Worktree: `git worktree add --detach ~/exp-build-work/repo HEAD` (3772b16, `git status` limpo).
- Pulls (fora da medição, `pulls.log`): `quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-25` 49,1 s
  (1,93 GB, ID `ddfb64ca6f42`); `ubi9/openjdk-21-runtime:1.24` 13,5 s; `ubi9/ubi-minimal:9.7` 12,0 s.
  Builder padrão do Quarkus 3.35.2 (`platform.quarkus.native.builder-image=mandrel` →
  `ContainerImages`: `ubi9-quarkus-mandrel-builder-image:jdk-25`). A tag `jdk-25` é flutuante: a versão exata
  do Mandrel usada aqui sai do log de cada build (pode diferir dos 25.0.4 do artefato oficial de 17/08).
- **Problema de ambiente:** Docker Hub inacessível nesta rede (TLS interceptado: certificado `*.safe-e.com` em
  `registry-1.docker.io`). `postgres:16-alpine` e `testcontainers/ryuk:0.12.0` falham no pull. Maven Central,
  plugins.gradle.org, services.gradle.org, quay.io, registry.access.redhat.com e public.ecr.aws funcionam.
  **Contorno (não altera o projeto):** (1) `docker tag public.ecr.aws/docker/library/postgres:16-alpine
  postgres:16-alpine` (espelho oficial já presente, ID `cf78e76683b9`) — tag criada por mim, a remover no fim;
  (2) `TESTCONTAINERS_RYUK_DISABLED=true` no ambiente do teste (o Ryuk só faz limpeza de contêineres órfãos;
  custo de partida ~1–2 s por JVM de teste deixa de existir → leve viés a favor das versões com Testcontainers,
  OS-QJ, OS-QN, OP-QJ, OP-QN).
- Erro meu (~10:35): ao inspecionar o erro de pull, imprimi `~/.docker/config.json` inteiro no terminal da sessão,
  que contém tokens de ECR (provavelmente expirados). Ficou só no contexto local; nada foi enviado a lugar algum.
- Ambiente do processo de teste: `DOCKER_HOST=unix:///var/run/docker.sock`,
  `TESTCONTAINERS_DOCKER_CLIENT_STRATEGY=…EnvironmentAndSystemPropertyClientProviderStrategy`,
  `TESTCONTAINERS_RYUK_DISABLED=true`. Gradle sempre com `--no-daemon --profile --console=plain`
  (`--profile` só registra tempos por tarefa; desvio mínimo do comando oficial).
- Medição (`run_one.py`): CPU de usuário/sistema por `getrusage(RUSAGE_CHILDREN)` (inclui o daemon de uso único
  do Gradle e as JVMs de teste; **não** inclui contêineres: native-image e Testcontainers rodam sob o dockerd);
  amostrador 1 Hz: memória do sistema (MemTotal − MemAvailable), swap, CPU do sistema (`/proc/stat`), RSS da
  árvore de processos do runner, `memory.current`/`memory.peak`/`cpu.stat` dos cgroups `docker-*.scope`.
  Linha de base = últimos 20 s da pausa de 30 s antes de cada build. "CPU em excesso" = CPU-s do sistema na
  janela − taxa da linha de base × duração.
- 10:37 Teste de fumaça `os-sb_smoke` (pausa 15 s): rc=0, 10,7 s (Gradle 6,4 s, imagem 4,3 s), compileJava
  executado de fato (não UP-TO-DATE); 29 amostras. MemAvailable antes = 10.078 MB (o autor fechou aplicativos).
- 10:38:52 Início do aquecimento (`run_series.sh warmup`, rodada k=0: os-sb, os-qj, os-qn, op-sb, op-qj, op-qn).
- 10:47:44 Fim do aquecimento: 6/6 rc=0. Parede total por versão (s): os-sb 7,2 · os-qj 38,7 · os-qn 181,4
  (native-image 122 s) · op-sb 9,0 · op-qj 19,1 · op-qn 86,9 (native-image 60 s). Nenhum download nos logs
  (cache já estava quente). Testes rodaram como no oficial (os-qj `:test` 11,2 s com Postgres via Testcontainers;
  os-qn também roda `:test` antes do native-image).
- Builder efetivo: **Mandrel 25.0.4.1-Final** (Java 25.0.4.1+1-LTS) — o artefato oficial de 17/08 usou
  25.0.4.0-Final (tag `jdk-25` flutuante). Diferença de *patch*.
- **Correção (10:48):** o native-image imprime números com vírgula decimal (locale pt_BR herdado:
  `Peak RSS: 4,83GB | CPU load: 12,30`, `in 2m 2s`). O regex de `run_one.py` só aceitava ponto → o aquecimento
  gravou `native_peak_rss_gb`/`native_cpu_load` vazios no CSV (o tempo foi lido certo). Regex corrigido antes da
  série medida; `analyze.py` relê esses três campos direto dos logs.
- **Recálculo (guard):** rodada = 342 s de builds + 6 × ~33 s de pausa/overhead ≈ 8,9 min (aquecimento real 8 min
  52 s). Série = aquecimento + 5 × 8,9 ≈ 54 min, contra 69 min aprovados (0,78×) → guard não dispara; segue.
- 10:48:04 Início da série medida (`run_series.sh measured`, rodadas k=1..5, rotação cíclica).
- 11:29:19 Fim: **30/30 rc=0**, nenhuma nova tentativa. Duração 41 min (estimativa recalculada 45; aprovada 69).
  Swap cresceu só nos *builds* OS-QN (+512, +47, +40, +6, +1 MB nas medidas). Taxa de CPU em repouso
  0,30–0,42 núcleo.
- 11:30 `image_layers.txt`: `docker history` das imagens r1 e das oficiais 20260616-160138; camadas da
  aplicação idênticas em tamanho. Conferido: nenhum contêiner nem volume criado pelo teste ficou para trás
  (os 3 contêineres parados e os 4 volumes anônimos existentes são de 13–20/09).
- 11:31 Limpeza: copiados `run_series.sh` e os logs da série para esta pasta (`serie/`); `docker rmi` das 19
  imagens `exp-build/*` (lista em `serie/imagens_removidas.txt`) e da tag `postgres:16-alpine` criada por mim;
  `git worktree remove --force ~/exp-build-work/repo` + `git worktree prune`; `rm -rf ~/exp-build-work`.
  Imagens oficiais conferidas com `docker images` (`order-service-springboot:20260616-160138`,
  `…quarkus-jvm/native:20260616-160138`, `gcf3-*:official`): intactas. Repositório: mesmo HEAD, nenhum
  arquivo rastreado modificado; só a pasta nova `analysis/exploratorio_build/` (não rastreada).
- **Deixado na máquina (não tem prefixo `exp-build-`, decisão do autor):** imagens baixadas para o teste
  `quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-25` (1,93 GB), `ubi9/openjdk-21-runtime:1.24`,
  `ubi9/ubi-minimal:9.7`; e o cache do BuildKit (3,86 GB no total, 1,41 GB recuperável após a remoção das
  imagens). Não é possível separar a parte do teste sem `docker builder prune` global (proibido).
- 11:35 Análise (`analyze.py`) e relatório `RESULTADOS_BUILD.md`. Correção no mesmo dia, antes da entrega:
  a primeira versão do relatório dizia "~84% do tempo de parede" para o `quarkusAppPartsBuild` do OS-QN; o
  correto é 84% do tempo de Gradle (75% do total com imagem). Também troquei "~6 a 9×" por "5,6 a 9,4×" na
  comparação com 15–25 min.
