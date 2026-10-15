# L1 — Investigação da lacuna de dados apontada na auditoria externa (Cap. 5, Lambda)

Data: 2026-09-07 · Conta AWS `pessoal` (776648109551) · região us-east-1

Continuação de `l1_dup_investigation.py` (reconciliação de N e identificação das 32
invocações reais de L1). Objetivo: dar fonte canônica aos dois números do texto que
não tinham CSV bruto — "execução pós-init" e "latência ponta-a-ponta total (k6)".

---

## 1. `Duration` (execução pós-inicialização) — ENCONTRADO E EXTRAÍDO

**Fonte:** linha `REPORT RequestId` do CloudWatch Logs, campo `Duration:` (mesma
linha de `Init Duration:`), log groups `/aws/lambda/order-processor-{springboot,
quarkus-jvm,quarkus-native}`.

**Comando / script:** `analysis/lambda/l1/l1_duration_postinit.py`
(boto3 `logs.filter_log_events`, `filterPattern='"REPORT RequestId"'`, com
`startTime`/`endTime` fixados na janela de cada sessão L1 — seleção por janela
temporal, não por fingerprint numérico; ver nota metodológica abaixo).

**Saídas geradas:**
- `analysis/lambda/l1/l1_duration_postinit.csv` — 33 linhas (11+11+11), uma por
  invocação, com `request_id`, `timestamp_utc`, `init_duration_ms`, `duration_ms`,
  `billed_duration_ms`, `max_memory_used_mb`, `excluded_outlier`.
- `analysis/lambda/l1/l1_duration_postinit_summary.json` — agregados por runtime.

### Resultado

| Runtime | N | `Duration` média (pós-init) | Desvio | Mediana | Min–Max | Valor no texto atual |
|---|---|---|---|---|---|---|
| Spring Boot | 11 | **2.766,7 ms** | ± 134,2 | 2.773,7 | 2.568,9 – 3.058,7 | ~2.774 ms |
| Quarkus JVM | 10 | **5.600,4 ms** | ± 173,7 | 5.620,4 | 5.315,1 – 5.842,5 | ~5.600 ms |
| Quarkus Native | 11 | **345,8 ms** | ± 17,5 | 350,5 | 308,6 – 369,3 | ~345 ms |

**Conclusão:** os três números do texto ("execução pós-init") **são valores reais
de `Duration` do CloudWatch**, corretos dentro do arredondamento. Não eram
estimativa. O que faltava era a **fonte canônica** (CSV + script), agora criada.
O "~2.774" do Spring Boot corresponde à mediana (2.773,7) — as outras duas versões
o texto usou a média. Sugestão para a versão final: padronizar em média e citar
`l1_duration_postinit.csv`.

### Nota metodológica (por que janela temporal e não fingerprint)

`l1_dup_investigation.py` já puxava a linha REPORT inteira e parseava `Duration`,
mas (a) só imprimia, não persistia, e (b) selecionava por fingerprint contra os
`init_duration_ms` de `l1_init_durations.json`. Para Spring Boot e Native isso
funciona (valores com 2 casas decimais, distintos). Para **Quarkus JVM os alvos
salvos foram arredondados a 1 ms inteiro** e o log group acumula centenas de cold
starts de L2/L3 (07-05: 128, 07-06: 98, 07-16: 145) que colidem dentro da
tolerância de 0,5 ms — o `linear_sum_assignment` casou 4 das 10 invocações com
eventos de **sessões erradas** (05/07 e 16/07). Como todo cold start de Quarkus
JVM tem `Duration` ~5,3–5,8 s, a média saiu quase igual por acaso (5.621 vs 5.600),
mas não era rastreável.

A seleção por janela é inequívoca: cada sessão L1 é um bloco isolado de 11
invocações espaçadas 15 min. Janelas confirmadas por inspeção
(`l1_window_probe.py`), em UTC:

| Runtime | Janela (UTC) | Invocações |
|---|---|---|
| Spring Boot | 2026-07-02 19:43:02 → 22:13:02 | 11 (todas válidas) |
| Quarkus Native | 2026-07-03 13:26:36 → 15:56:36 | 11 (todas válidas) |
| Quarkus JVM | 2026-07-03 16:58:49 → 19:28:49 | 11 = 10 válidas + 1 outlier |

**Outlier do Quarkus JVM** (o excluído da análise, N=10): a **primeira** invocação
da sessão — `2026-07-03T16:58:49.899Z`, `request_id`
`dace96c3-ad44-43c2-9313-83c3ed82acdd`, `Init Duration` 1.492,52 ms
(o mais alto da sessão), `Duration` 5.666,12 ms. É a única cujo `init_duration`
não consta na lista dos 10 valores de `l1_init_durations.json`.

---

## 2. Latência ponta-a-ponta total (k6) — NÃO ENCONTRADO

**Não existe nenhum arquivo de saída do k6 para o L1 em lugar nenhum.**

Buscas feitas (todas negativas para qualquer arquivo de latência/raw/summary do L1):
- `find / -name 'l1_sparse_coldstart*' -o -name 'l1_*run*'` → só o script `.js`.
- `grep -rl "l1_sparse_coldstart"` no repo → só `l1_sparse_coldstart.js`,
  `benchmark/README.md`, `benchmark/run/run-lambda.sh` (referências ao cenário, não dados).
- `analysis/lambda/fase4/` → só `{l2,l3}-*` (raw/latency/summary). Nenhum `l1-*`.
- `benchmark/results/**` (todos os subdiretórios) → nenhum output de L1.
- `~/Downloads`, `~/Documentos`, `~/.local/share/Trash` → nada.
- `git log --all` para arquivos deletados com `l1`/`cold`/`sparse` → nada.
- CloudWatch `describe-log-groups` → só os 3 log groups de função Lambda +
  3 de ECS + 1 de Container Insights. **Não há log group de API Gateway nem de
  Function URL access log** — ou seja, não existe registro server-side de latência
  ponta-a-ponta em nenhum lugar.

O pipeline da Fase 5 (`fase5_analise_estatistica.py`) **não usa k6 para o L1**: a
função `analyze_l1()` e o teste de significância do L1 operam sobre
`l1_init_durations.json` (`init_duration`), não sobre latência. A linha "l1" em
`fase5_estatistica_descritiva.csv` (`mean` 3727 / 1386 / 305) é `init_duration`,
não latência k6. `03-methodology.md:27` e `04-experiments.md:49` dizem
explicitamente que para o L1 a métrica vem do CloudWatch, "não do k6".

**Portanto os números "~7,1 s" (Spring Boot) e "~7,3–7,6 s" (Quarkus JVM) do
texto (`05-results.md:71`) não têm fonte rastreável no projeto.** Não conssegui
nem confirmar que são medições reais nem reconstruí-los. Não os estimo aqui.

`05-results.md:182` diz que o custo do Lambda foi "calculado a partir da latência
ponta-a-ponta do k6 (`fase5_estatistica_descritiva.csv`)" — mas a tabela de custo
(linhas 184–191) só tem L2/L3 (que de fato têm latência k6). O L1 não entra no
custo. A referência a latência k6 do L1 parece ser um resíduo de redação.

---

## 3. Fechamento aritmético (Init + Duration vs. total do texto)

Só o lado esquerdo é rastreável. O "total k6" é o número não-fundamentado.

| Runtime | Init (CW) | Duration (CW) | Init+Duration | "Total k6" (texto, sem fonte) | Resíduo |
|---|---|---|---|---|---|
| Spring Boot | 3.727,0 | 2.766,7 | **6.493,8 ms** | ~7.100 ms | ~606 ms |
| Quarkus JVM | 1.385,9 | 5.600,4 | **6.986,3 ms** | ~7.300–7.600 ms | ~314–614 ms |
| Quarkus Native | 305,0 | 345,8 | **650,8 ms** | (texto não cita) | — |

O resíduo de 300–600 ms nos dois casos é da ordem de grandeza de um RTT
Brasil↔us-east-1 (residencial, ~120–160 ms) somado a handshake TLS na primeira
conexão (2 RTT) e overhead do cliente k6 — **plausível, não confirmado**. Como não
há dado de k6, isso é conjectura; não deve entrar na monografia como causa.

Observação: numa invocação cold, a AWS cobra `Init Duration + Duration` — o
`Billed Duration` da linha REPORT confirma isso em toda invocação
(ex.: JVM `6cfd76e1` — `Duration: 5778.25 ms` + `Init Duration: 1377.87 ms` =
7156,12 → `Billed Duration: 7157 ms`). Portanto `Init + Duration` é exatamente o
tempo interno total do Lambda; a latência que o cliente k6 percebe numa chamada
cold é ~`Init + Duration + rede`, e o fechamento acima é a comparação correta.
Isso também dá uma base de "billing" real para o L1 que hoje não está no texto —
médias de `Billed Duration`: Spring Boot ~6.494 ms, Quarkus JVM ~6.986 ms (N=10),
Quarkus Native ~651 ms.

### Linha REPORT verbatim (uma por runtime, como evidência)

```
REPORT RequestId: 6cfd76e1-302a-4fd2-af07-eb07d3f2128e  Duration: 5778.25 ms  Billed Duration: 7157 ms  Memory Size: 512 MB  Max Memory Used: 185 MB  Init Duration: 1377.87 ms
```
(`/aws/lambda/order-processor-quarkus-jvm`, 2026-07-03T17:13:49Z — invocação #2 da sessão, 1ª válida)
As 33 linhas completas estão em `l1_duration_postinit.csv`; cada uma reproduzível com
`aws logs filter-log-events --profile pessoal --region us-east-1 --log-group-name <grupo> --start-time <ts> --end-time <ts+90s> --filter-pattern '"REPORT RequestId"'`.

---

## 4. Viabilidade de reexecutar o L1 hoje (só avaliação — nada foi executado)

**Tecnicamente simples. Sem mudança de infraestrutura.**

- As 3 funções Lambda estão no ar (`aws lambda list-functions`): `java21` (SB, JVM)
  e `provided.al2023` (Native), **512 MB** — mesma config do experimento original.
- Spring Boot tem Function URL pública (`AuthType: NONE`,
  `https://<id>.lambda-url.us-east-1.on.aws/`);
  presumivelmente as outras duas também (não checei as 3, só a do SB).
- O script `benchmark/scenarios/l1_sparse_coldstart.js` está intacto:
  `constant-arrival-rate` rate=1 / `timeUnit` 15 min / `duration` 150 min →
  ~11 invocações por runtime (~2h30 por runtime, ~7h30 no total para os 3).
- `benchmark/run/run-lambda.sh` já suporta `LAMBDA_OUTPUT_MODE=raw`, que adiciona
  `--out json=<arquivo>` ao k6 (linha 131-132). Bastaria rodar com esse modo —
  desta vez o raw seria capturado.
- Para garantir cold start em toda invocação: `run-lambda.sh` exige `RESET_URL`
  (ou `ALLOW_UNRESET_L1=true`). Os dados originais mostram que **toda** invocação
  espaçada 15 min foi cold (todas têm `Init Duration`), então o espaçamento sozinho
  já recicla o ambiente; o `RESET_URL` seria só cinto-e-suspensório. Precisa
  confirmar se o endpoint de reset ainda existe no app deployado.
- Custo desprezível (~33 invocações de 512 MB × ~7 s).
- Risco de comparabilidade: seriam cold starts de **setembro/2026**, não de
  julho — versões de runtime da AWS e do snapshot podem ter mudado. O `Init`/
  `Duration` novo pode não bater exatamente com o já publicado. Melhor uso: rodar
  só para capturar a **latência k6** e cruzar com o `Init+Duration` da mesma
  sessão nova, e reportar o resíduo de rede medido — não para substituir os
  números de cold start já validados.

---

## Arquivos gerados nesta investigação

| Arquivo | Conteúdo |
|---|---|
| `analysis/lambda/l1/l1_duration_postinit.py` | extração por janela temporal do `Duration` das 33 invocações |
| `analysis/lambda/l1/l1_duration_postinit.csv` | 1 linha por invocação (request_id, timestamps, init, duration, billed, mem) |
| `analysis/lambda/l1/l1_duration_postinit_summary.json` | agregados por runtime |
| `analysis/lambda/l1/l1_window_probe.py` | diagnóstico: lista todos os cold starts por dia/log group |
| `analysis/lambda/l1/l1_lacuna_dados_auditoria.md` | este documento |
