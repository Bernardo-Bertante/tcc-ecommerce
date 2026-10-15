# Resultado F2 e F3 — validação de conexão sob carga mais alta (24/09/2026)

**Investigação exploratória.** Fora do desenho oficial do TCC. Nenhum `.tex`/`.md` do projeto
principal tocado, sem branch. Sem conclusão interpretativa sobre o que isto significa para a tese.
Mesmo formato de `../06_resultado_consolidado.md` (F1, coleta 3). Setup e decisões em `00_setup_e_plano.md`.

## Coleta

Palíndromo ABCCBA por cenário (A = SB, B = SB sem validação, C = QJ), F2 e depois F3, numa única
execução desacoplada (24/09, 00:24–04:31Z). RDS exploratório `db.t3.micro` em us-east-1d (mesma AZ do
oficial), uma task por vez, `TRUNCATE` + `pg_stat_statements_reset()` antes de cada rodada.

| | F2 | F3 |
|---|---|---|
| perfil | pré-aquec. 2 min a 48 → rampa 90 s → **7 min a 96** → descida 1 min (reduzido) | 48 / 240 / 48, 5m/2m/10m/2m/5m/1m (**oficial completo**) |
| iterações por rodada | 55.439–55.440 | 208.799 (SB: 207.772 e 208.466) |
| requisições por rodada | 62.195–62.196 | 233.975 (SB: 232.816 e 233.594) |
| falhas HTTP | 0 em todas | 0 em todas |
| iterações descartadas pelo k6 | 0 em todas | **SB r1: 1.027; SB r6: 333**; demais 0 |
| k6 rc | 0 em todas | **99 nas duas do SB** (thresholds p95 < 2 s / p99 < 5 s estourados); 0 nas demais |

Saída completa por requisição do k6 preservada: 12 × `k6_raw.json.gz` (354 MB) e 12 × `requests.csv.gz`
em `s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds/f2_f3/`.

## 1. Banco e CPU

Média das 2 réplicas. Fração do gap removida = (SB − SB sem val.) / (SB − QJ). A coluna "faixa" é a
fração calculada nas **8 combinações** de réplicas (2 SB × 2 sem val. × 2 QJ): mostra quanto o número
depende de quais rodadas se escolhe.

### F2

| medida | SB | SB sem val. | QJ | SB/QJ | sem val./QJ | fração do gap removida | faixa |
|---|---|---|---|---|---|---|---|
| CPU total do RDS (%) | 22,89 | 21,07 | 19,15 | 1,195 | 1,100 | 49 % | **7 % – 74 %** |
| CPU dos backends da app (%) | 8,45 | 6,75 | 5,87 | 1,440 | 1,150 | **66 %** | 63 % – 69 % |
| tempo ativo dos backends (ms/s) | 530,5 | 504,3 | 381,5 | 1,390 | 1,322 | 18 % | **−16 % – 48 %** |
| exec + planejamento (pgss, ms) | 230.423 | 222.089 | 175.459 | 1,313 | 1,266 | 15 % | **−10 % – 39 %** |

Réplicas: CPU total SB 24,04 / 21,74 (a primeira rodada da coleta inteira foi a mais alta); QJ `active_time`
408,9 / 354,1. **Em F2, só a CPU dos backends tem faixa estreita.** As outras três dependem de quais
réplicas se escolhe a ponto de trocar de sinal, então não sustentam um número único.

### F3

| medida | SB | SB sem val. | QJ | SB/QJ | sem val./QJ | fração do gap removida | faixa |
|---|---|---|---|---|---|---|---|
| CPU total do RDS (%) | 48,36 | 45,38 | 40,03 | 1,208 | 1,134 | **36 %** | 28 % – 43 % |
| CPU dos backends da app (%) | 33,16 | 29,86 | 24,68 | 1,343 | 1,210 | **39 %** | 36 % – 42 % |
| tempo ativo dos backends (ms/s) | 5.587,8 | 4.270,3 | 2.621,1 | 2,132 | 1,629 | **44 %** | 40 % – 49 % |
| exec + planejamento (pgss, ms) | 7.192.817 | 5.527.526 | 3.394.646 | 2,119 | 1,628 | **44 %** | 39 % – 48 % |

Em F3 as réplicas ficaram próximas (CPU total SB 47,84 / 48,88; sem val. 45,15 / 45,62; QJ 40,10 / 39,96),
e as faixas são estreitas nas quatro medidas.

## 2. Latência da aplicação

`http_req_duration` com `phase = load` (mesma definição da coleta 3/F1), réplicas agrupadas.
Fonte: `requests.csv.gz`. Faixa = 8 combinações de réplicas, como acima.

### F2

| estatística (ms) | SB | SB sem val. | QJ | SB/QJ | sem val./QJ | fração do gap removida | faixa |
|---|---|---|---|---|---|---|---|
| média | 14,28 | 10,62 | 7,84 | 1,821 | 1,354 | **57 %** | 46 % – 69 % |
| mediana | 7,28 | 5,00 | 3,40 | 2,141 | 1,469 | **59 %** | 51 % – 66 % |
| p90 | 20,16 | 14,31 | 9,01 | 2,238 | 1,589 | **52 %** | 45 % – 60 % |
| p95 | 33,05 | 24,08 | 15,42 | 2,143 | 1,562 | **51 %** | 25 % – 74 % |
| p99 | 98,29 | 86,01 | 67,43 | 1,458 | 1,276 | 40 % | **−20 % – 81 %** |

### F3

| estatística (ms) | SB | SB sem val. | QJ | SB/QJ | sem val./QJ | fração do gap removida | faixa |
|---|---|---|---|---|---|---|---|
| média | 497,71 | 160,48 | 53,78 | 9,255 | **2,984** | 76 % | 71 % – 81 % |
| mediana | 15,82 | 9,01 | 7,06 | 2,240 | 1,276 | 78 % | 71 % – 84 % |
| p90 | 1.945,29 | 150,51 | 20,88 | 93,19 | **7,210** | 93 % | 92 % – 94 % |
| p95 | 3.380,67 | 1.027,16 | 80,49 | 42,00 | **12,76** | 71 % | 69 % – 74 % |
| p99 | 6.546,68 | 3.332,84 | 1.641,39 | 3,989 | **2,031** | 66 % | 52 % – 79 % |

**Leitura obrigatória da tabela de F3:** a fração é calculada sobre um gap enorme (p90 SB/QJ = 93×).
Tirar a validação remove a maior parte desse gap **em milissegundos**, mas o SB sem validação continua
**3× (média), 7× (p90) e 13× (p95) mais lento que o QJ**. Em F1, o SB sem validação ficava
indistinguível do QJ; em F3, não. A fração alta e a razão "sem val./QJ" precisam ser lidas juntas.

Réplicas de F3 (p95): SB 3.661 / 3.179; sem val. 1.018 / 1.041; QJ 102,9 / 62,5. **O risco declarado no
plano — variância do SB dominar F3 — não se materializou:** as duas rodadas do SB caíram no mesmo
regime (ambas saturadas), com diferença de 13 % no p95.

### Por endpoint (réplicas agrupadas, p50 / p95 / p99 em ms)

**F3:**

| endpoint | SB | SB sem val. | QJ |
|---|---|---|---|
| **GET /orders/summary** (`get_summary`) | **229,1 / 3.211,5 / 4.302,6** | **208,7 / 2.340,0 / 3.569,4** | **171,8 / 622,8 / 3.023,3** |
| POST /orders (`create_order`) | 20,1 / 5.355,9 / 8.968,6 | 14,0 / 1.608,9 / 5.172,9 | 8,4 / 45,2 / 975,4 |
| GET /orders/{id} (`get_order`) | 14,0 / 2.810,1 / 4.304,6 | 6,8 / 897,0 / 2.927,5 | 5,2 / 20,7 / 1.790,8 |
| GET /orders/customer/{id} | 8,0 / 2.823,9 / 4.291,4 | 5,4 / 884,9 / 2.906,0 | 3,6 / 19,0 / 1.754,2 |
| PUT status (`update_status`) | 32,5 / 4.500,9 / 7.908,1 | 13,6 / 1.035,4 / 3.683,4 | 8,8 / 55,8 / 2.235,1 |

No `get_summary`, a **mediana** muda pouco entre condições (229 / 209 / 172 ms); a diferença está na cauda.
Nos endpoints triviais, SB e SB sem validação têm p50 baixo e p95 de segundos. A cauda não é do endpoint:
é espera, que atinge todos eles no mesmo período (ver item 5).

**F2:**

| endpoint | SB | SB sem val. | QJ |
|---|---|---|---|
| `get_summary` | 56,6 / 137,4 / 331,8 | 50,1 / 125,7 / 334,5 | 41,4 / 112,2 / 280,3 |
| `create_order` | 16,2 / 31,9 / 143,3 | 11,6 / 24,4 / 141,7 | 7,8 / 14,8 / 113,5 |
| `get_order` | 6,5 / 16,9 / 61,2 | 4,4 / 10,6 / 47,6 | 3,0 / 7,8 / 30,5 |
| `get_orders_by_customer` | 7,0 / 13,2 / 44,6 | 4,9 / 9,4 / 47,8 | 3,3 / 5,9 / 25,9 |
| `update_status` | 13,9 / 47,6 / 126,6 | 9,3 / 33,4 / 90,3 | 7,7 / 26,2 / 55,8 |

### Comparação com o oficial (`fase5_estatistica_descritiva_novo.csv`)

Aqui a latência usa **todas** as requisições (setup, aquecimento, auxiliar e carga), porque é essa a
definição dos `*-latency.json` oficiais (lá, `n` por rodada = `http_reqs`). Entre colchetes, a razão com
`phase = load`, para referência.

**F2 — valida só sentido e ordem de grandeza** (platô de 7 min contra 30 min no oficial; tabela menor):

| | reprodução SB | reprodução QJ | razão SB/QJ | oficial SB | oficial QJ | razão SB/QJ oficial |
|---|---|---|---|---|---|---|
| média | 15,61 | 8,83 | 1,77 [1,82] | 19,15 | 10,16 | 1,88 |
| mediana | 8,75 | 3,86 | 2,26 [2,14] | 11,56 | 6,15 | 1,88 |
| p90 | 21,55 | 9,28 | 2,32 [2,24] | 20,10 | 8,75 | 2,30 |
| p95 | 37,54 | 15,33 | 2,45 [2,14] | 34,91 | 12,27 | 2,84 |
| p99 | 111,63 | 72,92 | 1,53 [1,46] | 259,62 | 168,26 | 1,54 |

Mesmo sentido e mesma ordem de grandeza em todas as estatísticas (razões 1,5–2,5× × 1,5–2,8×).
Os valores absolutos de p99 são menores na reprodução, coerente com o platô mais curto.

**F3 — duração oficial, comparação direta:**

| | reprodução SB | reprodução QJ | razão SB/QJ | oficial SB | oficial QJ | razão SB/QJ oficial |
|---|---|---|---|---|---|---|
| média | 525,29 | 52,38 | 10,03 [9,26] | 90,93 | 15,74 | 5,78 |
| mediana | 16,56 | 7,55 | **2,19** [2,24] | 14,89 | 6,95 | **2,14** |
| p90 | 2.018,05 | 22,52 | 89,62 [93,19] | 63,80 | 11,83 | 5,39 |
| p95 | 3.559,85 | 80,63 | 44,15 [42,00] | 357,42 | 29,16 | 12,26 |
| p99 | 6.940,03 | 1.530,12 | 4,54 [3,99] | 1.934,26 | 254,01 | 7,61 |

A **mediana reproduz** (2,19 × 2,14, valores absolutos próximos). A **cauda não**: na reprodução, a cauda
do SB é muito mais pesada que a do oficial agrupado (p95 3,6 s × 0,36 s). O oficial agrupa 5 rodadas de
dias diferentes; o reexame de setembro (`../../investigacao_instabilidade_f3_setembro/`) mostrou que o F3
do SB oficial é ruim **por dia** (p95 por rodada de 326 a 2.108 ms nas rodadas ruins, normal nas outras).
As duas rodadas SB desta coleta caíram no regime saturado, com p95 acima até da pior rodada oficial,
na mesma faixa da reprodução de 21/09 (825–3.149 ms). **Em F3, só a mediana e o sentido das razões são
comparáveis com o oficial; os valores de cauda, não.**

## 3. A fração explicada pela validação muda com a taxa?

| medida | F1 (coleta 3) | F2 | F3 |
|---|---|---|---|
| CPU total do RDS | 86 % | 49 % (faixa 7–74 %, **inconclusivo**) | 36 % (28–43 %) |
| CPU dos backends | 79 % | **66 %** (63–69 %) | **39 %** (36–42 %) |
| tempo ativo dos backends | 72 % | 18 % (−16–48 %, **inconclusivo**) | 44 % (40–49 %) |
| exec + plan (pgss) | 74 % | 15 % (−10–39 %, **inconclusivo**) | 44 % (39–48 %) |
| latência, média | 104 % | 57 % (46–69 %) | 76 % (71–81 %) |
| latência, mediana | 98 % | 59 % (51–66 %) | 78 % (71–84 %) |
| latência, p95 | 119 % | 51 % (25–74 %) | 71 % (69–74 %) |
| latência, p99 | — (sem dado na coleta 3) | 40 % (−20–81 %, **inconclusivo**) | 66 % (52–79 %) |
| **latência: SB sem val. / QJ (p95)** | **0,85 (indistinguível)** | **1,56** | **12,76** |

**Resposta direta ao item 4:**

- **No banco, a fração desce com a taxa.** Na medida com faixa estreita nos três cenários (CPU dos
  backends): **79 % → 66 % → 39 %**. Na CPU total do RDS, 86 % em F1 e 36 % em F3; em F2 a faixa (7–74 %) é
  larga demais para um número. Em pontos percentuais de CPU dos backends, o custo absoluto da validação
  **cresce** com a taxa (SB − sem val.: 1,28 → 1,70 → 3,30), mas o resíduo **cresce mais rápido**
  (sem val. − QJ: 0,34 → 0,88 → 5,18).
- **Na latência, a fração em % não é monotônica** (≈ 100 % → ≈ 55 % → ≈ 75 %), mas a razão
  **SB sem validação / QJ sobe com a taxa**: indistinguível em F1, 1,4–1,6× em F2, 3–13× em F3. Em F3 a
  fração alta vem do tamanho do gap do SB, não de o SB sem validação ter chegado perto do QJ.

Ressalva: F1 vem de outra instância RDS (coleta 3, us-east-1f, 23/09). F2 e F3 são da mesma instância
(us-east-1d, 24/09). A comparação entre taxas mistura taxa com instância/dia para o F1.

## 4. Mecanismos que não apareciam em F1 (observações, não isoladas)

**a) Saturação de CPU do RDS no fim do pico do F3 — e a validação empurra para dentro dela.**
CPU total do RDS por minuto (`resultados/f3/serie_resumo.txt`), minutos 14–18 do pico:

| | min 14 | min 16 | min 18 |
|---|---|---|---|
| SB (r1 / r6) | 83 / 82 % | 93 / 94 % | 100 / 98 % |
| SB sem val. (r2 / r5) | 83 / 80 % | 90 / 87 % | 94 / 94 % |
| QJ (r3 / r4) | 70 / 70 % | 78 / 78 % | 81 / 82 % |

A CPU sobe nas três condições durante o pico (custo do `get_summary` crescendo com a tabela, o mesmo
mecanismo da reprodução de 21–22/09). O p95 por minuto explode quando ela passa de ~85–90 %: SB e SB sem
validação a partir do minuto ~12–14 (p95 de 0,6 a 8,6 s); QJ só num pico no minuto 18 (1,9–2,3 s).
Perto desse joelho, uma diferença pequena de CPU vira uma diferença enorme de latência. A validação
soma ~3 pontos de CPU do RDS em F3. Sem ela o SB satura menos e por menos tempo, mas **ainda satura**,
porque o resíduo (≈ 5 pontos acima do QJ) também é suficiente para cruzar o joelho. Em F1 e F2 o RDS nunca
chegou perto disso.

**b) O resíduo está no `get_summary`, executando mais devagar no SB mesmo sem validação.**
exec + plan por chamada (`resultados/residuo_por_operacao.txt`):

| `get_summary`, ms/chamada | SB | SB sem val. | QJ |
|---|---|---|---|
| F2 | 35,8 | 34,2 | 26,3 |
| F3 | 330,2 | 252,7 | 156,1 |

É o mesmo "mesma consulta mais lenta" da coleta 1 (SQL idêntico). Em F1, isso **sumia** ao tirar a
validação; em F2 e F3, **não**. É tempo de parede (inclui espera por CPU no RDS), não CPU por consulta.
Com os dados daqui não dá para separar o que é a consulta do SB custando mais do que é disputa com o
restante do tráfego do SB, que mesmo sem validação gera mais bytes por requisição (ver coleta 3).

**c) Esgotamento na aplicação, só no SB com validação.** Só as duas rodadas F3 do SB descartaram
iterações (1.027 e 333: o k6 ficou sem VU livre porque as respostas demoravam). Sem validação: 0,
igual ao QJ.

**d) Pico transitório de CPU do contêiner: sem evidência na resolução disponível.** CPU da task
(Container Insights, média por minuto): máximo de 721 / 607 unidades no SB, 611 / 611 no SB sem validação,
342 / 181 no QJ (1.024 = 1 vCPU). Nenhuma rodada saturou a task em média de 1 minuto, e tirar a validação
pouco muda a CPU do contêiner do SB (F2: 265 / 214 × 242 / 212). Picos sub-minuto não são visíveis nesta
fonte; não foi medido em resolução maior.

## 5. Resposta direta

**Em F2 e F3, a validação de conexão deixa de explicar a maior parte da diferença.** No banco, a fração
cai com a taxa — CPU dos backends 79 % (F1) → 66 % (F2) → 39 % (F3); CPU total do RDS 86 % (F1) → 36 % (F3).
Na latência, tirar a validação ainda remove a maior parte do gap **em milissegundos** em F3, mas o SB sem
validação continua 3–13× mais lento que o QJ nas estatísticas de média a p95, enquanto em F1 ficava
igual a ele.

O que passa a pesar é um mecanismo que não aparecia em F1: o **`get_summary` executando mais devagar no
SB mesmo sem validação**, combinado, em F3, com a **proximidade do joelho de saturação de CPU do RDS**.
Lá, os ~5 pontos de CPU que sobram (SB sem validação × QJ) bastam para levar o banco a 87–94 % e produzir
caudas de segundos. Esse mecanismo foi observado, não isolado.

## Limites

- 2 réplicas por condição e por cenário. As faixas das 8 combinações estão reportadas; onde a faixa
  cruza zero ou abrange 7–74 %, o número foi marcado como inconclusivo.
- F2 reduzido: valida sentido e ordem de grandeza contra o oficial, não valores.
- F3 caiu no regime saturado nas duas rodadas SB. Valores de cauda não são comparáveis com o oficial
  agrupado; só a mediana e o sentido das razões são.
- `db.t3.micro` exploratório, não o oficial; *steal* médio 2,8–4,0 % nas rodadas.
- `auto_explain` a 2 % e `track_planning` ligados em todas as rodadas (custo pequeno e simétrico).
- CPU do contêiner só em média de 1 minuto.

## Fontes

| dado | arquivo |
|---|---|
| métricas por rodada (CPU RDS, backends, active_time, pgss, steal, CPU da task, rede) | `resultados/{f2,f3}/metricas_por_rodada.csv` |
| tabelas de gap (banco) com réplicas e faixas | `resultados/{f2,f3}/gap_banco.csv` |
| latência por rodada / condição / endpoint | `resultados/{f2,f3}/latencia_por_rodada.csv`, `latencia_por_condicao.csv`, `latencia_por_endpoint.csv` |
| comparação com o oficial | `resultados/{f2,f3}/comparacao_oficial.csv` |
| séries por minuto | `resultados/{f2,f3}/serie_por_minuto.csv`, `resultados/f3/serie_resumo.txt` |
| resíduo por operação | `resultados/residuo_por_operacao.txt` |
| saída do script | `resultados_console.txt` |
| dados brutos por rodada | `dados/{f2,f3}/r*/` (+ `k6_raw.json.gz` no S3) |
| script | `analisa_f2f3.py` |
