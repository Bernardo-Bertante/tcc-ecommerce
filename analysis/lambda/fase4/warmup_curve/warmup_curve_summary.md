# Seção 6.5 — Curva de aquecimento por ambiente de execução (Lambda L2/L3)

Fonte: linhas REPORT do CloudWatch Logs (retenção infinita, conta 776648109551,
`--profile pessoal`), cenários L2 e L3, runtimes Spring Boot e Quarkus JVM,
5 rodadas (05–06/jul e 16/jul/2026). Nº de sequência = ordem de invocação
dentro do próprio `@logStream` (ambiente de execução), acumulada L2→L3
(L3 reaproveita os ambientes já aquecidos por L2). Nada foi reexecutado;
CSVs oficiais preservados.

## Cobertura de extração (REPORT vs. esperado k6)

| runtime | rodada | cenário | REPORT | esperado | % |
|---|---|---|---|---|---|
| springboot | 1 | L2 | 20513 | 20354 | 100.8% |
| springboot | 1 | L3 | 27600 | 27759 | 99.4% |
| springboot | 2 | L2 | 20511 | 20350 | 100.8% |
| springboot | 2 | L3 | 27513 | 27674 | 99.4% |
| springboot | 3 | L2 | 20509 | 20352 | 100.8% |
| springboot | 3 | L3 | 27566 | 27723 | 99.4% |
| springboot | 4 | L2 | 20746 | 20353 | 101.9% |
| springboot | 4 | L3 | 27300 | 27693 | 98.6% |
| springboot | 5 | L2 | 20356 | 20356 | 100.0% |
| springboot | 5 | L3 | 27444 | 27701 | 99.1% |
| quarkus-jvm | 1 | L2 | 20498 | 20343 | 100.8% |
| quarkus-jvm | 1 | L3 | 27548 | 27703 | 99.4% |
| quarkus-jvm | 2 | L2 | 20507 | 20345 | 100.8% |
| quarkus-jvm | 2 | L3 | 27534 | 27696 | 99.4% |
| quarkus-jvm | 3 | L2 | 20492 | 20341 | 100.7% |
| quarkus-jvm | 3 | L3 | 27563 | 27714 | 99.5% |
| quarkus-jvm | 4 | L2 | 20339 | 20339 | 100.0% |
| quarkus-jvm | 4 | L3 | 27699 | 27705 | 100.0% |
| quarkus-jvm | 5 | L2 | 20471 | 20342 | 100.6% |
| quarkus-jvm | 5 | L3 | 27550 | 27679 | 99.5% |

## Tabela 1 — duration por faixa de sequência (agregado das 5 rodadas)

| cenário | faixa seq. | runtime | N obs | % das req. | dur. média (ms) | dur. mediana (ms) | p90 (ms) |
|---|---|---|---|---|---|---|---|
| L2 | 1 | springboot | 246 | 0.2% | 2672.5 | 2664.0 | 2822.7 |
| L2 | 1 | quarkus-jvm | 253 | 0.2% | 5538.0 | 5522.1 | 5789.8 |
| L2 | 2-10 | springboot | 650 | 0.6% | 80.1 | 79.6 | 113.3 |
| L2 | 2-10 | quarkus-jvm | 661 | 0.6% | 73.5 | 72.2 | 105.9 |
| L2 | 11-100 | springboot | 2419 | 2.4% | 38.6 | 33.1 | 67.8 |
| L2 | 11-100 | quarkus-jvm | 2557 | 2.5% | 39.6 | 32.6 | 72.7 |
| L2 | 101-1000 | springboot | 18242 | 17.8% | 22.4 | 19.7 | 29.8 |
| L2 | 101-1000 | quarkus-jvm | 22605 | 22.1% | 24.2 | 22.1 | 32.2 |
| L2 | 1001-5000 | springboot | 46222 | 45.0% | 17.6 | 16.9 | 23.3 |
| L2 | 1001-5000 | quarkus-jvm | 59593 | 58.2% | 21.1 | 20.4 | 28.2 |
| L2 | 5001+ | springboot | 34856 | 34.0% | 17.0 | 16.3 | 22.1 |
| L2 | 5001+ | quarkus-jvm | 16638 | 16.3% | 20.4 | 19.8 | 27.3 |
| | | | | | | | |
| L3 | 1 | springboot | 109 | 0.1% | 2662.1 | 2653.9 | 2796.7 |
| L3 | 1 | quarkus-jvm | 118 | 0.1% | 5528.7 | 5528.3 | 5774.8 |
| L3 | 2-10 | springboot | 569 | 0.4% | 80.8 | 80.0 | 111.8 |
| L3 | 2-10 | quarkus-jvm | 610 | 0.4% | 76.3 | 74.3 | 109.5 |
| L3 | 11-100 | springboot | 2897 | 2.1% | 41.5 | 36.6 | 70.6 |
| L3 | 11-100 | quarkus-jvm | 3235 | 2.3% | 43.0 | 35.2 | 78.4 |
| L3 | 101-1000 | springboot | 23809 | 17.3% | 22.3 | 19.8 | 29.8 |
| L3 | 101-1000 | quarkus-jvm | 25664 | 18.6% | 24.3 | 22.5 | 31.7 |
| L3 | 1001-5000 | springboot | 86132 | 62.7% | 17.5 | 16.9 | 23.5 |
| L3 | 1001-5000 | quarkus-jvm | 94226 | 68.3% | 21.2 | 20.6 | 28.3 |
| L3 | 5001+ | springboot | 23907 | 17.4% | 17.2 | 16.5 | 23.1 |
| L3 | 5001+ | quarkus-jvm | 14041 | 10.2% | 21.1 | 20.6 | 28.3 |
| | | | | | | | |
| L2+L3 | 1 | springboot | 355 | 0.1% | 2669.3 | 2661.0 | 2812.7 |
| L2+L3 | 1 | quarkus-jvm | 371 | 0.2% | 5535.1 | 5524.3 | 5784.7 |
| L2+L3 | 2-10 | springboot | 1219 | 0.5% | 80.5 | 79.7 | 112.5 |
| L2+L3 | 2-10 | quarkus-jvm | 1271 | 0.5% | 74.8 | 73.2 | 108.3 |
| L2+L3 | 11-100 | springboot | 5316 | 2.2% | 40.1 | 35.0 | 69.4 |
| L2+L3 | 11-100 | quarkus-jvm | 5792 | 2.4% | 41.5 | 34.0 | 75.8 |
| L2+L3 | 101-1000 | springboot | 42051 | 17.5% | 22.3 | 19.7 | 29.8 |
| L2+L3 | 101-1000 | quarkus-jvm | 48269 | 20.1% | 24.3 | 22.3 | 31.9 |
| L2+L3 | 1001-5000 | springboot | 132354 | 55.1% | 17.6 | 16.9 | 23.4 |
| L2+L3 | 1001-5000 | quarkus-jvm | 153819 | 64.0% | 21.2 | 20.5 | 28.3 |
| L2+L3 | 5001+ | springboot | 58763 | 24.5% | 17.1 | 16.4 | 22.6 |
| L2+L3 | 5001+ | quarkus-jvm | 30679 | 12.8% | 20.7 | 20.1 | 27.8 |
| | | | | | | | |

## Tabela 2 — fração das requisições por faixa de sequência (por rodada)

Combinado L2+L3. Cada célula = % das requisições daquela rodada/runtime cujo
ambiente já tinha acumulado N invocações naquele ponto.

| runtime | rodada | seq=1 | 2-10 | 11-100 | 101-1k | 1k-5k | 5k+ | <100 (soma) |
|---|---|---|---|---|---|---|---|---|
| springboot | 1 | 0.1% | 0.5% | 2.6% | 15.8% | 50.3% | 30.7% | **3.2%** |
| springboot | 2 | 0.2% | 0.6% | 1.9% | 15.0% | 53.8% | 28.5% | **2.7%** |
| springboot | 3 | 0.1% | 0.4% | 1.9% | 14.9% | 53.4% | 29.3% | **2.4%** |
| springboot | 4 | 0.1% | 0.5% | 1.9% | 16.9% | 57.3% | 23.3% | **2.6%** |
| springboot | 5 | 0.1% | 0.5% | 2.8% | 25.1% | 60.9% | 10.6% | **3.4%** |
| quarkus-jvm | 1 | 0.2% | 0.6% | 2.6% | 20.7% | 61.8% | 14.1% | **3.4%** |
| quarkus-jvm | 2 | 0.2% | 0.6% | 2.4% | 19.4% | 62.5% | 15.0% | **3.1%** |
| quarkus-jvm | 3 | 0.1% | 0.5% | 2.4% | 21.2% | 67.5% | 8.2% | **3.1%** |
| quarkus-jvm | 4 | 0.1% | 0.5% | 2.1% | 18.3% | 63.8% | 15.1% | **2.7%** |
| quarkus-jvm | 5 | 0.2% | 0.6% | 2.4% | 20.8% | 64.6% | 11.4% | **3.2%** |

## Tabela 3 — fração em ambiente pouco aquecido, só cenário L2

| runtime | rodada | % req. em env <100 inv | % req. em env <1000 inv |
|---|---|---|---|
| springboot | 1 | 4.2% | 21.6% |
| springboot | 2 | 2.1% | 15.3% |
| springboot | 3 | 3.0% | 19.2% |
| springboot | 4 | 2.6% | 20.0% |
| springboot | 5 | 4.1% | 28.9% |
| springboot | **média** | **3.2%** | **21.0%** |
| quarkus-jvm | 1 | 3.5% | 29.9% |
| quarkus-jvm | 2 | 3.0% | 23.2% |
| quarkus-jvm | 3 | 3.6% | 25.3% |
| quarkus-jvm | 4 | 3.6% | 23.9% |
| quarkus-jvm | 5 | 3.0% | 25.0% |
| quarkus-jvm | **média** | **3.4%** | **25.5%** |

## Tabela 4 — duration em ambientes muito aquecidos (gap persistente?)

Mediana de duration por faixa alta de sequência, agregado 5 rodadas, L2+L3.

| faixa seq. | SB mediana | Quarkus JVM mediana | gap (QJ−SB) | gap % |
|---|---|---|---|---|
| 101-1000 | 19.7 | 22.3 | +2.6 ms | +13.2% |
| 1001-5000 | 16.9 | 20.5 | +3.6 ms | +21.1% |
| 5001+ | 16.4 | 20.1 | +3.7 ms | +22.8% |

## Tabela 5 — curva fina duration mediana vs. nº de sequência (L2+L3, agregado)

| seq (>=) | SB N | SB mediana | SB p90 | QJ N | QJ mediana | QJ p90 |
|---|---|---|---|---|---|---|
| 1 | 355 | 2661.0 | 2812.7 | 371 | 5524.3 | 5784.7 |
| 2 | 233 | 90.0 | 123.7 | 249 | 79.5 | 111.4 |
| 3 | 346 | 86.6 | 112.4 | 361 | 75.5 | 107.2 |
| 5 | 553 | 74.1 | 107.3 | 567 | 71.3 | 107.2 |
| 10 | 759 | 54.1 | 82.5 | 813 | 68.3 | 107.0 |
| 20 | 1832 | 39.6 | 72.6 | 1991 | 37.5 | 72.4 |
| 50 | 2759 | 29.1 | 56.8 | 3023 | 29.0 | 54.9 |
| 100 | 5113 | 23.8 | 41.8 | 5775 | 25.1 | 39.4 |
| 200 | 14338 | 21.1 | 30.5 | 16695 | 23.3 | 32.7 |
| 500 | 22609 | 18.1 | 26.0 | 25808 | 21.1 | 29.3 |
| 1000 | 40975 | 17.1 | 23.6 | 47654 | 20.5 | 28.2 |
| 2000 | 91405 | 16.9 | 23.3 | 106194 | 20.5 | 28.3 |
| 5000 | 40657 | 16.4 | 22.6 | 30700 | 20.1 | 27.8 |
| 10000 | 18124 | 16.2 | 22.6 | 0 | — | — |

## Tabela 6 — decomposição do gap: composição (aquecimento) vs. taxa (intrínseco)

Padronização direta: reponderando as invocações QUENTES (seq>1) do Quarkus JVM
pela distribuição de nº de sequência do Spring Boot (bins log finos), isola-se
quanto do gap vem da MISTURA de aquecimento (composição) e quanto vem da
diferença de duration DENTRO de cada faixa (taxa / eficiência intrínseca).

| cenário | mean SB | mean QJ | gap mean | median SB | median QJ | gap median | gap QUENTE bruto | efeito composição | **gap intrínseco (taxa)** |
|---|---|---|---|---|---|---|---|---|---|
| L2 | 25.5 | 36.1 | +10.6 | 17.3 | 20.8 | +3.5 | +3.36 ms | +0.47 ms | **+2.89 ms (+15.1%)** |
| L3 | 21.2 | 27.3 | +6.1 | 17.4 | 21.1 | +3.7 | +3.50 ms | +0.12 ms | **+3.38 ms (+17.7%)** |
| L2+L3 | 23.0 | 31.0 | +8.0 | 17.4 | 21.0 | +3.6 | +3.44 ms | +0.21 ms | **+3.23 ms (+16.9%)** |

## Tabela 7 — ambiente mais aquecido de cada rodada (L2+L3)

`max_seq` = invocações acumuladas pelo @logStream mais ativo. `tail-2k` =
mediana de duration nas últimas 2000 invocações desse ambiente (estado mais
quente efetivamente atingido na rodada).

| runtime | rodada | nº ambientes | max_seq | tail-2k mediana (ms) |
|---|---|---|---|---|
| springboot | 1 | 66 | 16264 | 15.8 |
| springboot | 2 | 89 | 15095 | 16.1 |
| springboot | 3 | 63 | 14699 | 16.4 |
| springboot | 4 | 67 | 12014 | 17.2 |
| springboot | 5 | 70 | 10047 | 16.3 |
| quarkus-jvm | 1 | 78 | 7992 | 21.1 |
| quarkus-jvm | 2 | 76 | 9103 | 19.2 |
| quarkus-jvm | 3 | 72 | 7230 | 20.1 |
| quarkus-jvm | 4 | 66 | 9438 | 19.2 |
| quarkus-jvm | 5 | 79 | 8894 | 21.4 |

## Respostas

**1. A curva do Quarkus JVM converge para o Spring Boot conforme o ambiente
esquenta?** Não. Ambos os runtimes atingem um platô: Spring Boot em ~16,4 ms
por volta de seq≈1000, Quarkus JVM em ~20,5 ms por volta de seq≈700. Desse
ponto em diante o gap (~3,5 ms, ~20 %) é estável — não diminui em ambientes
com 5.000+ invocações (Tabela 4: gap de +3,7 ms / +23 % na faixa 5001+, 
igual ou maior que na faixa 101-1000). O ambiente mais quente do Spring Boot
chega a 10-16 mil invocações e continua em ~16 ms; o do Quarkus JVM não passa
de ~9,5 mil e está plano em ~20 ms desde seq≈1000. Nada indica convergência
se o Quarkus JVM recebesse mais tráfego. (Curiosidade: em seq 2-30 o Quarkus
JVM é *mais rápido* que o Spring Boot; o Spring Boot ultrapassa por volta de
seq≈40 e abre o gap definitivo até o platô.)

**2. A fração de requisições em ambiente pouco aquecido é maior no Quarkus JVM?**
Só marginalmente, e não onde importa. Em env com <100 invocações as duas
versões são praticamente iguais (L2: SB 3,2 % vs QJ 3,4 %). Em env com <1000
invocações o Quarkus JVM é moderadamente maior (L2: 21,0 % vs 25,5 %). A
diferença real de distribuição é outra: o Spring Boot CONCENTRA tráfego em
poucos ambientes ultra-quentes (10-31 % das req. em seq 5000+), o Quarkus JVM
espalha por ambientes medianamente quentes (8-15 % em seq 5000+). Mas como
ambos já estão no platô desde seq≈1000, essa assimetria de concentração
explica quase nada do gap: a padronização (Tabela 6) atribui apenas ~0,2 ms
de ~3,4 ms de gap quente ao efeito de composição; ~3,2 ms (~17 %) é diferença
intrínseca de duration por invocação, dentro da mesma faixa de aquecimento.

**Conclusão para a §6.5:** a inversão de ranking em L2/L3 em regime aquecido
**não** é primariamente um artefato de aquecimento/distribuição de tráfego.
Dentro de um mesmo ambiente de execução bem aquecido, a execução por
invocação do Quarkus JVM é intrinsecamente ~17 % (~3,2 ms) mais lenta que a
do Spring Boot, e esse gap é estável de ~1000 invocações em diante. A
assimetria de concentração de tráfego notada na investigação anterior
(min/mediana/máx) é real, mas contribui de forma desprezível para a diferença
de mediana / média-quente. Ela infla a diferença de **média** via cold starts
(execução de cold start do Quarkus JVM ~5,5 s vs ~2,7 s do Spring Boot), o
que pesa em agregados baseados em média, não em mediana.
