# Exploratório: proxy dinâmico/reflexão/AOP explicam o gap de CPU do Spring Boot no Fargate? (20/09/2026)

**Não é resultado formal do TCC.** Investigação fora do desenho experimental, mesmo status de
`exploratorio_cpu_lambda`, `exploratorio_gc_f1` e `exploratorio_c2_lambda`. Nenhum `.tex` ou `.md`
do projeto principal foi alterado.

**Hipótese testada:** o Spring Data R2DBC monta repositórios via proxy dinâmico e reflexão em runtime,
com interceptação de `@Transactional` por chamada, enquanto o Panache resolve isso em build time; se
for verdade, o perfil de CPU do Spring Boot deve mostrar fatia visível em despacho de proxy, reflexão
e interceptadores de AOP que o Quarkus não tem.

**Resposta direta: não.** As três categorias somam **2,6% do gap de CPU**. A hipótese se inverte na
dimensão de proxy: o Quarkus gasta ~2× mais CPU em proxy dinâmico que o Spring Boot. Onde a diferença
de fato aparece está na seção "Onde o gap está".

## Observação prévia sobre a hipótese

A versão Spring Boot **não tem nenhum `@Transactional`** (grep em `order-service/springboot/src/main/java/`:
zero ocorrências). Quem tem interceptação transacional por requisição é o **Quarkus**, via `@WithTransaction`
em `OrderService.java:151/166/199` (interceptador CDI gerado em build). A terceira categoria da hipótese,
portanto, não tinha como aparecer no lado Spring — e foi medida nos dois lados assim mesmo.

Assimetria adicional não prevista na hipótese: o Quarkus usa **Hibernate Reactive + Panache** (ORM completo)
e o Spring usa **Spring Data R2DBC** (mapeador mais fino). Não são camadas do mesmo peso.

## Setup

- Imagens **idênticas às do F1/F2/F3 oficiais** (tag `20260616-160138`), derivadas só para embutir o
  async-profiler 4.5 em `/opt/async-profiler`. Nenhum código recompilado. Em ambas o `java` é PID 1 e o
  entrypoint da UBI aplica as mesmas flags (`UseParallelGC`, `MaxRAMPercentage=80`, etc.).
- Container 8 CPUs dedicadas (`--cpuset-cpus=0-7`) = ergonomia da task Fargate oficial (`TaskCpu=8192`).
  Postgres 16 local (cores 8-11), k6 local (cores 12-15). Pools reativos 20 nos dois lados (config real).
- Carga: `f1_low_load.js`, mix oficial 51/20/15/12/2, **48 iter/s**, rampa 60 s + hold 960 s.
  3 repetições por versão, ordem intercalada (sb, qj, sb, qj, sb, qj — `run_all.sh`).
  53.909 requisições por execução, **0,000% de falhas**.
- Profiling por repetição, duas janelas na mesma execução:
  - **cpu** (`ctimer`, CPU-time por thread), t+120 s por 360 s;
  - **wall** (wall-clock, todas as threads, captura espera), t+520 s por 360 s.
  Saída em `.jfr` (bruto), `.collapsed` (quantificação) e `.html` (flame graph).

### Verificação do profiler antes da carga (tarefa 1)

Cada repetição faz um warm-up de 60 s e, dentro dele, uma coleta de prova de 10 s; o script **aborta**
se vierem menos de 50 amostras. Todas passaram:

| | sb-r1 | sb-r2 | sb-r3 | qj-r1 | qj-r2 | qj-r3 |
|---|---|---|---|---|---|---|
| amostras em 10 s | 420 | 375 | 283 | 117 | 165 | 91 |
| stacks distintos | 338 | 325 | 262 | 114 | 157 | 90 |

### Validação do perfil contra o cgroup

A soma das amostras de `ctimer` (1 amostra = 10 ms de CPU) bate com a CPU medida do contêiner, então as
categorias podem ser lidas em **vCPU absoluto**, não só em percentual:

| | sb-r1 | sb-r2 | sb-r3 | qj-r1 | qj-r2 | qj-r3 |
|---|---|---|---|---|---|---|
| vCPU pelo cgroup (`cpu.stat`) | 0,200 | 0,221 | 0,171 | 0,079 | 0,071 | 0,066 |
| vCPU pelo profiler | 0,198 | 0,197 | 0,161 | 0,080 | 0,067 | 0,063 |

**Média: Spring Boot 0,197 vCPU vs Quarkus JVM 0,072 vCPU = 2,7×** — dentro da faixa de 2,6–3,9× medida
no Fargate oficial. A reprodução local é válida.

## Tarefa 3 — quebra percentual, lado a lado

Atribuição por **self time** (frame folha): cada amostra conta para uma única categoria, então as
categorias particionam 100% da CPU amostrada. Média das 3 repetições; `desvio` = maior desvio de uma
repetição em relação à média (tarefa 2: consistência entre repetições).

| categoria | Spring Boot | desvio | Quarkus JVM | desvio |
|---|---|---|---|---|
| **proxy dinâmico / geração de proxy** | **0,42%** | ±0,18pp | **0,34%** | ±0,13pp |
| **reflexão (`java.lang.reflect`, `MethodHandle`)** | **2,20%** | ±0,33pp | **2,53%** | ±0,47pp |
| **interceptação AOP / `@Transactional`** | **0,08%** | ±0,01pp | **~0,00%** | — |
| **soma das três (hipótese)** | **2,70%** | | **2,87%** | |
| jdk_outro (coleções, String, atomics) | 17,36% | ±1,84pp | 13,22% | ±1,44pp |
| syscall de rede (send/recv/epoll) | 14,95% | ±2,73pp | 23,03% | ±2,00pp |
| plumbing reativo (Reactor / Mutiny) | 13,09% | ±0,37pp | 1,43% | ±0,27pp |
| compilador JIT (C1/C2) | 10,44% | ±2,08pp | 21,55% | ±4,41pp |
| servidor HTTP (Netty / Vert.x) | 9,42% | ±0,42pp | 15,06% | ±0,75pp |
| despacho virtual/interface (itable/vtable stub) | 8,35% | ±0,26pp | 3,62% | ±0,45pp |
| nativo da VM | 6,28% | ±1,13pp | 1,99% | ±0,32pp |
| ORM / mapeador | 4,04% | ±0,49pp | 0,25% | ±0,10pp |
| driver de banco (R2DBC / Vert.x PG) | 4,36% | ±0,20pp | 3,28% | ±0,29pp |
| framework_outro | 2,99% | ±0,53pp | 4,29% | ±0,24pp |
| nativo libc | 1,87% | ±0,18pp | 1,35% | ±0,24pp |
| JSON (Jackson) | 0,92% | ±0,14pp | 2,92% | ±0,60pp |
| lógica de negócio (`com.tcc.orderservice`) | 0,48% | ±0,09pp | 1,49% | ±0,25pp |
| GC | 0,48% | ±0,07pp | 0,37% | ±0,08pp |
| demais (sincronização, VM outras, não classificado) | 2,27% | | 3,26% | |

Consistência entre repetições (tarefa 2): desvio máximo abaixo de 1pp na maioria das categorias; o pior
caso é `compilador JIT` (±4,41pp no Quarkus), que é a categoria naturalmente mais instável. Os flame
graphs das 3 repetições de cada versão são consistentes entre si.

**Atribuição inclusiva** (qualquer frame do stack casa — categorias se sobrepõem, não somam 100%):

| | Spring Boot | Quarkus JVM |
|---|---|---|
| proxy dinâmico | 5,05% | **24,21%** |
| reflexão | 7,68% | 3,97% |
| AOP / transação | 0,10% | 0,21% |

O Quarkus passa por frame de proxy em ~1/4 da sua CPU (é o `_ClientProxy` do CDI, em todo acesso a bean),
contra 5% do Spring Boot. Em vCPU absoluto: **Quarkus 0,0169 vs Spring Boot 0,0087** — o dobro.

## Tarefa 4 — onde o gap está de fato

Gap total a explicar: **0,1153 vCPU** (SB 0,1854 − QJ 0,0701, amostrado).

| categoria | SB (vCPU) | QJ (vCPU) | delta | % do gap |
|---|---|---|---|---|
| plumbing reativo (Reactor vs Mutiny) | 0,02425 | 0,00100 | 0,02325 | **20,2%** |
| jdk_outro (coleções, String, atomics) | 0,03196 | 0,00919 | 0,02278 | **19,7%** |
| despacho virtual/interface | 0,01549 | 0,00251 | 0,01298 | **11,3%** |
| syscall de rede | 0,02805 | 0,01622 | 0,01182 | 10,3% |
| nativo da VM | 0,01153 | 0,00140 | 0,01013 | 8,8% |
| ORM / mapeador | 0,00744 | 0,00018 | 0,00726 | 6,3% |
| servidor HTTP | 0,01741 | 0,01052 | 0,00689 | 6,0% |
| driver de banco | 0,00810 | 0,00230 | 0,00581 | 5,0% |
| compilador JIT | 0,01962 | 0,01524 | 0,00438 | 3,8% |
| nativo libc | 0,00348 | 0,00094 | 0,00254 | 2,2% |
| framework_outro | 0,00548 | 0,00301 | 0,00247 | 2,1% |
| reflexão | 0,00404 | 0,00176 | 0,00228 | 2,0% |
| não classificado | 0,00261 | 0,00109 | 0,00152 | 1,3% |
| GC | 0,00089 | 0,00026 | 0,00063 | 0,5% |
| proxy dinâmico | 0,00076 | 0,00023 | 0,00053 | 0,5% |
| sincronização | 0,00051 | 0,00029 | 0,00022 | 0,2% |
| VM (outras threads) | 0,00108 | 0,00090 | 0,00019 | 0,2% |
| AOP / transação | 0,00015 | 0,00000 | 0,00015 | 0,1% |
| lógica de negócio | 0,00087 | 0,00104 | −0,00017 | −0,1% |
| JSON | 0,00171 | 0,00202 | −0,00031 | −0,3% |
| **HIPÓTESE (proxy + reflexão + AOP)** | **0,00494** | **0,00199** | **0,00295** | **2,6%** |

### Subsistemas específicos (inclusivo, subárvore inteira)

| subsistema | SB (vCPU) | QJ (vCPU) | delta | % do gap |
|---|---|---|---|---|
| Spring Data: renderização de SQL (AST → string) | 0,01754 | 0,00000 | 0,01754 | **15,2%** |
| exceção: `fill_in_stack_trace` | 0,00741 | 0,00000 | 0,00741 | **6,4%** |
| Spring Data: `PropertyPath` + `PropertyReferenceException` | 0,00611 | 0,00000 | 0,00611 | 5,3% |
| Reactor: propagação de `Context` | 0,00619 | 0,00033 | 0,00586 | 5,1% |
| proxy dinâmico (qualquer) | 0,00869 | 0,01685 | **−0,00817** | **−7,1%** |

Três coisas que aparecem **só no Spring Boot** e não têm equivalente no perfil do Quarkus:

1. **Renderização de SQL por requisição** (0,0176 vCPU, 15,2% do gap). O `DelegatingVisitor` de
   `org.springframework.data.relational.core.sql.render` percorre uma AST de SQL e a serializa em string
   a cada chamada. Assinatura no perfil: `java.util.Vector.isEmpty` (0,86% da CPU do SB) e
   `java.util.Stack.peek` (0,37%) — coleções sincronizadas legadas usadas pelo visitor.

2. **Exceção como fluxo de controle dentro do Spring Data** (1,88% da CPU do SB).
   `PropertyReferenceException` é construída e capturada dentro de `PropertyPath.create` a cada
   resolução de property path. Custo real: `java_lang_Throwable::fill_in_stack_trace` (1,40%) +
   `BacktraceBuilder::push` (1,02%). Nota: outros 0,80% de `fill_in_stack_trace` vêm da
   `OrderNotFoundException` da própria aplicação (caminho 404, previsto no mix da carga) — esse
   pedaço não é do framework.

3. **Despacho de interface megamórfico na propagação de `Context` do Reactor**. `itable stub` sozinho é
   **7,72% da CPU do Spring Boot contra 2,55% do Quarkus**; os stacks que mais levam a ele são
   `reactor.core.publisher.InnerOperator.currentContext` recursivo — a cadeia de operadores é percorrida
   por chamada de interface a cada acesso ao contexto.

### Diferença de topologia de threads

| | Spring Boot | Quarkus JVM |
|---|---|---|
| event loop HTTP | 23,5% da CPU (`reactor-http-epoll`) | **76,0%** (`vert.x-eventloop`) |
| event loop de banco | **63,8%** (`reactor-tcp-epoll`) | — (não existe grupo separado) |
| compilador JIT | 10,4% | 21,5% |

O Spring Boot roda dois grupos de event loop distintos — o servidor HTTP em `reactor-http-epoll` e o
cliente R2DBC em `reactor-tcp-epoll` — e concentra 64% da CPU no segundo. O Quarkus atende HTTP e banco
no mesmo grupo de event loops do Vert.x. Isso é consistente com o peso de `syscall de rede` e de
sincronização observado no lado Spring, mas **este teste não isolou o custo do salto entre threads**;
fica como observação estrutural, não como medida.

## Tarefa 5 — contagem de "quantidade de máquina"

| | Spring Boot | Quarkus JVM |
|---|---|---|
| beans singleton instanciados no startup | **326** | — (modelo CDI) |
| classes geradas em **build time** (`generated-bytecode.jar`) | 0 | **497** |
| — das quais `_Bean` / `_ClientProxy` / `_ProducerMethod` / `_Observer` / `_Subclass` | — | 136 / 48 / 37 / 21 / 5 |
| classes transformadas em build (`transformed-bytecode.jar`) | 0 | 21 |
| classes geradas em build efetivamente **carregadas** em runtime | 0 | 180 |
| proxies dinâmicos JDK gerados em **runtime** (`jdk.proxyN.$ProxyN`) | **117** | 25 |
| classes CGLIB geradas em runtime (`$$SpringCGLIB$$`) | 2 | 0 |
| ByteBuddy | 0 | 1 |
| **total de classes carregadas** | **13.124** | **13.487** |
| lambdas / `LambdaForm` gerados | 3.097 | 1.919 |

As 2 classes CGLIB do Spring são `OrderRepositoryImpl$$SpringCGLIB$$0` e `OrderSummaryRepositoryImpl$$SpringCGLIB$$0`.

A contagem **não** mostra o Spring com mais "máquina": ele gera 119 classes em runtime contra 497 geradas
em build pelo Quarkus (180 carregadas), e o total de classes carregadas é praticamente igual
(13.124 vs 13.487), com o Quarkus ligeiramente à frente.

## Desvios em relação ao ambiente oficial (registrar ao usar)

> **ERRATA (20/09/2026) — alocação de CPU do teste original estava errada.**
> A execução original usou `--cpuset-cpus=0-7` (8 núcleos visíveis, **sem quota**), descrita acima como
> "ergonomia da task Fargate oficial (`TaskCpu=8192`)". Esse número veio de
> `benchmark/docs/fargate-runbook.md`, que **não corresponde aos dados oficiais**. A task real é de
> **1024 unidades / 2048 MB (1 vCPU / 2 GB)**, conforme `CPU_UNITS = 1024` / `MEM_MB = 2048` em
> `analysis/fase5_recursos_fase_isolada.py`, `analysis/fase5_recursos_f2s.py` e
> `analysis/fase5_recursos_f3_rerun.py` — os três scripts que produziram os números oficiais de CPU/memória.
> Consequência: a JVM enxergava 8 processadores em vez de 1, inflando paralelismo de fundo
> (`CICompilerCount` 4 em vez de 2; `ParallelGCThreads` 8 em vez de 1).
> **Os números originais abaixo e nas seções acima foram mantidos como estão**; a reconfirmação sob
> 1 vCPU está na seção seguinte e não os substitui.
>
> **Inconsistência adicional — RESOLVIDA em 20/09/2026 (ver adendo abaixo).** A contagem original
> ("quatro valores diferentes para a mesma task") estava contaminada por uma cópia desatualizada de
> `metodologia.tex`. O valor correto é **1024 CPU units / 2048 MB**. Nenhum `.tex` foi alterado.

### Adendo (20/09/2026) — resolução dos valores conflitantes de CPU/memória da task

**Valor correto: 1024 CPU units / 2048 MB (1 vCPU / 2 GB).** Seis fontes independentes concordam:

1. o `metodologia.tex` real do projeto (Overleaf; versionado no projeto Claude como
   `metodologia_44_.tex`), em cinco lugares;
2. `02-environment.md`, na tabela de especificação de ambiente;
3. `analysis/fase5_recursos_fase_isolada.py:46-47`;
4. `analysis/fase5_recursos_f2s.py:57-58`;
5. `analysis/fase5_recursos_f3_rerun.py:36-37`;
6. `analysis/fase5_analise_estatistica.py:870-871` (`FARGATE_TASK_CPU_UNITS` / `FARGATE_TASK_MEMORY_MB`,
   com o comentário "ver 02-environment.md -- igual nas 3 variantes").

**A fonte de 0,5 vCPU / 1 GB era espúria.** O arquivo consultado nesta investigação
(`~/Downloads/TCC_Bernardo/latex/secoes/metodologia.tex`) era uma cópia solta baixada em 03/08/2026,
**fora do controle de versão** — no repositório, `latex/secoes/` está vazio (só `latex/main.tex` e
`latex/referencias.bib` são versionados). Renomeada para `metodologia.OBSOLETO_NAO_USAR.tex` em
20/09/2026, com `README.md` de aviso ao lado. Não tem autoridade sobre o conteúdo do TCC.

**Checagem independente do denominador 2048 MB.** A `MemoryUtilization` bruta do CloudWatch nas rodadas
oficiais do F1 é ~11,0% (Quarkus JVM) e ~14,4% (Spring Boot). Contra 2048 MB isso dá RSS de 225 MB e
295 MB — plausível para as duas versões, e na razão esperada entre elas. Contra 8192 MB daria ~900 MB e
~1,18 GB; contra 16384 MB, ~1,8 GB e ~2,36 GB — implausível para esta aplicação a 48 req/s. As
porcentagens brutas corroboram o denominador usado pelos scripts.

#### Os dois valores isolados: origem

**`benchmark/docs/fargate-runbook.md:37` (8192/16384) — é o *default do código*, documentado, de uma era
anterior; superado e nunca atualizado.** Não se autodeclara smoke test: pelo contrário, diz "current
official methodology" e intitula a seção "Official Infrastructure Sizing". Mas é demonstravelmente
obsoleto, por quatro sinais convergentes:

- `mtime` de **11/06/2026**, anterior às imagens oficiais (`20260616-160138`) e a toda a coleta oficial
  (fase3 de 06/07 a 13/07, fase3b em 10/08, re-coletas do F1 em 31/08 e do F3 em 06/09). Entrou no git
  só em 31/08, no commit `13f52f3` "snapshot: estado real do pipeline de benchmark Fargate (nunca
  commitado)" — retro-commit de estado, não documento em uso;
- declara `F1: 30 req/s`, que é justamente o valor do **bug conhecido do F1**, corrigido para 48 req/s
  no desenho oficial (ver re-coleta do F1);
- declara `-Xms512m -Xmx6144m`, heap que só aparece em artefatos de junho e **em nenhum dado oficial**;
- declara RDS `db.t3.medium`, contra `db.t3.micro` do default atual de
  `infrastructure/aws/scripts/deploy-order-service-stack.sh:48`.

O número 8192/16384 não foi inventado pelo runbook: é o **default** de
`infrastructure/aws/order-service-stack.yaml:39-42` e de `deploy-order-service-stack.sh:52-53`. O runbook
apenas documentou o default do código. **Nenhum arquivo versionado passa 1024/2048** — as coletas
oficiais obtiveram esse valor por flag na linha de comando (`--task-cpu` / `--task-memory`) no momento do
deploy, e essa invocação não ficou registrada em nenhum script ou log do repositório.

> **Sétimo valor, descoberto nesta checagem:** o `--help` do próprio
> `deploy-order-service-stack.sh:23-24` anuncia "`--task-cpu` Default: 1024" e
> "`--task-memory` Default: 3072", enquanto as variáveis reais nas linhas 52-53 valem 8192/16384. O
> script é internamente inconsistente, e "3072" não corresponde a nenhuma outra fonte. Não corrigido
> aqui (fora do escopo).

**`benchmark/results/task-definition-verification.txt` (4096/8192) — artefato de uma conta AWS diferente,
descartada.** Nunca versionado (`??` no git status), `mtime` de **02/06/2026 08:20**. É saída de um
`describe-task-definition` real. O que o desqualifica de forma decisiva:

- registra `arn:aws:ecs:us-east-1:**169872703824**:task-definition/order-service-springboot:14`, enquanto
  **todos** os artefatos oficiais registram a conta **776648109551** (ex.:
  `analysis/fargate/fase3-f1-rerun/f1-springboot-r1-meta.json` → `aws_account: 776648109551`,
  `task_definition: order-service-springboot:12`). Contas distintas ⇒ ambientes distintos; a revisão `:14`
  **não** é uma revisão posterior da `:12` oficial, são numerações independentes;
- `169872703824` aparece em **um único arquivo** de todo o repositório: este;
- traz `-Xmx6144m`, o heap da era do runbook;
- a data coincide com as execuções `aws-order-service-validation-4vcpu8gb-f2-300-springboot-...-short-20260601*`,
  que se autodescrevem como `validation` e `short`.

O histórico de revisões dessa task definition na AWS **não é consultável** (conta abandonada, infra
derrubada), mas é dispensável: a divergência de conta já explica o valor.

#### Nenhum dos dois gerou dado oficial

Verificado, e este era o critério de parada: o pipeline oficial
(`fase5_analise_estatistica.py`) lê **apenas** `analysis/fargate/fase3`, `fase3b`, `fase3-f1-rerun`,
`fase3-f3-rerun` e `analysis/lambda/fase4`. Uma busca por `8vcpu16gb`, `4vcpu8gb` e `6144m` em
`analysis/fargate/` e `analysis/lambda/` **não retorna nada**. Os artefatos `8vcpu16gb` e `4vcpu8gb`
existem só em `benchmark/results/` e `benchmark/collected_results/`, todos datados de 01/06 a 05/06/2026,
anteriores a qualquer dado oficial. As execuções `official-clean-8vcpu16gb-...` de 04-05/06 (F2-300, que
o próprio runbook reclassifica como F3-S) ficaram em `benchmark/results/_cloudwatch/` e não foram
promovidas para `analysis/`. **Os dois valores isolados são resíduo de era pré-oficial descartada; não
contaminam nenhum CSV oficial.**

- Heap `-Xmx2g` nos dois lados, contra `-Xmx6144m` da task Fargate oficial (RAM da máquina local não
  comportava). Carga de 48 req/s não pressiona heap; GC ficou em 0,5% da CPU nos dois.
- Memória do contêiner em 3 GB, contra 2048 MB da task oficial. Mantida igual na reconfirmação de
  1 vCPU para isolar a variável de CPU.
- Postgres 16 em container local, não RDS t3.medium.
- Duração de 16 min por repetição, não os 24–25 min oficiais.
- Flags `-XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints` adicionadas nas duas versões para
  precisão do stack walking; não alteram o caminho quente.
- Evento de CPU é `ctimer`, não `perf`: o host está com `perf_event_paranoid=2` e o seccomp do Docker
  bloqueia `perf_event_open`. `ctimer` não atribui tempo de kernel a frames de kernel — syscalls
  aparecem pela frame de entrada em libc (`send`, `__GI___writev`), que é como estão categorizadas.
- `compilador JIT` ainda responde por 10–22% da CPU na janela t+120–480 s: nessa taxa a aplicação segue
  compilando. É CPU real do contêiner e está contabilizada, mas não é caminho de requisição.

## Reconfirmação sob 1 vCPU (20/09/2026) — escopo reduzido

Correção da errata acima. **Única variável alterada:** `--cpus=1` (quota `cpu.max` 100000/100000 =
1024 unidades = task Fargate oficial). Imagens, carga, Postgres, categorias e `analyze.py` idênticos.
Escopo reduzido a **2 repetições por versão** (contra 3 no original). Resultados em `results_1vcpu/`.

> **ADENDO (24/09/2026) — o Spring Boot desta reconfirmação rodou com `validation-query: SELECT 1` ativa.**
> A linha `spring.r2dbc.pool.validation-query: SELECT 1` do `application.yml` estava ligada aqui (e no
> teste original de 8 núcleos) sem que se soubesse da sua existência; `pg_stat_statements_rds/` mostrou
> depois que ela explica 86% do gap de CPU **do RDS** em F1. O profiling foi repetido com a validação
> desligada: ver "Adendo (24/09/2026) — repetição sem `validation-query`" no fim desta seção e
> `validacao_conexao/NOTAS_validacao_conexao.md`. **Os números desta seção foram mantidos como estão.**

### Verificação da restrição antes da carga (tarefa 1)

A JVM foi consultada dentro do contêiner em cada repetição, com aborto automático se não batesse:

```
CPU Quota is: 100000 / CPU Period is: 100000
CPU Quota count based on quota/period: 1
OSContainer::active_processor_count: 1
```

As 4 repetições registraram `active_processor_count=1` no log. Efeito na ergonomia da JVM:

| flag | 8 núcleos (original) | 1 vCPU (corrigido) |
|---|---|---|
| `CICompilerCount` | 4 | **2** |
| `ParallelGCThreads` | 8 | **0** = calcular em runtime |
| threads de GC efetivamente criadas | `GC Thread#0..#7` (8) | **`GC Thread#0` (1)** |

(a última linha é contagem observada nos perfis `wall`, não inferência da flag)

### Categorias sensíveis a paralelismo de fundo (self time)

| categoria | SB 8 núcleos | SB 1 vCPU | QJ 8 núcleos | QJ 1 vCPU |
|---|---|---|---|---|
| **compilador JIT** | 10,44% | **8,44%** | 21,55% | **19,58%** |
| **GC** | 0,48% | **0,16%** | 0,37% | **0,20%** |
| proxy dinâmico | 0,42% | 0,43% | 0,34% | 0,27% |
| reflexão | 2,20% | 2,55% | 2,53% | 2,60% |
| AOP / `@Transactional` | 0,08% | 0,10% | ~0,00% | ~0,00% |
| **soma da hipótese** | **2,70%** | **3,07%** | **2,87%** | **2,87%** |
| **hipótese como % do gap** | **2,6%** | **3,2%** | | |

O efeito previsto existe e está na direção esperada — JIT cai ~2pp e GC cai para 1/3 — mas é pequeno
demais para mudar o quadro. A hipótese continua respondendo por **~3% do gap**. Em proxy a inversão
persiste: inclusivo, Quarkus 0,01625 vCPU contra 0,00769 do Spring Boot.

Consistência entre repetições **melhorou** com a correção (desvio máximo quase todo abaixo de 0,5pp,
contra até ±4,41pp no original), o que é coerente com menos threads de fundo concorrendo.

### Os três achados principais se mantêm

| achado | SB 8 núcleos | SB 1 vCPU | variação |
|---|---|---|---|
| Spring Data: render de SQL por requisição | 0,01754 vCPU | 0,01757 vCPU | +0,2% |
| exceção: `fill_in_stack_trace` (total) | 0,00741 vCPU | 0,00814 vCPU | +9,9% |
| — dos quais `PropertyPath`/`PropertyReferenceException` | 0,00611 vCPU | 0,00683 vCPU | +11,8% |
| `itable stub` (% self do total) | 7,72% | 7,83% | +0,1pp |
| Reactor: propagação de `Context` | 0,00619 vCPU | 0,00504 vCPU | −18,6% |

Nos três casos o Quarkus segue em 0,00000 vCPU para render de SQL e exceção, e `itable stub` no Quarkus
vai de 2,59% para 2,75%. Como previsto, são custos por chamada na própria thread de requisição e não
dependem de quantos núcleos existem.

### Quebra completa por categoria sob 1 vCPU (self time)

Reprocessamento dos mesmos `.jfr`/`.collapsed` já salvos, com o mesmo `analyze.py` e as mesmas
categorias — sem coleta nova. Média das 2 repetições; `desvio` = maior desvio de uma repetição
em relação à média. (A soma da hipótese é 3,07% pelo cálculo exato; a tabela de categorias sensíveis
acima mostrava 3,08% por somar valores já arredondados.)

| categoria | Spring Boot | desvio | Quarkus JVM | desvio |
|---|---|---|---|---|
| jdk_outro (coleções, String, atomics) | 19,18% | ±0,08pp | 13,17% | ±0,11pp |
| plumbing reativo (Reactor / Mutiny) | 13,45% | ±0,30pp | 1,54% | ±0,02pp |
| syscall de rede (send/recv/epoll) | 13,00% | ±0,10pp | 26,15% | ±0,49pp |
| servidor HTTP (Netty / Vert.x) | 9,26% | ±0,00pp | 15,12% | ±0,33pp |
| despacho virtual/interface (itable/vtable stub) | 8,54% | ±0,09pp | 3,44% | ±0,05pp |
| compilador JIT (C1/C2) | 8,44% | ±0,21pp | 19,58% | ±0,44pp |
| nativo da VM | 6,40% | ±0,13pp | 1,63% | ±0,06pp |
| ORM / mapeador | 5,04% | ±0,12pp | 0,42% | ±0,15pp |
| driver de banco (R2DBC / Vert.x PG) | 4,32% | ±0,07pp | 2,51% | ±0,27pp |
| framework_outro | 3,34% | ±0,01pp | 3,63% | ±0,41pp |
| reflexão (`java.lang.reflect`, `MethodHandle`) | 2,55% | ±0,02pp | 2,60% | ±0,39pp |
| nativo libc | 1,83% | ±0,01pp | 1,56% | ±0,09pp |
| não classificado | 1,64% | ±0,18pp | 1,57% | ±0,40pp |
| JSON (Jackson) | 1,00% | ±0,07pp | 2,60% | ±0,04pp |
| VM (outras threads) | 0,59% | ±0,03pp | 1,45% | ±0,02pp |
| lógica de negócio (`com.tcc.orderservice`) | 0,50% | ±0,06pp | 2,18% | ±0,10pp |
| proxy dinâmico / geração de proxy | 0,43% | ±0,00pp | 0,27% | ±0,09pp |
| sincronização | 0,22% | ±0,07pp | 0,37% | ±0,06pp |
| GC | 0,16% | ±0,00pp | 0,20% | ±0,02pp |
| interceptação AOP / `@Transactional` | 0,10% | ±0,01pp | ~0,00% | — |
| **soma da hipótese** | **3,07%** | | **2,87%** | |

Amostras: SB 6.068 / 5.549 · QJ 2.304 / 2.237.

### Gap absoluto sob 1 vCPU (equivalente à Tarefa 4)

SB 0,1613 vCPU − QJ 0,0631 vCPU = **gap de 0,0983 vCPU** (razão 2,56×).

| categoria | SB (vCPU) | QJ (vCPU) | delta | % do gap |
|---|---|---|---|---|
| jdk_outro (coleções, String, atomics) | 0,03096 | 0,00831 | +0,02265 | **23,0%** |
| plumbing reativo (Reactor / Mutiny) | 0,02168 | 0,00097 | +0,02071 | **21,1%** |
| despacho virtual/interface | 0,01378 | 0,00217 | +0,01161 | **11,8%** |
| nativo da VM | 0,01033 | 0,00103 | +0,00931 | 9,5% |
| ORM / mapeador | 0,00814 | 0,00026 | +0,00788 | 8,0% |
| servidor HTTP (Netty / Vert.x) | 0,01494 | 0,00954 | +0,00540 | 5,5% |
| driver de banco (R2DBC / Vert.x PG) | 0,00697 | 0,00158 | +0,00539 | 5,5% |
| syscall de rede | 0,02099 | 0,01650 | +0,00449 | 4,6% |
| framework_outro | 0,00539 | 0,00229 | +0,00310 | 3,2% |
| reflexão | 0,00411 | 0,00164 | +0,00247 | 2,5% |
| nativo libc | 0,00296 | 0,00099 | +0,00197 | 2,0% |
| não classificado | 0,00267 | 0,00099 | +0,00168 | 1,7% |
| compilador JIT | 0,01360 | 0,01235 | +0,00125 | 1,3% |
| proxy dinâmico | 0,00069 | 0,00017 | +0,00053 | 0,5% |
| interceptação AOP / `@Transactional` | 0,00015 | 0,00000 | +0,00015 | 0,2% |
| GC | 0,00026 | 0,00013 | +0,00014 | 0,1% |
| sincronização | 0,00035 | 0,00024 | +0,00011 | 0,1% |
| VM (outras threads) | 0,00094 | 0,00092 | +0,00003 | 0,0% |
| JSON (Jackson) | 0,00163 | 0,00164 | −0,00001 | −0,0% |
| lógica de negócio | 0,00081 | 0,00137 | −0,00057 | −0,6% |
| **HIPÓTESE (proxy + reflexão + AOP)** | **0,00496** | **0,00181** | **+0,00315** | **3,2%** |

A ordem dos três primeiros muda em relação aos 8 núcleos (lá era reativo 20,2% > jdk_outro 19,7% >
despacho 11,3%; aqui jdk_outro 23,0% > reativo 21,1% > despacho 11,8%), mas o conjunto e as magnitudes
são os mesmos. `compilador JIT` sai de 3,8% para 1,3% do gap — efeito direto da correção.

### 8 núcleos vs 1 vCPU, todas as categorias

| categoria | SB 8n | SB 1v | Δ SB | QJ 8n | QJ 1v | Δ QJ |
|---|---|---|---|---|---|---|
| jdk_outro | 17,36% | 19,18% | +1,83pp | 13,22% | 13,17% | −0,05pp |
| plumbing reativo | 13,09% | 13,45% | +0,36pp | 1,43% | 1,54% | +0,11pp |
| syscall de rede | 14,95% | 13,00% | **−1,94pp** | 23,03% | 26,15% | **+3,12pp** |
| servidor HTTP | 9,42% | 9,26% | −0,15pp | 15,06% | 15,12% | +0,06pp |
| despacho virtual/interface | 8,35% | 8,54% | +0,19pp | 3,62% | 3,44% | −0,18pp |
| compilador JIT | 10,44% | 8,44% | **−2,01pp** | 21,55% | 19,58% | **−1,96pp** |
| nativo da VM | 6,28% | 6,40% | +0,12pp | 1,99% | 1,63% | −0,36pp |
| ORM / mapeador | 4,04% | 5,04% | +1,00pp | 0,25% | 0,42% | +0,16pp |
| driver de banco | 4,36% | 4,32% | −0,03pp | 3,28% | 2,51% | −0,78pp |
| framework_outro | 2,99% | 3,34% | +0,35pp | 4,29% | 3,63% | −0,67pp |
| reflexão | 2,20% | 2,55% | +0,35pp | 2,53% | 2,60% | +0,07pp |
| nativo libc | 1,87% | 1,83% | −0,03pp | 1,35% | 1,56% | +0,21pp |
| não classificado | 1,42% | 1,64% | +0,22pp | 1,58% | 1,57% | −0,01pp |
| JSON (Jackson) | 0,92% | 1,00% | +0,08pp | 2,92% | 2,60% | −0,32pp |
| VM (outras threads) | 0,58% | 0,59% | +0,00pp | 1,28% | 1,45% | +0,17pp |
| lógica de negócio | 0,48% | 0,50% | +0,02pp | 1,49% | 2,18% | +0,70pp |
| proxy dinâmico | 0,42% | 0,43% | +0,01pp | 0,34% | 0,27% | −0,07pp |
| sincronização | 0,27% | 0,22% | −0,05pp | 0,40% | 0,37% | −0,03pp |
| GC | 0,48% | 0,16% | **−0,32pp** | 0,37% | 0,20% | **−0,17pp** |
| interceptação AOP | 0,08% | 0,10% | +0,01pp | ~0,00% | ~0,00% | +0,00pp |

**Cuidado ao ler os pp acima:** o total caiu com a correção (SB 0,1854 → 0,1613 vCPU, −13%;
QJ 0,0701 → 0,0631, −10%). Uma categoria que ficou estável em valor absoluto **sobe** em percentual.
Em vCPU absoluto, as variações reais são:

| categoria | SB 8n → 1v | var. SB | QJ 8n → 1v | var. QJ |
|---|---|---|---|---|
| GC | 0,00089 → 0,00026 | **−70%** | 0,00026 → 0,00013 | **−52%** |
| compilador JIT | 0,01962 → 0,01360 | **−31%** | 0,01524 → 0,01235 | **−19%** |
| syscall de rede | 0,02805 → 0,02099 | **−25%** | 0,01622 → 0,01650 | +2% |
| driver de banco | 0,00810 → 0,00697 | −14% | 0,00230 → 0,00158 | −31% |
| jdk_outro | 0,03196 → 0,03096 | −3% | 0,00919 → 0,00831 | −10% |
| framework_outro | 0,00548 → 0,00539 | −2% | 0,00301 → 0,00229 | −24% |
| ORM / mapeador | 0,00744 → 0,00814 | +9% | 0,00018 → 0,00026 | +50% |
| lógica de negócio | 0,00087 → 0,00081 | −7% | 0,00104 → 0,00137 | +33% |

Lendo em absoluto, nada mudou de forma inesperada:

- **GC e JIT** são as maiores quedas reais — exatamente as duas categorias previstas, e na proporção
  esperada (8→1 thread de GC, `CICompilerCount` 4→2).
- **`syscall de rede` no Spring Boot cai 25%** — é a única categoria *não* ligada a paralelismo de fundo
  com variação real relevante. Observação plausível: sob 1 vCPU os dois grupos de event loop do Spring
  (`reactor-http-epoll` e `reactor-tcp-epoll`) passam a se multiplexar no mesmo processador, o que reduz
  despertares entre CPUs. **Não foi isolado neste teste** — fica como observação, não como medida.
  No Quarkus, que tem um único grupo de event loops, a mesma categoria fica plana (+2%): o `+3,12pp`
  da tabela anterior é puro efeito de denominador.
- **`jdk_outro` no SB (+1,83pp)** é efeito de denominador: em absoluto caiu 3%.
- **ORM/mapeador e lógica de negócio no Quarkus** variam muito em termos relativos (+50%, +33%), mas
  partem de bases minúsculas (0,00018 e 0,00104 vCPU) — é ruído de contagem baixa, não sinal.

### Validação da razão vCPU contra os dados oficiais (tarefa 5)

CPU do cgroup medida **na janela de profiling** (t+120–480 s), que é onde o perfil é colhido:

| | SB | QJ | razão |
|---|---|---|---|
| original, 8 núcleos | 0,1860 vCPU | 0,0706 vCPU | 2,63× |
| **reconfirmação, 1 vCPU** | **0,1617 vCPU** | **0,0633 vCPU** | **2,55×** |
| profiler (1 vCPU), para conferência | 0,1613 vCPU | 0,0631 vCPU | 2,56× |

Razões oficiais Spring Boot / Quarkus JVM por cenário (task 1024/2048, `fase5_f2s_recursos_NOTAS.md`):

| cenário | SB | QJ | razão |
|---|---|---|---|
| **F1** (cenário reproduzido aqui) | 11,12% | 4,33% | **2,57×** |
| F2 | 21,37% | 7,72% | 2,77× |
| F3 | 45,67% | 16,26% | 2,81× |
| F2-S | 3,72% | 1,45% | 2,57× |

A reconfirmação dá **2,55× contra 2,57× do F1 oficial** — a correção de CPU *aproximou* a reprodução do
alvo (o original, com 8 núcleos, dava 2,63×). A validade externa não foi quebrada; melhorou.

Nota sobre a faixa "2,6–3,9×": ela mistura duas comparações. Spring Boot contra **Quarkus JVM** fica em
2,57–2,81× nos cenários oficiais; os valores próximos de 3,9× são Spring Boot contra **Quarkus Native**,
que não faz parte deste teste.

### Adendo (24/09/2026) — repetição sem `validation-query`

Mesmo ambiente desta reconfirmação (mesmas imagens `pilhaexp-*:prof` de 20/09, `cpu.max` = `100000 100000`
lido do cgroup e `active_processor_count=1` confirmados em cada rodada antes da carga, mesmo async-profiler,
mesmo `analyze.py`). **Única variável alterada:** `SPRING_R2DBC_POOL_VALIDATION_QUERY=` (vazia) no Spring Boot.
Smoke antes da coleta com `log_statement=all` no Postgres local: 2.585 `SELECT 1` em 60 s com validação,
**0** sem. 3 rodadas de SB sem validação + 1 âncora de SB **com** validação no mesmo dia (0,1681 vCPU, dentro
da faixa 0,1541–0,1686 das duas rodadas desta seção: sem deriva de host visível). Quarkus JVM reaproveitado
desta seção. Detalhes, sanidade por rodada e calibração dos padrões em
`validacao_conexao/NOTAS_validacao_conexao.md`; saída completa em `validacao_conexao/results/COMPARACAO.txt`.

**Gap absoluto:**

| | SB (vCPU) | QJ (vCPU) | gap | razão |
|---|---|---|---|---|
| com validação (esta seção, 2 rodadas) | 0,1613 | 0,0631 | 0,0983 | 2,56× |
| com validação (2 rodadas + âncora) | 0,1636 | 0,0631 | 0,1005 | 2,59× |
| **sem validação (3 rodadas)** | **0,1511** | 0,0631 | **0,0881** | **2,40×** |

Queda de 12,4% do gap (7,0% excluindo `sbnv-r1`, a rodada mais baixa). Welch 3 × 3 no total do SB: t = −1,73,
**não significativo**. A diferença entre as duas rodadas com validação desta seção (0,0144 vCPU) é da mesma
ordem que o efeito médio (0,0125).

**Categorias sensíveis (self time, vCPU, 3 com × 3 sem):**

| categoria | com val. | sem val. | Δ % | t | % do gap com → sem |
|---|---|---|---|---|---|
| **syscall de rede** | 0,02102 | 0,01743 | **−17,1%** | **−5,02** | 4,6% → 1,1% |
| **driver de banco** | 0,00701 | 0,00533 | **−23,9%** | **−4,16** | 5,5% → 4,3% |
| servidor HTTP (Netty) | 0,01556 | 0,01583 | +1,7% | 0,34 | 5,5% → 7,1% |
| plumbing reativo | 0,02146 | 0,01912 | −10,9% | −2,36 | 21,1% → 20,6% |
| despacho virtual/interface | 0,01378 | 0,01210 | −12,2% | −3,47 | 11,8% → 11,3% |
| thread `reactor-tcp-epoll` | 0,10496 | 0,09103 | −13,3% | −3,29 | |
| thread `reactor-http-epoll` | 0,04308 | 0,04368 | +1,4% | 0,32 | |
| `io.r2dbc.pool.Validation` (inclusivo) | 0,00206 | 0,00054 | −73,9% | −10,44 | |
| **total do SB** | 0,16358 | 0,15112 | −7,6% | −1,73 | |

Syscall de rede e driver de banco são as únicas categorias que caem bem acima da proporção do total, com
|t| > 4: juntas perdem 0,00527 vCPU, contra 0,00213 esperados se caíssem na mesma proporção do total.

**Os três mecanismos em vCPU absoluto** (padrões inclusivos reconstruídos; reproduzem exatamente os valores
publicados acima e no teste de 8 núcleos):

| mecanismo | com val. (esta seção) | sem val. | Δ % (3 × 3) | t | fração da CPU do SB, com → sem |
|---|---|---|---|---|---|
| render de SQL (Spring Data) | 0,01757 | 0,01680 | −7,1% | −1,29 | 11,05% → 11,12% |
| `PropertyPath` / `PropertyReferenceException` | 0,00683 | 0,00651 | −8,2% | −1,39 | 4,33% → 4,31% |
| exceção `fill_in_stack_trace` (total) | 0,00814 | 0,00735 | −12,9% | −1,73 | 5,15% → 4,86% |
| Reactor: propagação de `Context` | 0,00504 | 0,00453 | −7,6% | −0,93 | 2,99% → 2,99% |
| `itable stub` (self) | 0,01263 (7,83%) | 0,01094 (7,24%) | −13,5% | −3,47 | 7,74% → 7,24% |

**Resposta direta:** os três mecanismos são, na prática, **adicionais** ao custo da validação. Sem validação o
gap ainda mostra os três em magnitude parecida (render de SQL 19,1% do gap, `PropertyPath` 7,4%, reativo
20,6% + despacho 11,3%), e render de SQL, `PropertyPath` e `Context` mantêm a fração da CPU do SB até a
segunda casa decimal. As variações absolutas deles (−4% a −8%, |t| < 1,4) ficam dentro da amplitude entre
repetições. O custo da validação no contêiner estava em `syscall de rede`, `driver de banco`, no event loop
do R2DBC e nas frames do `io.r2dbc.pool`, nenhuma delas entre os três mecanismos. **Exceção parcial:** plumbing
reativo e despacho de interface caem um pouco além do proporcional (0,00133 vCPU somados, ≈1,3% do gap
original), parcela compatível com tráfego de validação passando pela cadeia de operadores do Reactor.

## Arquivos

- `run_one.sh` / `run_all.sh` / `count_machinery.sh` — execução (desacoplada, sob `systemd-inhibit`).
- `analyze.py` — classificação e quantificação; `results/ANALISE.txt` é a saída completa.
- `results/AGREGADO-{springboot,quarkusjvm}.{cpu,wall}.html` — flame graphs agregados das 3 repetições.
- `results/{sb,qj}-r{1,2,3}.{cpu,wall}.html` — flame graph por repetição (12 arquivos).
- `results/DIFF-r1-quarkus-para-springboot.cpu.html` — flame graph diferencial (vermelho = mais CPU no SB).
- `results/*.jfr` — gravações brutas; `results/*.collapsed` — stacks para requantificação.
- `results/*.cpu.tsv` — CPU/memória do cgroup a cada 5 s; `results/*.k6.csv.gz` — métricas da carga.

### Reconfirmação sob 1 vCPU

- `run_all_1vcpu.sh` — driver da reconfirmação (`CPU_QUOTA=1`, `OUT_DIR=results_1vcpu`).
  `run_one.sh` ganhou as variáveis `CPU_QUOTA` e `OUT_DIR`; sem elas o comportamento é o original.
- `results_1vcpu/ANALISE.txt` — saída completa do mesmo `analyze.py`.
- `results_1vcpu/AGREGADO-{springboot,quarkusjvm}-1vcpu.cpu.html` — flame graphs agregados (2 repetições).
- `results_1vcpu/DIFF-1vcpu-quarkus-para-springboot.cpu.html` — diferencial entre versões, sob 1 vCPU.
- `results_1vcpu/DIFF-springboot-8nucleos-para-1vcpu.cpu.html` — diferencial do **mesmo** Spring Boot
  entre as duas alocações de CPU; é onde o efeito da correção aparece isolado.
- `results_1vcpu/{sb,qj}-r{1,2}.{cpu,wall}.html` — flame graph por repetição (8 arquivos).

### Repetição sem `validation-query` (24/09/2026)

- `validacao_conexao/NOTAS_validacao_conexao.md` — setup, sanidade, calibração e resultado completo.
- `validacao_conexao/smoke_validacao.sh` — smoke da desativação com controle positivo (`log_statement=all` temporário).
- `validacao_conexao/run_one_valcon.sh` / `run_all_valcon.sh` — cópia de `run_one.sh` + variável de
  validação e checagem de `cpu.max`; driver das 4 rodadas (`sbnv-r1..r3`, âncora `sbval-a1`).
- `validacao_conexao/compara_valcon.py` — comparação (importa `analyze.py`); saída em `validacao_conexao/results/COMPARACAO.txt`.
- `validacao_conexao/results/` — `.jfr`, `.collapsed`, `.html`, `.cpu.tsv`, `.k6.csv.gz` por rodada.
