# CPU do RDS por cenário × runtime × rodada

**Data da análise:** 10/09/2026 · **Script:** `analysis/fase5_rds_cpu_por_rodada.py`
**Saídas:** `fase5_rds_cpu_por_rodada.csv` (94 linhas) · `fase5_rds_cpu_por_rodada_raw.json` (datapoints brutos)

Nenhum teste reexecutado, nenhum CSV oficial sobrescrito. Fonte: `AWS/RDS CPUUtilization`,
dim `DBInstanceIdentifier=order-service-postgres`, na mesma janela de carga sustentada
usada para o container (sem rampas, prewarm, boot, TRUNCATE/repopulate; só buckets
inteiramente contidos na janela).

## 1. A premissa do 08-known-problems.md está desatualizada

A limitação "CPU do RDS não recuperada por rodada" não se sustenta: o RDS é instância
única e as janelas já existiam. Correção factual ao enunciado da investigação: o F1 e o
F3 **oficiais** não são de julho/agosto — são as re-coletas de 31/08 e 02–05/09, com
`meta.json` e timestamps exatos. Não foi preciso CloudTrail para eles.

| cenário | fonte da janela | granularidade | cobertura |
|---|---|---|---|
| F1 (31/08) | `meta.json` | p60 | 15/15 |
| F3 (02–05/09) | `meta.json` (fases exatas) | p60 | 15/15 (peak, baseline, recovery) |
| F2-S (10/08) | RunTask (NOTAS F2-S §1), PRE_K6=60 | p300 | 15/15 (1–2 dp/rodada) |
| F2 (jul) | `runtasks_july.json` + mtime, PRE_K6 de julho | p300 r4–r5 / p3600 r1–r3 | 6 ok + 7 contaminadas + 2 perdidas |
| F3-jul (suplementar) | idem | p300 | 6/15 (r4–r5); r1–r3 perdidas |

Retenção (verificada 10/09): p60 só de ~26/08 em diante; p300 de 06–07/07 já expirou;
**p300 de 13/07 (F2 r4–r5, F3-jul r4–r5) expira ~14/09** — brutos salvos no JSON.
F2 r1–r3 só em p3600 (bucket de 1 h com 50 % de hold) → `qualidade=p3600_contaminado`,
fora das conclusões. F2 quarkus-jvm r2 e quarkus-native r1: nenhum bucket horário com ≥50 % de hold.

Modo de crédito: `describe-db-instances` não expõe o campo para RDS, mas
`CPUSurplusCreditBalance` chegou a 98,6 (só acumula em **Unlimited**) e
`CPUSurplusCreditsCharged` = 0 em todo o período. Idle (09/09): ~3 % média.

## 2. Resultado (CPU média do RDS %, média ± DP entre rodadas; pico = maior 1-min/5-min)

| cenário / fase | taxa | springboot | quarkus-jvm | quarkus-native | SB ÷ Quarkus |
|---|---|---|---|---|---|
| F1 hold | 48 it/s | 11,3 ± 0,1 (pico 14,7) | 9,2 ± 0,1 (13,0) | 9,4 ± 0,2 (13,3) | 1,22 |
| F3 baseline | 48 it/s | 9,8 ± 0,5 (11,5) | 8,5 ± 0,4 (10,4) | 7,8 ± 0,6 (9,8) | 1,21 |
| F2 hold (r4–r5, n=2) | ~96 it/s | 31,1 ± 0,2 (42,2) | 23,0 ± 0,8 (35,1) | 23,0 ± 1,3 (32,0) | 1,35 |
| F3 recovery | 48 it/s | 25,8 ± 0,7 (27,7) | 21,0 ± 0,2 (22,2) | 20,6 ± 0,5 (21,8) | 1,24 |
| F3 peak | 240 it/s | 60,7 ± 1,6 (**85,9**) | 50,0 ± 1,3 (69,9) | 48,5 ± 1,0 (69,3) | 1,23 |
| F2-S hold | 8 req/s | **77,3** ± 0,4 (80,8) | 61,0 ± 0,6 (65,1) | 60,9 ± 0,4 (64,8) | 1,27 |

Kruskal-Wallis entre os 3 runtimes: p ≤ 0,009 em todos os cenários com n=5.
JVM × Native (Mann-Whitney): p = 0,10–0,69 — **indistinguíveis** em todos.

## 3. Interpretação

**Por runtime — a expectativa se confirma só em parte.** Quarkus JVM e Native geram
carga idêntica no banco (mesmo código, mesmas queries — muda só o modo de execução),
o que confirma a hipótese "o modo de execução Java não afeta o banco". Mas o **Spring
Boot impõe ~21–27 % a mais de CPU ao RDS, de forma consistente em todos os cenários e
fases**, com DP entre rodadas de 0,1–1,6 p.p. Não é o runtime em si, é a **pilha de
acesso a dados**: Spring Boot usa Spring Data R2DBC + `r2dbc-postgresql`; Quarkus usa
Hibernate Reactive Panache + Vert.x `reactive-pg-client`. Mesmo pool (max 20).
Hipótese não verificada: diferença no uso do protocolo estendido / cache de prepared
statements (parse por execução no servidor). Confirmar exigiria `pg_stat_statements`.

Descartado confundidor de ordem/tempo: no F3 o springboot r4–r5 rodou em 05/09
intercalado com native r3–r5 e manteve o mesmo patamar (58–60 % vs 48–50 %).

**Implicação para o TCC:** a vantagem de CPU do Quarkus no container **não é
transferida para o banco** — ela se soma. Com o RDS dimensionado para o SB (pico
86 %), o Quarkus deixa ~16 p.p. de folga no mesmo `db.t3.micro`.

**Por cenário:** ordem pela média é **F1 ≈ F3-baseline < F3-recovery < F2 < F3-peak < F2-S**.
- F1 hold e F3 baseline (ambos 48 it/s) batem (9–11 % vs 8–10 %) — checagem de
  robustez: mesma taxa → mesma CPU de banco, em coletas de dias diferentes.
- F3 recovery (48 it/s) fica em 21–26 %, **2,5× o baseline na mesma taxa**: efeito
  pós-pico no banco (tabela crescida pelas escritas do pico e/ou autovacuum). Merece nota.
- F2-S tem a **maior CPU média** com a **menor taxa** (8 req/s): custo por query
  (agregação sobre 50.000 linhas) domina a taxa.
- Pico absoluto: F3 peak springboot, 86 % em 1 min.

**Confundidor "task fresca / banco limpo" (90–98 % vs 64–65 %):** na coleta final
nenhuma janela chegou a 90 %; o F3 peak é estável entre rodadas (DP ≤ 1,6 p.p.) com
descanso de 133–164 s entre rodadas. O contraste qualitativo registrado era da fase de
diagnóstico e **não aparece nos dados oficiais** — o protocolo de task fresca +
TRUNCATE parece ter neutralizado o efeito. O contraste F3 baseline × recovery (mesma
taxa, 8 % vs 21 %) é o análogo quantificável dentro de uma rodada.
