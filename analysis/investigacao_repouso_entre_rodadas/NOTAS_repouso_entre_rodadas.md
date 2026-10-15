# Repouso real entre rodadas: F1, F2, F3 (Fargate)

21/09/2026. Verifica o "intervalo mínimo de 30 min entre repetições" que aparece em
`metodologia.tex` §3.1 e `discussao.tex` §6.7 comparando com os scripts e os timestamps.
Não altera nenhum .tex/.md do texto. Reproduzir: `python3 repouso_real.py` (nesta pasta).

## Resposta curta

| Cenário oficial | Script que rodou | Pausa programada entre rodadas | Repouso real do RDS (carga→carga) |
|---|---|---|---|
| F1 (re-coleta 31/08) | `benchmark/run/f1_rerun.sh` (blob `9b07a92`, = commit `08473e0` = HEAD) | **nenhuma** | **57–100 s** |
| F3 (re-coleta 02–06/09) | `benchmark/run/f3_rerun.sh` (02/09: blob `c4a7fb4`, não commitado; 05–06/09: blob `713bedb`, = commit `6b90310`) | **nenhuma** | **133–176 s** (+1×485 s, +1×3515 s por interrupção) |
| F2 (jul, 06–14/07) | `/tmp/bloco_fargate.sh` (efêmero) + `sleep 1800` **digitado à mão** entre blocos | nenhuma dentro do bloco; 30 min pretendidos entre blocos | **~65–105 s** após o F1 do mesmo bloco |

Nenhum cenário oficial teve 30 min de repouso **imediatamente antes da carga medida**,
F2 incluído. Os 30 min existiram só entre **blocos** de julho (um bloco = F1→F2→F3 da
mesma runtime/rodada), eram digitados no terminal (não ficavam no script) e na prática
variaram de 6 min a horas.

## 1. Scripts das re-coletas: sem pausa entre rodadas

Nenhum dos dois scripts tem sleep/wait de repouso. Os únicos `sleep` estão em
`fresh_task()` e são tempos de orquestração da task, não repouso:

`benchmark/run/f1_rerun.sh`
- l.245 `sleep 8` (após `stop-task` da task anterior)
- l.252 `sleep 20` (após `run-task`), depois l.253 `aws ecs wait tasks-running`
- l.262 `sleep 5` (dentro do loop de health, até 24 tentativas)
- Loop principal l.387–399: `fresh_task` → `truncate_db` → `run_k6`, **sem nada entre
  as iterações**; a troca de runtime (l.400–403) só faz `stop-task`.

`benchmark/run/f3_rerun.sh`
- l.288 `sleep 8`, l.295 `sleep 20`, l.305 `sleep 5`: as mesmas três chamadas
- Loop principal l.529–549: idêntico ao do F1, sem pausa.

Nenhuma variável de repouso (`REST_SECONDS`/`VERSION_REST_SECONDS`) existe nesses dois
scripts. Essas variáveis estão só em `run-fargate.sh`/`run-lambda.sh`, que **não** foram
usados nas coletas oficiais.

**A versão que rodou é a que está no git?** Sim para o F1: `runner_script.git_blob_sha`
dos 15 meta.json = `9b07a92ae1` = `git rev-parse 08473e0:benchmark/run/f1_rerun.sh`.
No F3, as 10 rodadas de 02/09 gravaram blob `c4a7fb4093`, que não está no repositório
(o script só foi commitado em 05/09, `6b90310`). As 5 de 05–06/09 gravaram `713bedb2ab`,
o blob commitado. O conteúdo de `c4a7fb4` não é recuperável, mas os repousos de 02/09
(133–176 s) têm a mesma ordem de grandeza dos de 05/09 (155–170 s). Isso descarta
qualquer pausa longa naquela versão. Não há `sleep 1800` em nenhum transcript de sessão.

## 2. O CSV mede o repouso corretamente

`analysis/fase5_rds_cpu_por_rodada.py` l.134–144:
```python
d["_start"] = parse(d.get("load_start_utc") or d["start_utc"])
d["_end"]   = parse(d.get("load_end_utc")   or d["end_utc"])
...
rest = (d["_start"] - prev_end).total_seconds() if prev_end else np.nan
```
A coluna `descanso_antes_s` é o início da carga da rodada menos o fim da carga da rodada
anterior, com as metas de F1 e F3 ordenadas juntas por tempo. É exatamente o intervalo
sem carga no RDS, então mede o que precisa medir. Não há sleep programado que esteja sendo
mascarado. Composição do intervalo, que é todo orquestração:
- F3: fim do k6 → scp/meta → `stop-task` + 8 s + `run-task` + 20 s + wait + health →
  TRUNCATE → **init do k6 (~131–146 s entre a invocação e o 1º request**, com 1500 VUs
  pré-alocados; `load_start_utc − k6_invoke_utc` nos meta.json). A maior parte do
  repouso do F3 vem do init do k6.
- F1: `start_utc`/`end_utc` envolvem o ssh do k6 inteiro, incluindo o init e a extração
  de latência. O repouso real é ≥ 57–100 s.
- Detalhe: no F3, `load_*` usa o relógio do runner e `k6_*` o relógio local. O runner
  estava ~1 min adiantado (`load_end_utc` > `k6_return_utc`). O cálculo usa só `load_*`,
  então o resultado continua coerente.

Exceções do F3:
- springboot r1→r2 (485 s): o `k6_return` de r1 veio 4 min 21 s depois do fim da carga,
  contra −55 s nas outras rodadas. Houve lentidão no pós-processamento/scp dessa rodada,
  não uma pausa programada.
- springboot r3 → quarkus-jvm r1 (3515 s, não citado no pedido): a sessão de 02/09 parou
  depois do springboot r3 (r4/r5 só rodaram em 05/09) e foi retomada ~58 min depois
  com outra runtime.

## 3. F2 (julho): de onde vêm os 30 min

`bloco_fargate.sh` vivia em `/tmp` e se perdeu. O esqueleto está em
`~/Documentos/tcc/files/09-scripts.md` l.7–75 e roda F1→F2→F3 de uma runtime/rodada em
sequência, sem pausa:
```bash
IP=$(fresh_task); truncate_db; run_k6 "f1" ...
IP=$(fresh_task); truncate_db; run_k6 "f2" ...
IP=$(fresh_task); truncate_db; run_k6 "f3" ...
```
Os 30 min ficavam **fora** do script. Estavam no terminal, entre um bloco e o seguinte
(`~/.bash_history`, sem credenciais transcritas aqui):
```
19  echo "Aguardando 30min — disparar R5 às ..."
20  sleep 1800
21  nohup /tmp/bloco_fargate.sh "springboot" "5" ...
55  sleep 1800   → quarkus-jvm r4
80  sleep 18     → quarkus-jvm r5   (echo diz 30min; sleep de 18 s)
105 sleep 1800   → quarkus-native r4
131 sleep 10     → quarkus-native r5 (echo diz 30min; sleep de 10 s)
```
O histórico só cobre as rodadas 4–5. É daqui que vem o "confirmado via script real,
`sleep 1800`" registrado em `11-plano-redacao-tcc_11_.md` l.68.

Pelos timestamps (RunTask do CloudTrail, `analysis/fase5/runtasks_july.json`, 15 blocos;
início da carga ≈ RunTask + PRE_K6, erro de ±1 min):

| | repouso antes do F2 (após F1) | antes do F3 (após F2) | entre blocos (F3 anterior → F1) |
|---|---|---|---|
| 15 blocos | **65–105 s** | **149–208 s** | 6 min – dias (32, 35, 38, 44, 51, 58, 74, 107, 118, 134, 137 min…) |

O F2 de julho nunca teve 30 min de repouso antes da carga. Ele sempre começou ~1–2 min
depois de 24 min de F1. O F3 de julho vinha ~2,5 min depois de 44,5 min de F2. Quem
ficava depois dos 30 min era o F1 de cada bloco. Mesmo esse intervalo não era garantido:
quarkus-jvm r4→r5 teve 6 min (`sleep 18`). quarkus-native r4→r5 teve 35 min, mas com
`sleep 10`; a espera real foi a demora em digitar o comando.

## 4. Por que a metodologia diz 30 min para os três

1. **Origem:** o `sleep 1800` manual de julho foi entendido como "30 min entre
   repetições de F1/F2/F3". Na verdade, era a pausa entre **blocos** F1+F2+F3, não entre
   repetições de um mesmo cenário. Dentro do bloco, F2 e F3 rodavam 1–3 min depois do
   cenário anterior. Por construção, o texto já não valia para F2 e F3 nem em julho.
2. **Não atualizado:** `f1_rerun.sh` e `f3_rerun.sh` (31/08 e 02–05/09) se descrevem
   como "metodologia idêntica ao bloco_fargate.sh original" (l.10 e l.17). Isso é
   verdade: o bloco nunca teve pausa interna. Só que as rodadas passaram a ser
   encadeadas direto, sem o `sleep 1800` manual, e §3.1 continuou com o valor de agosto.
3. **Justificativa:** o contraste "RDS 90–98 % sem descanso vs 64–65 % com descanso"
   (§6.7, via `11-plano` l.71) vem de `08-known-problems.md` §2. Lá o problema descrito
   é **"task suja"** (task Fargate reaproveitada por horas), e a solução foi o protocolo
   de task fresca, não repouso do RDS. Nos dados oficiais, o F3 peak ficou estável entre
   rodadas (DP ≤ 1,6 p.p., `fase5_rds_cpu_por_rodada_NOTAS.md` l.77–82) com repouso de
   ~2–3 min. Chamar o intervalo de "indispensável" e sua justificativa de "correta desde
   a implementação inicial" não tem suporte nos dados oficiais.

## Valores para corrigir o texto (sugestão, não aplicada)

- F1: sem pausa programada; ~1–1,5 min entre o fim de uma carga e o início da próxima
  (troca de task + TRUNCATE + init do k6).
- F3: sem pausa programada; ~2–3 min (o init do k6 com 1500 VUs responde por ~2,4 min).
- F2 (julho): sem pausa programada antes da carga. O F2 vinha ~1–2 min após o F1 do
  mesmo bloco. Entre blocos houve pausa manual pretendida de 30 min, cumprida de forma
  irregular (6 min – horas).
