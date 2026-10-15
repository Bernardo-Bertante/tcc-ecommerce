# F2-S — CPU/memória do Fargate (reconstrução via CloudTrail RunTask)

**Data da análise:** 09/09/2026 · **Script:** `analysis/fase5_recursos_f2s.py`
**Saída:** `analysis/fase5/fase5_f2s_recursos.csv` (15 linhas, 5 rodadas × 3 runtimes)

Nenhum teste de carga foi reexecutado. Só reconsulta de métricas já existentes.
Nenhum CSV oficial foi sobrescrito.

## 1. Os 15 timestamps FORAM localizados

CloudTrail ainda tem os eventos `RunTask` de 10/08/2026 (retenção de 90 dias →
expira ~08/11/2026). **Atenção: há DOIS blocos de 15 RunTask nesse dia.**

| bloco | janela (UTC) | é a coleta boa? |
|---|---|---|
| 1 | 00:04 – 05:35 | não |
| 2 | **10:11 – 15:46** | **sim** |

O bloco 2 é o que casa com os `mtime` dos `summary.json` em disco: o gap
RunTask → mtime fica em 830–885 s nas 15 rodadas (o k6 dura 840 s). A atribuição
rodada → arquivo é inequívoca: 5 RunTask por runtime, em ordem cronológica,
espaçados ~15 min.

Timestamps (UTC, 10/08/2026):

| runtime | r1 | r2 | r3 | r4 | r5 |
|---|---|---|---|---|---|
| springboot | 10:11:26 | 10:27:22 | 10:42:35 | 10:57:56 | 11:13:20 |
| quarkus-jvm | 12:29:18 | 12:44:20 | 12:59:36 | 13:14:44 | 13:30:29 |
| quarkus-native | 14:45:42 | 15:00:49 | 15:16:03 | 15:31:06 | 15:46:12 |

## 2. Por que o CSV antigo estava errado

As linhas `f2s` de `fase5_fargate_recursos_novo.csv` vieram de
`estimate_round_window_from_mtime(padding_sec=600)`, que monta a janela
`[mtime − 1440 s, mtime + 600 s]` = **2040 s (34 min)** para rodadas que estão
**~910 s (15 min)** umas das outras. Janelas de rodadas consecutivas se sobrepõem
quase inteiramente e engolem o pico de arranque das tasks vizinhas.

Assinatura do defeito no CSV antigo: r2 e r3 compartilham `cpu_units_max`
idêntico (520,204…), e r4/r5 também (492,026…). Mesmo defeito de
`08-known-problems.md` #18.

Confirmado no traço bruto — o bucket 10:40–10:45 Z (max **520,2** unidades)
contém o `RunTask` da rodada 3 (10:42:35), não carga da rodada 2.

## 3. Janela usada agora

`hold = [RunTask + PRE_K6 + 30 s, RunTask + PRE_K6 + 810 s]` (exclui ramp-up e
ramp-down), com duas regras de seleção:

- só entram buckets de 5 min **inteiramente contidos** no hold;
- **guarda anti-arranque**: descarta qualquer bucket que toque
  `[RunTask − 30 s, RunTask + 180 s]`.

### PRE_K6 recalibrado (correção relevante)

O `PRE_K6` de julho (`fase5_recursos_fase_isolada.py`: springboot 105 s, jvm 55 s,
native 50 s) **é incompatível com esta coleta**. As rodadas são encadeadas com
`RunTask` a cada 902–956 s e o k6 sozinho já ocupa 840 s, logo
`PRE_K6 + teardown = 62…116 s` (mediana ~74 s). Com `PRE_K6 = 105 s` a task
seguinte teria sido lançada *antes* do fim do k6 da rodada anterior — o que não
ocorre. Aqui o termo dominante é o provisionamento do Fargate (ENI + image pull,
~40–60 s), que não depende do runtime; adotado **`PRE_K6 = 60 s` para os três**.

Sensibilidade (regra estrita, CPU média agregada por runtime, `PRE_K6` de 0 a
105 s): a média se move **menos de 1,2 p.p.** em qualquer runtime. Só os
*máximos* são sensíveis, e apenas por vazamento do pico de boot — que a guarda
anti-arranque elimina.

## 4. Limitação: granularidade

`period=60` **já expirou** para 10/08 (retenção de 1 min = 15 dias; verificado:
0 datapoints). Só `period=300` está disponível (retenção 63 dias, expira
~12/10/2026). Como o hold tem 780 s = 2,6 buckets de 300 s, sobram **1–2
datapoints por rodada** (8 para springboot, 5 para quarkus-jvm, 10 para
quarkus-native no total). É pouco por rodada; no agregado por runtime é
suficiente, mas **não use estes números para variância entre rodadas**.

## 5. Resultado

CPU/memória do F2-S por runtime (task de 1024 unidades / 2048 MB):

| runtime | CPU média | CPU pico | MEM média | MEM pico |
|---|---|---|---|---|
| springboot | 38,1 un (3,72 %) | 99,4 un (9,70 %) | 263,8 MB (12,88 %) | 272 MB |
| quarkus-jvm | 14,9 un (1,45 %) | 28,7 un (2,81 %) | 212,1 MB (10,36 %) | 219 MB |
| quarkus-native | 9,9 un (0,96 %) | 16,6 un (1,62 %) | 53,1 MB (2,59 %) | 60 MB |

Correção frente ao número antigo: CPU média do springboot e do quarkus-jvm cai
~50 % (era pico de boot, não carga); o native quase não muda (+6,7 %), porque
não tem pico de arranque para contaminar.

### Comparação com F1/F2/F3 (CPU média %, MEM média MB)

| cenário | springboot | quarkus-jvm | quarkus-native |
|---|---|---|---|
| **F2-S** (8 req/s, leitura) | **3,72 % / 264 MB** | **1,45 % / 212 MB** | **0,96 % / 53 MB** |
| F1 | 11,12 % / 294 MB | 4,33 % / 224 MB | 6,25 % / 25 MB |
| F2 | 21,37 % / 376 MB | 7,72 % / 245 MB | 10,08 % / 28 MB |
| F3 | 45,67 % / 614 MB | 16,26 % / 261 MB | 18,78 % / 28 MB |

## 6. O padrão de memória se repete no F2-S? **Não.**

Picos de memória por cenário:

| cenário | springboot | quarkus-jvm | quarkus-native |
|---|---|---|---|
| F1 | 321 MB | 235 MB | 60 MB |
| F2 | 578 MB | 260 MB | 35 MB |
| F3 | **1064 MB** | 308 MB | 32 MB |
| **F2-S** | **272 MB** | **219 MB** | **60 MB** |

No F1→F2→F3 a memória do Spring Boot escala com a carga (321 → 578 → 1064 MB) e
cruza degraus de faturamento do Fargate, enquanto o Quarkus fica praticamente
plano. **No F2-S isso não acontece:** os três cabem folgadamente no menor degrau
do Fargate (0,25 vCPU / 512 MB) — springboot usa 53 % desse degrau de memória e
99 de 256 unidades de CPU no pico.

Ou seja: a vantagem *relativa* do Quarkus persiste (o Spring Boot consome 2,6× a
CPU do Quarkus JVM e 3,9× a do Native; 5× a memória do Native), mas **no F2-S ela
não tem consequência de faturamento** — a carga é leve demais (8 req/s) para que
a diferença mude o degrau contratado. O F2-S separa os runtimes por eficiência,
não por custo de provisionamento.

Duas observações de detalhe:

- O **quarkus-native usa mais memória no F2-S (53 MB) do que em F1/F2/F3
  (25–28 MB)** — quase o dobro. Compatível com a natureza do cenário: leitura
  analítica sobre 50.000 linhas, com result set maior em memória.
- No traço bruto de springboot e quarkus-jvm, o **primeiro bucket após o boot é
  consistentemente maior que o segundo** (ex.: 66,7 → 38,8 unidades) — cauda de
  aquecimento de JIT. No quarkus-native o traço é plano (8,2 → 8,3), sem
  aquecimento. Coerente com o achado de `l2-warmup-curve-intrinsic-gap`.
