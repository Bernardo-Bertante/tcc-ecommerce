# Exploratório: os picos de p95 do Spring Boot no F3 coincidem com pausas de GC? (20/09/2026)

**Não é resultado formal do TCC.** Sinal direcional para a pendência de §6.4 (instabilidade de
cauda do Spring Boot no F3, descrita e não explicada). Mesmo status de
`analysis/exploratorio_gc_f1/`, `analysis/exploratorio_cpu_lambda/` e
`analysis/exploratorio_pilha_fargate/`. Nenhum `.tex` ou `.md` do projeto principal alterado.

## Fenômeno alvo (dados oficiais, `analysis/fargate/fase3-f3-rerun/`)

p95 por rodada (ms), calculado dos `*-latency.json` oficiais:

| runtime | r1 | r2 | r3 | r4 | r5 |
|---|---|---|---|---|---|
| **springboot** | 326 | **1022** | **874** | 73 | 94 |
| quarkus-jvm | 38 | 37 | 40 | 47 | 39 |
| quarkus-native | 51 | 37 | 33 | 34 | 30 |

Observação factual de desenho, relevante para a reprodução: as rodadas do Spring Boot **não** se
dividem ao acaso. r1-r3 (326/1022/874 ms) rodaram em 02/09/2026; r4-r5 (73/94 ms) em 05/09/2026.
A separação é por **bloco de coleta**, não por rodada. Implicação para este teste: um efeito que
varia por sessão pode não aparecer em 5 repetições locais consecutivas no mesmo dia.

## VERIFICAÇÃO DE CPU/MEMÓRIA ANTES DE QUALQUER CARGA (obrigatória)

### 1. Quota do cgroup — `--cpus=1`, não `--cpuset-cpus` sem cota

```
$ docker run --rm --cpus=1 -m 2g --memory-swap 2g ... 
cpu.max      = 100000 100000     <- 1 vCPU exato, quota (= task Fargate 1024 units)
memory.max   = 2147483648        <- 2 GiB (= task Fargate 2048 MB)
cpuset.cpus  = [0-15]            <- sem pinning; restrição é por quota, como no Fargate
```

### 2. A JVM detecta 1 processador — CONFIRMADO nas duas imagens

`java -XshowSettings:system -version` **dentro** do contêiner:

```
Operating System Metrics:
    Provider: cgroupv2
    Effective CPU Count: 1
    CPU Period: 100000us
    CPU Quota: 100000us
    Memory Limit: 2.00G
openjdk version "21.0.11" 2026-04-21 LTS (Red_Hat-21.0.11.0.10-1)
```

Ergonomia resultante (`-XX:+PrintFlagsFinal`), idêntica em `gcf3-sb:official` e `gcf3-qj:official`:
`CICompilerCount = 2 {ergonomic}`, `ParallelGCThreads = 0`, `UseSerialGC = true {ergonomic}`,
`UseG1GC = false`. Assinatura inequívoca de 1 CPU visível.

### 3. Memória: 2 GB, igual ao oficial. Nenhum `-Xmx` será passado

Confirmado na AWS que as três task definitions oficiais **não têm** `JAVA_OPTS`/`JAVA_OPTS_APPEND`:
o heap é o que o `run-java.sh` da imagem calcula a partir do limite de 2 GB. O
`-Xmx2g` do `exploratorio_pilha_fargate` era desvio; aqui não se repete. A única flag adicionada é
o log de GC, via `JAVA_OPTS_APPEND` (que o `run-java.sh` **acrescenta**, sem substituir nada).

## Auditoria do ambiente do `exploratorio_gc_f1` — ESTAVA CORRETO

O `gc_f1` usou `--cpuset-cpus=3 -m 2g` (1 núcleo dedicado, **sem** cota). Verificado nesta data que
essa configuração produz a **mesma** ergonomia que `--cpus=1`:

```
--cpuset-cpus=3   -> Effective CPU Count: 1, CPU Quota: -1, CICompilerCount=2, UseSerialGC=true
--cpus=1          -> Effective CPU Count: 1, CPU Quota: 100000, CICompilerCount=2, UseSerialGC=true
--cpuset-cpus=0-7 -> Effective CPU Count: 8, CPU Quota: -1, CICompilerCount=4, UseG1GC=true  (ERRADO)
```

Ou seja: o erro de 8 núcleos foi **exclusivo** do `exploratorio_pilha_fargate`. O método e os
números do `gc_f1` são reaproveitáveis. Diferença residual: `cpuset` dá um núcleo exclusivo,
`--cpus=1` dá cota de 1 CPU distribuída — o Fargate é por cota, então aqui se usa `--cpus=1`.

## Tag das imagens — a do F3 NÃO é a mesma do F1/F2 no Spring Boot

Consultado o ECR e as task definitions oficiais (conta 776648109551):

| runtime | task def oficial do F3 | cpu/mem | imagem | digest | tag no ECR |
|---|---|---|---|---|---|
| springboot | `order-service-springboot:12` | **1024/2048** | `:latest` | `sha256:276548dd…` | **`latest`** (push 21/06/2026) |
| quarkus-jvm | `order-service-quarkus-jvm:10` | **1024/2048** | `:20260616-160138` | `sha256:abec3583…` | `20260616-160138` |
| quarkus-native | `order-service-quarkus-native:9` | **1024/2048** | `:20260616-160138` | `sha256:650b4e42…` | `20260616-160138` |

**O Spring Boot oficial do F3 é um build de 21/06/2026 (`latest`, `276548dd`), não o
`20260616-160138` (`cb6ab3f8`)** usado no `gc_f1` e no `pilha_fargate`. São digests distintos. A
imagem correta foi baixada do ECR por digest e marcada localmente como `gcf3-sb:official`; o
Quarkus JVM oficial é o `20260616-160138`, marcado como `gcf3-qj:official`.

As três task definitions oficiais confirmam **1024/2048** direto na AWS — sétima fonte concordante,
e a única primária (ver errata em `../exploratorio_pilha_fargate/NOTAS_pilha_fargate.md`).

## Carga a reproduzir (estrutura oficial exata, dos `*-meta.json`)

`benchmark/scenarios/f3_black_friday_controlled.js`, `ramping-arrival-rate`, 25 min:
baseline 5m@48 → ramp_up 2m linear → peak 10m@240 → recovery_ramp 2m linear → recovery 5m@48 →
ramp_down 1m. `theoretical_iterations = 208800`. Taxas 48/240/48 são obrigatórias (guard no script).

**Intervalo real entre rodadas oficiais: 1,1 a 1,5 min** — não 30 min. Medido de
`k6_return_utc` → `k6_invoke_utc` consecutivos nos metas. A task **não** era reiniciada entre
rodadas do mesmo runtime, então a JVM chegava aquecida na rodada seguinte.

## Execução: duas tentativas

**Tentativa 1 (20/09, arquivada em `results_tentativa1_db_saturado/`) — INVÁLIDA.** Sem reset do
dataset entre rodadas (para ser fiel ao protocolo oficial, que não reiniciava a task), o banco
cresceu 0 → 67k → 134k → 195k pedidos e o **Postgres local saturou**. A r3 colapsou: p95 de 18,3 s,
throughput de 141 req/s em vez de 240, 18.788 iterações descartadas, `Insufficient VUs` a 3000 VUs.

Causa isolada por medição direta dos três componentes no pico da r4:

| componente | CPU no pico | limite |
|---|---|---|
| app Spring Boot | 0,308 vCPU | 1,0 |
| **Postgres** | **1,999 vCPU** | **2,0** |
| k6 | 0,36 vCPU | 4,0 |

O app estava a 31% da cota e o k6 a 9% — o que descarta a hipótese alternativa de que o gerador de
carga estivesse inflando a latência. O gargalo era o banco. Comparação com o oficial confirma que é
artefato local: o RDS oficial no pico do F3 ficou em **58-62% de CPU média** (máx 82-85%).

Bloco interrompido na r4 para não gastar 1h45 gerando dados incapazes de responder a pergunta.
r1-r3 preservadas com logs de GC recuperados.

**Bug de ferramenta encontrado no caminho:** o `-Xlog` do JVM rotaciona o arquivo em 20 MB
(`filesize=20M` default), o que quebrou o fatiamento por offset de bytes a partir da r2 (slice de 0
bytes). Corrigido de duas formas: `filecount=0` desliga a rotação, e o `slice_gc.py` passou a fatiar
por **timestamp absoluto**. Validado: a r1 refatiada por timestamp dá as mesmas 9.499 pausas do slice
original por bytes.

**Correções aplicadas para a tentativa 2:**
1. `TRUNCATE` antes de cada rodada, com o app **em pé** — remove a deriva do dataset sem reiniciar a
   JVM, preservando o aquecimento entre rodadas que o oficial tinha.
2. Postgres com `--cpus=4` em núcleos 4-9, 4 GB, `shared_buffers=1GB`.
3. Núcleos disjuntos: PG em 4-9, k6 em 10-15, app com cota de 1,0 flutuando (como no Fargate).
4. `filecount=0` no `-Xlog`.

**Calibração antes de relançar** (8 min, pico real de 240 req/s):

| | tentativa 1 (r3) | calibração | oficial |
|---|---|---|---|
| p95 | 18.310 ms | **48 ms** | 73–1022 ms |
| CPU do app no pico | 0,31 vCPU | **0,460 vCPU** | **~0,46 vCPU** |
| CPU do banco no pico | 100% | 14% da cota | 58–62% |
| VUs / descartes | esgotou 3000 / 18.788 | 1500 / 0 | — |

A CPU do app no pico local (0,460 vCPU) reproduz a do F3 oficial (~0,46 vCPU) — validação externa
direta. O banco passou a usar menos CPU que o RDS oficial (dataset truncado, sem SSL nem rede):
divergência do oficial, mas na direção segura, pois deixou de mascarar o comportamento do app.

**Tentativa 2 (20-21/09) — VÁLIDA.** 5 rodadas Spring Boot + 2 Quarkus JVM, todas com `k6_exit=0`,
sem thresholds cruzados, sem descartes. Guard de ergonomia (`1 available`) passou nas duas versões.

## Resultados por rodada

| rodada | p95 | p99 | max | pausas/min | pausa média | pausa máx | tempo em GC |
|---|---|---|---|---|---|---|---|
| sb-r1 | 65,2 ms | 109,9 ms | 2191,9 ms | 600,8 | 3,72 ms | 196,7 ms | 3,72% |
| sb-r2 | 72,2 ms | 125,9 ms | 1348,6 ms | 566,9 | 4,29 ms | **503,9 ms** | 4,06% |
| sb-r3 | 71,9 ms | 127,6 ms | 622,9 ms | 595,3 | 4,27 ms | 128,4 ms | 4,23% |
| sb-r4 | 70,4 ms | 122,9 ms | 512,2 ms | 729,7 | 4,19 ms | 132,6 ms | 5,09% |
| sb-r5 | 66,8 ms | 112,6 ms | 471,4 ms | 705,8 | 4,18 ms | 125,5 ms | 4,91% |
| qj-r1 | 46,4 ms | 69,9 ms | 278,5 ms | 48,8 | 1,76 ms | 5,78 ms | 0,143% |
| qj-r2 | 50,9 ms | 85,7 ms | 835,0 ms | 41,8 | 2,10 ms | 5,39 ms | 0,146% |

### Tarefa 3: as 5 repetições NÃO reproduziram o pior caso oficial

p95 local entre **65,2 e 72,2 ms** — variação de 11%. As cinco rodadas oficiais variaram **14×**
(73 a 1022 ms). Nenhuma repetição chegou perto de 1022 ms. Registrado explicitamente, sem forçar
correlação.

Contraste relevante: no oficial as rodadas r1-r3 foram as *ruins* (326/1022/874 ms), e são as que
foram replicadas na mesma ordem e no mesmo dia. O cenário foi reproduzido; o defeito, não.

Observação contra-hipótese: a r4 tem a **maior** pressão de GC do conjunto (729,7 pausas/min, 5,09%
do tempo em GC) e o **segundo menor** p95. Entre rodadas, mais GC não produziu pior cauda.

### Distribuição de pausas do Spring Boot (5 rodadas, n=81.198 pausas)

| percentil | pausa |
|---|---|
| p50 | 4,13 ms |
| p95 | 6,41 ms |
| p99 | 7,35 ms |
| p99,9 | 8,68 ms |
| p99,99 | 22,16 ms |
| máx | 503,90 ms |

Acima de limiares: **> 10 ms: 25 pausas** (0,031%); > 100 ms: 6; > 500 ms: 1; **> 1000 ms: nenhuma**.
Soma total parado: 335,3 s em ~7.500 s de carga.

81.184 das 81.198 pausas são `ParallelGCFailedAllocation` (coleta jovem por falha de alocação),
coerente com `MaxHeapFreeRatio=20` + `GCTimeRatio=4` que a imagem UBI injeta e que mantêm o heap
pequeno. A 2ª maior pausa (196,7 ms, r1) é `CollectForMetadataAllocation` — carregamento de classes,
não pressão de heap.

### Tarefa 2: coincidência temporal vs magnitude

**A coincidência temporal, no Spring Boot, é vácua por taxa-base.** Com ~600 pausas/min (10 por
segundo), **99,3% de todos os segundos de carga contêm alguma pausa**. Os 20, 100 e 500 piores
segundos de latência contêm pausa em 100% dos casos — **lift de 1,01×**. Ou seja, "os picos coincidem
com pausas de GC" é verdade e não informa nada: é garantido por construção.

| | taxa-base | 20 piores segundos | lift |
|---|---|---|---|
| sb | 99,3% | 100,0% | **1,01×** |
| qj | 66,1% | 95,0% | 1,44× |

**A magnitude é o teste que discrimina, e ele falha.** Nos 20 segundos de pior latência do
Spring Boot (latência máxima média de 771 ms), a maior pausa daquele segundo vale em média **34,5 ms
= 4,5%** da latência; a soma de todas as pausas do segundo vale 95,7 ms = 12,4%. No pior caso
absoluto, a maior pausa observada (503,9 ms) é **23%** da maior latência observada (2191,9 ms).
A sobreposição entre os 20 piores segundos de latência e os 20 segundos de maior pausa é de 8/20.

**O controle do Quarkus fornece o caso limite decisivo:** a qj-r2 teve latência máxima de **835 ms**
com pausa máxima de **5,4 ms** em toda a rodada. Um evento de cauda de quase 1 segundo ocorreu com
GC praticamente ausente (0,146% do tempo). Isso demonstra que, neste ambiente, a cauda não precisa de
GC para acontecer.

Nota sobre a comparação ingênua: "latência máxima de 130 ms em segundos com pausa longa vs 25,6 ms em
segundos sem pausa" (em `correlacao.csv`) é enganosa para o Spring Boot, porque os segundos "sem
pausa" são apenas 0,7% do total e são segundos de tráfego baixo. O `r` de Pearson de 0,38 (sb) contra
0,29 (qj) tem a mesma ordem de grandeza apesar de pausas **87× menores** no Quarkus — compatível com
pausas e latência respondendo a um terceiro fator comum (rajadas de alocação e de carga no mesmo
instante), não com a pausa causando a latência.

### Tarefa 4: controle do Quarkus JVM

| | pausas/min | pausa média | pausa máx | tempo em GC |
|---|---|---|---|---|
| Spring Boot (média r1-r5) | 640 | 4,13 ms | 503,9 ms | 4,40% |
| **Quarkus JVM** (r1-r2) | **45** | **1,93 ms** | **5,78 ms** | **0,145%** |

O Quarkus JVM faz **14× menos pausas**, gasta **30× menos tempo** em GC, e sua pausa **máxima**
(5,78 ms) é menor que o **p95 das pausas** do Spring Boot (6,41 ms). O padrão de pausas
longas/frequentes do Spring Boot não se replica no controle.

## Limitações desta execução

- Resolução do CSV do k6 é de **1 segundo**: a correlação é por bucket de 1 s, não por requisição
  individual. Mesma limitação encontrada no `gc_f1` a 240 req/s.
- Postgres local truncado por rodada usa menos CPU que o RDS oficial (14% da cota vs 58-62%);
  divergência deliberada, para o banco não ser o gargalo.
- Host compartilhado: Firefox consumindo ~50% de CPU agregada durante todo o bloco, adicionando
  ruído de escalonamento (a cota do app é isolada; a latência de escalonamento não é).
- 2 repetições no controle do Quarkus, não 5.
- O `gc.stream.qj.log` tem duplicação exata de 2× (dois watchers sobrepostos); o `slice_gc.py`
  deduplica por linha e os slices primários vêm do contêiner, então não afeta resultado.

## Reprodução

```
./run_all.sh sb 5     # 5 rodadas Spring Boot, ~2h20
./run_all.sh qj 2     # 2 rodadas Quarkus JVM, ~55 min
python3 slice_gc.py   # refatia gc.log por timestamp (redundância)
python3 analyze.py    # p95/pausas por rodada + correlação por segundo
python3 correlacao_taxabase.py   # teste de taxa-base e de magnitude
```
