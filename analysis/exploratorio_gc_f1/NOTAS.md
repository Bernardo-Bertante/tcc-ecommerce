# Exploratório: GC explica o QJ < QN do F1? (13/09/2026)

**Não é resultado formal do TCC.** Sinal direcional para a pendência de §6.3.

## Setup
- Imagens exatas do F1 (ECR `20260616-160138`: jvm `abec3583`, native `650b4e42`), sem rebuild.
- Container 1 CPU dedicada (`--cpuset-cpus=3`, sem cota) + 2 GB = ergonomia da task Fargate 1024/2048.
  Pool reativo 40 (igual à task). Postgres 16 local (cores 10-11), k6 local (cores 12-15).
- Coletores efetivos (iguais aos do Fargate, pois dependem só de CPU/memória + imagem):
  - QJ: **ParallelGC** (injetado por `java-default-options` da imagem UBI), MaxRAMPercentage=80 → heap máx 1640 MB,
    `MaxHeapFreeRatio=20` mantém heap pequeno (~28 MB) → coletas jovens frequentes e baratas.
  - QN: **Serial GC**, heap máx 1638 MB, geração jovem até 546 MB, alterna Incremental/Full.
- `f1_low_load.js` (mesmo mix), 48 e 240 iter/s; rampa 60 s + hold 540 s; janela = hold após 120 s. 3 rodadas × 2 × 2,
  ordem intercalada (`run_all.sh`). GC: `-Xlog:gc*,safepoint` (QJ) / `-XX:+PrintGC +VerboseGC +PrintGCTimes` (QN).
  CPU: `cpu.stat` do cgroup a cada 5 s.

## Resultados (médias das 3 rodadas; `gc_resumo.csv`, `gc_por_rodada.csv`)

| | QJ 48 | QN 48 | QJ 240 | QN 240 |
|---|---|---|---|---|
| Latência mediana (ms) | 2,07 | 2,44 | 1,28 | 1,67 |
| Pausas GC/min | 13,5 | 4,3 | 89 | 238 |
| Full GC na janela | 0 | 2,7 | 0 | 96 |
| Pausa média / máx (ms) | 1,6 / 2,4 | 2,6 / 12,6 | 1,7 / 5,8 | 2,5 / 29 |
| Fração do tempo em GC | 0,036% | **0,019%** | 0,25% | **1,0%** |
| vCPU média | 0,051 | 0,063 | 0,088 | 0,147 |
| CPU ms/requisição | 1,06 | 1,31 | 0,37 | 0,62 |
| GC como % da CPU | 0,7% | 0,3% | 2,8% | 6,8% |

Latência agregada: 48 → QN/QJ mediana 1,19, Cliff(QJ,QN) = −0,124; 240 → QN/QJ 1,27, Cliff = −0,079.

Por endpoint (`mediana_por_endpoint.csv`): o atraso do QN é **aditivo e concentrado nos endpoints leves**
(get_order +0,31/+0,16 ms; get_orders_by_customer +0,33/+0,32 ms em 48/240); endpoints dominados por banco
(get_summary, create_order a 240, update_status a 240) empatam ou QN fica à frente.

Atribuição temporal a 48 iter/s (`latencia_vs_segundos_com_gc.csv`): só ~7% das requisições do QN caem num
segundo com pausa (22% no QJ); nesses segundos a mediana sobe só +0,2–0,4 ms. A 240, todo segundo tem pausa
(resolução de 1 s do k6 não separa).

## Leitura
1. **Na taxa baixa, o QN NÃO gasta mais tempo em GC** — gasta metade do QJ (0,019% vs 0,036%). Pausas menos
   frequentes, mais longas (Full GC ~11 ms), mas raras. GC não explica +0,4 ms de mediana. Contra a hipótese.
2. **Na taxa alta, a diferença de GC aumenta (e inverte)**: QN 1% do tempo, 96 Full GCs, 6,8% da CPU. Se GC
   fosse a causa, o efeito de latência cresceria com a taxa — o oposto do padrão do Fargate. Contra a hipótese.
3. **O efeito de latência reproduz localmente, nas duas taxas** (QN ~+0,4 ms de mediana, Cliff pequeno/desprezível).
   Não é específico da AWS. O que é constante nas duas taxas é o **custo de CPU por requisição** do QN
   (+24% a 48, +67% a 240) — compatível com código AOT sem JIT/PGO sendo mais lento no caminho quente,
   não com GC. A CPU extra do QN no Fargate (44 vs 64 etc.) também aparece aqui e é majoritariamente não-GC.
4. Por que "só F1": nos dados oficiais o QJ também é mais rápido em F2/F3, só que com efeito menor
   (Cliff F2 −0,100, F3 −0,134, abaixo do limiar 0,147 de "pequeno"; medianas +3,5% e +7,8% vs +21% no F1).
   Hipótese mais simples: um custo aditivo ~constante por requisição (sub-ms) pesa proporcionalmente mais quando
   a latência total é baixa (F1, mediana 3,9 ms) e se dilui quando a espera por banco/rede cresce (F2 6,1 ms,
   F3 7,0 ms). É diferença de grau, não de natureza.

## Limitações
Postgres local (sem rede/TLS/t3.micro), k6 na mesma máquina, notebook com governor `powersave`,
N=3 por condição, k6 com timestamp de 1 s (sem atribuição fina pausa→requisição a 240).
