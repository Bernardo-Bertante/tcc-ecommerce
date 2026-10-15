# Investigação exploratória: o gap Spring Boot vs Quarkus JVM muda se a JVM puder chegar a C2?

Exploratório, 16/09/2026. **Não é resultado formal do TCC** (N pequeno, ambiente local). Continua
`../exploratorio_cpu_lambda/RESULTADOS.md` (cliente HTTP do SDK como causa do gap).

## Resposta direta

**Não. O gap praticamente não muda.** Com as duas JVMs podendo chegar a C2, as duas versões ficam cerca de 1 ms
mais rápidas. A diferença absoluta Quarkus JVM − Spring Boot continua igual (**+3,67 ms com teto C1 → +3,64 ms
sem teto**). A diferença relativa até sobe um pouco (+38,0% → +41,9%), só porque o denominador (SB) diminuiu.
Isso reforça a leitura de que o gap vem do custo do cliente HTTP por chamada ao DynamoDB (I/O e o tempo do
cliente entre chamadas), e não do nível de compilação.

## Setup

- Código: `order-processor` original de cada versão (SB com `ApacheHttpClient`, QJ com `UrlConnectionHttpClient`),
  sem as variantes do teste de cliente HTTP. As imagens (`build/Dockerfile`, `c2exp-proc-{sb,qj}`) foram montadas a
  partir dos zips **baixados das funções publicadas** (`aws lambda get-function`, conta pessoal). O sha256 bate com o
  `CodeSha256` publicado: SB `ODLvR0a1…bbg=`, QJ `qqGaGUSy…WME=`.
  - Observação: os zips locais em `order-processor/*/build` **não** têm o mesmo sha256 dos publicados. No QJ o
    conteúdo é idêntico. No SB, só o jar da aplicação difere, e só em metadados: nenhuma entrada interna muda. As
    imagens `cpuexp-proc-*` do teste anterior são, portanto, equivalentes em bytecode, mas não em sha256.
- Runtime: `public.ecr.aws/lambda/java:21` (Corretto 21.0.12) + RIE, `AWS_LAMBDA_FUNCTION_MEMORY_SIZE=512`
  (heap 445 MB), SerialGC.
- Mesma topologia do teste anterior: DynamoDB Local pinado em 8,10; função em 2,4 (`-XX:ActiveProcessorCount=2`,
  `-m 512m`); k6 em 6,7; dockerd nativo. As tabelas são recriadas antes de cada execução.
- Carga: `processOrder` com o payload do L2, 20 rps, 1 VU serial, **480 s (~9.600 invocações)**, com um ambiente
  novo por execução. A janela principal considera só **seq > 5.500** (4.100 invocações).
- 3 rodadas × {SB, QJ} × {C1, C2}, ordem contrabalanceada (`run_all.sh`). 12/12 execuções, 0 checks falhos.
  A execução r1-sb-c1 teve 9.567 invocações; as demais, 9.600-9.601.
- Scripts: `run_one.sh`, `run_all.sh`, `analyze.py` → `analise.txt`, `por_execucao.csv`, `curva_aquecimento.csv`.

## Tarefa 1 — a flag é respeitada? (`flagcheck/`)

`jcmd <pid> VM.flags -all` / `VM.command_line` com 4 valores de `JAVA_TOOL_OPTIONS`:

| `JAVA_TOOL_OPTIONS` | `TieredStopAtLevel` efetivo | Origem |
|---|---|---|
| `-XX:ActiveProcessorCount=2` (default) | 1 | `{command line}` (bootstrap) |
| `… -XX:+UseSerialGC -XX:TieredStopAtLevel=4` | **1 — ignorado** | `{command line}` (bootstrap) |
| `… -XX:+UseSerialGC -XX:+TieredCompilation` | 4 | `{default}` |
| `… -XX:+UseSerialGC -XX:+TieredCompilation -XX:TieredStopAtLevel=4` | 4 | `{environment}` |

**`-XX:TieredStopAtLevel=4` sozinho em `JAVA_TOOL_OPTIONS` é ignorado sem aviso.** O bootstrap (`/var/runtime/bootstrap`,
binário) acrescenta `-XX:+TieredCompilation -XX:TieredStopAtLevel=1` à linha de comando, que tem precedência sobre
`JAVA_TOOL_OPTIONS`. Ele só deixa de acrescentar quando `JAVA_TOOL_OPTIONS` contém `-XX:+TieredCompilation` ou
`-XX:-TieredCompilation`. Por isso, a condição C2 usou a 4ª linha. As flags efetivas de cada execução estão em
`results/*.flags` e confirmam `TieredStopAtLevel = 1` em todas as execuções C1 e `= 4` em todas as C2.

## Por execução (janela seq > 5.500; ms)

| Rodada | Versão | Cond. | Mediana | p90 | p99 | CPU/inv | Métodos nível 4 | Métodos nível 1-3 | Tempo JIT total (s) | Frio (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SB | C1 | 9,66 | 11,87 | 12,93 | 5,53 | 0 | 6725 | 1,90 | 1,54 |
| 2 | SB | C1 | 9,64 | 11,79 | 12,63 | 5,58 | 0 | 6755 | 1,66 | 1,31 |
| 3 | SB | C1 | 9,69 | 11,87 | 12,83 | 5,61 | 0 | 6714 | 1,71 | 1,33 |
| 1 | SB | C2 | 8,76 | 10,70 | 11,67 | 6,09 | 1783 | 6313 | 14,08 | 1,67 |
| 2 | SB | C2 | 8,64 | 10,57 | 11,42 | 6,02 | 1794 | 6401 | 13,12 | 1,72 |
| 3 | SB | C2 | 8,65 | 10,56 | 11,56 | 5,98 | 1786 | 6472 | 13,77 | 1,69 |
| 1 | QJ | C1 | 13,30 | 16,84 | 18,11 | 5,72 | 0 | 5165 | 1,38 | 1,10 |
| 2 | QJ | C1 | 13,36 | 16,81 | 18,05 | 5,73 | 0 | 5132 | 1,37 | 0,84 |
| 3 | QJ | C1 | 13,34 | 16,89 | 18,02 | 5,69 | 0 | 5116 | 1,29 | 0,85 |
| 1 | QJ | C2 | 12,26 | 15,71 | 17,00 | 5,94 | 1465 | 4847 | 11,29 | 1,06 |
| 2 | QJ | C2 | 12,30 | 15,79 | 17,09 | 5,96 | 1477 | 4866 | 11,13 | 1,00 |
| 3 | QJ | C2 | 12,41 | 15,82 | 17,00 | 5,99 | 1470 | 4880 | 11,44 | 1,03 |

- "CPU/inv": `usage_usec` do cgroup da função durante toda a carga (inclui threads do compilador) ÷ invocações.
  É a mesma métrica do teste anterior.
- "Métodos nível 4": linhas com nível 4 em `jcmd Compiler.codelist` ao final. **0 em todas as C1 e 1.465-1.794 em
  todas as C2**, então C2 foi de fato alcançado e a comparação vale.
- "Tempo JIT total": `java.ci.totalTime` (compilação C1 + C2 durante a vida da JVM).
- O C2 começa bem antes de 5.000 invocações do handler (868 métodos nível 4 no smoke de 45 s ≈ 900 invocações),
  porque `Tier4InvocationThreshold` conta chamadas **por método**, e métodos internos são chamados muitas vezes por
  invocação. A janela seq > 5.500 continua sendo "além do limiar" em qualquer leitura.

Dispersão entre rodadas ≤ 0,15 ms na mediana em todas as células. Isso é bem menor que os efeitos abaixo.

## Tarefa 3 — C1 vs C2 por versão (média das 3 rodadas, seq > 5.500)

| Versão | Mediana C1 → C2 | p90 C1 → C2 | CPU/inv C1 → C2 |
|---|---|---|---|
| Spring Boot | 9,66 → 8,68 (**−10,1%**, −0,98 ms) | 11,84 → 10,61 (−10,4%) | 5,58 → 6,03 (+8,1%) |
| Quarkus JVM | 13,33 → 12,32 (**−7,6%**, −1,01 ms) | 16,85 → 15,77 (−6,4%) | 5,71 → 5,96 (+4,4%) |

As duas versões ficam mais rápidas com C2, e em **quantidade absoluta praticamente igual (~1 ms)**.

## Tarefa 4 — gap QJ vs SB nas duas condições (pergunta central)

| Condição | SB mediana | QJ mediana | Gap absoluto | Gap relativo | Por rodada | Gap p90 | Gap CPU/inv |
|---|---|---|---|---|---|---|---|
| C1 (Lambda real) | 9,66 | 13,33 | **+3,67 ms** | +38,0% | +37,6 / +38,6 / +37,7% | +42,3% | +2,5% |
| C2 (sem teto) | 8,68 | 12,32 | **+3,64 ms** | +41,9% | +40,0 / +42,5 / +43,4% | +48,7% | −1,1% |

O gap absoluto é o mesmo (diferença de 0,03 ms, dentro da dispersão entre rodadas). Nenhuma rodada C2 teve gap
relativo menor que qualquer rodada C1. O que o C2 acelera é uma parcela comum às duas versões, de ~1 ms/invocação:
serialização, SDK e lógica. Os ~3,6 ms extras do `UrlConnectionHttpClient` não respondem ao nível de compilação.
Isso é consistente com o diagnóstico anterior, em que a maior parte do gap estava no tempo entre receber a resposta
e enviar a próxima requisição, e não em CPU de código "frio". **A hipótese I/O/cliente HTTP fica mais forte.**

Aqui o gap local é +38%, não os ~17% do Lambda real. O absoluto (~3,6 ms) é próximo dos ~3,2 ms do Lambda. Esta
sessão teve latências absolutas mais altas que a de 13/09 (SB 9,66 vs 6,64 ms; QJ 13,33 vs 9,79 ms), com gap
absoluto semelhante (3,67 vs 3,15 ms). Por isso, só vale comparar dentro da mesma sessão.

## Tarefa 5 — efeitos colaterais do C2

- **Pior no início.** Nas primeiras 1.000 invocações, a mediana fica maior com C2: SB 11,10 → 11,77 ms (+6,1%),
  QJ 14,30 → 14,87 ms (+4,0%), consistente nas 3 rodadas das duas versões. Mediana por bloco de 500 invocações
  (média das rodadas; `curva_aquecimento.csv`):

  | Bloco (seq) | 0 | 500 | 1000 | 1500 | 2000 | 3000 | 5500 | 7000 | 9000 |
  |---|---|---|---|---|---|---|---|---|---|
  | SB C1 | 12,3 | 10,1 | 9,6 | 9,5 | 9,5 | 9,6 | 9,7 | 9,7 | 9,7 |
  | SB C2 | 12,9 | 10,9 | 9,5 | 9,3 | 9,2 | 9,0 | 8,7 | 8,8 | 8,4 |
  | QJ C1 | 15,4 | 13,5 | 13,1 | 13,3 | 13,2 | 13,3 | 13,3 | 13,4 | 13,3 |
  | QJ C2 | 15,9 | 14,0 | 13,1 | 13,0 | 12,8 | 12,8 | 12,4 | 12,2 | 12,1 |

  O C2 só passa a ganhar a partir de ~1.000 invocações e **ainda estava melhorando no fim** (~9.600 invocações). Não
  houve platô claro, então o ganho de longo prazo pode ser um pouco maior que 1 ms. Mesmo assim, a diferença entre
  as curvas SB e QJ fica em ~3,6-3,7 ms em todos os blocos.
- **Mais CPU por invocação.** A CPU por invocação sobe +8,1% (SB) e +4,4% (QJ), mesmo com latência menor. O tempo
  total de JIT vai de ~1,3-1,9 s para ~11-14 s. Num Lambda de 512 MB (~0,29 vCPU), essas threads competiriam com o
  handler. Esse efeito não foi testado aqui (CPU livre em 2 núcleos).
- **Frio.** A invocação fria foi um pouco mais lenta com C2: SB 1,40 → 1,69 s, QJ 0,93 → 1,03 s (1 amostra por
  execução).

## Limitações

- DynamoDB Local ≠ DynamoDB real, e RIE ≠ serviço Lambda (ver o teste anterior).
- CPU livre (2 núcleos). O Lambda de 512 MB tem uma fração de vCPU. Lá, o custo de compilação do C2 teria mais peso
  e o ganho em regime poderia demorar mais ou ser menor. A pergunta central (o gap muda?) não depende disso, mas o
  ganho absoluto de ~1 ms não deve ser transposto para o Lambda.
- Um ambiente persistente por execução, sem a fragmentação entre ambientes do Lambda real.
- A contagem de métodos nível 4 é um snapshot final do code cache.
