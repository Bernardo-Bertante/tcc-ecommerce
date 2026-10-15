# Perfil de CPU do contêiner com e sem `validation-query` (24/09/2026)

**Exploratório, fora do desenho oficial.** Nenhum `.tex`/`.md` do projeto principal foi alterado, sem branch.
Continuação de `../NOTAS_pilha_fargate.md` (reconfirmação sob 1 vCPU, 20/09) e de
`../../pg_stat_statements_rds/` (validação de pool = 86% do gap de CPU **do RDS** em F1).

**Pergunta:** os três mecanismos que o profiling de 20/09 atribuiu ao gap de CPU do contêiner (renderização
de SQL, exceção no `PropertyPath`, despacho/`Context` do Reactor) já traziam embutida parte do custo das
validações `SELECT 1`, ou são adicionais a ele? O teste de 20/09 rodou com a validação ligada.

## Setup

Idêntico à reconfirmação de 20/09. **Única mudança:** `-e SPRING_R2DBC_POOL_VALIDATION_QUERY=` (vazia) no
contêiner do Spring Boot.

| item | valor |
|---|---|
| imagens | `pilhaexp-sb:prof` `sha256:2acdf7ee…`, criada 20/09 14:29, **a mesma** usada às 17:23 de 20/09 |
| CPU | `--cpuset-cpus=0-7 --cpus=1`; `cpu.max` lido do cgroup em cada rodada = `100000 100000` (aborta se diferente); JVM `active_processor_count=1` nas 4 rodadas (aborta se diferente) |
| carga | `f1_low_load.js`, 48 iter/s, rampa 60 s + hold 960 s, mix oficial; k6 v0.45.0 nos núcleos 12-15 |
| profiling | async-profiler 4.5, `ctimer` t+120 s/360 s e `wall` t+520 s/360 s, smoke de 10 s com aborto < 50 amostras |
| Postgres | `pilhaexp-pg` (16, núcleos 8-11), o mesmo container |
| classificação | `../analyze.py` importado sem alteração (mesmas categorias self-time) |
| script | `run_one_valcon.sh` = cópia de `../run_one.sh`; o diff está no cabeçalho do arquivo (variável de validação, caminhos, checagem de `cpu.max`, 2 campos a mais no `.meta`) |

**Rodadas** (`run_all_valcon.sh`, ordem de execução): `sbnv-r1`, `sbnv-r2`, `sbval-a1`, `sbnv-r3`.
`sbnv` = sem validação (as 3 pedidas). `sbval-a1` = **âncora acrescentada**: Spring Boot com validação,
exatamente como em 20/09, no mesmo dia e host, para separar o efeito da validação da deriva do host entre 20/09
e 24/09. Quarkus JVM não rodou; o controle são `../results_1vcpu/qj-r{1,2}`.

### Smoke da desativação (antes da coleta)

`smoke_validacao.sh`: `log_statement=all` ligado temporariamente no Postgres local (`ALTER SYSTEM` + reload),
60 s de carga leve em cada condição, contagem de `SELECT 1` no log e depois `RESET` (`log_statement` confirmado
`none` antes das rodadas).

| condição | `SELECT 1` em 60 s | statements totais |
|---|---|---|
| com validação (controle positivo) | 2.585 | 5.180 |
| **sem validação** | **0** | 2.595 |

### Sanidade por rodada (janela de CPU, t+120–480 s)

| rodada | amostras | vCPU profiler | vCPU cgroup | reqs (total) | falhas |
|---|---|---|---|---|---|
| sb-r1 (20/09, com val.) | 6.068 | 0,1686 | 0,1689 | 53.908 | 0 |
| sb-r2 (20/09, com val.) | 5.549 | 0,1541 | 0,1545 | 53.909 | 0 |
| **sbval-a1 (âncora, com val.)** | 6.050 | 0,1681 | 0,1683 | 53.909 | 0 |
| sbnv-r1 | 5.047 | 0,1402 | 0,1405 | 53.564 | 0 |
| sbnv-r2 | 5.637 | 0,1566 | 0,1569 | 53.909 | 0 |
| sbnv-r3 | 5.637 | 0,1566 | 0,1568 | 53.909 | 0 |
| qj-r1 (20/09) | 2.304 | 0,0640 | 0,0643 | 53.114 | 0 |
| qj-r2 (20/09) | 2.237 | 0,0621 | 0,0624 | 53.909 | 0 |

A âncora (0,1681) cai dentro da faixa das duas rodadas de 20/09 (0,1541–0,1686): não há deriva de host
visível. Por isso as 3 rodadas com validação são tratadas como um grupo só (`val3`).

**`sbnv-r1`:** 345 requisições a menos e 309 `dropped_iterations`, **todas em t≈554 s**, dentro da janela
`wall` (520–880 s), fora da janela de CPU. Dentro da janela de CPU a rodada é normal: 19.356 requisições
(as outras têm 19.353–19.358), p99 103 ms, zero descartes. Ela foi mantida; a CPU dela já é mais baixa
em toda a janela de CPU (min 3–8: 0,12–0,15 vCPU, contra 0,14–0,16 em `sbnv-r2`). Os resultados sem ela
estão na coluna "sem r1".

### Calibração dos subsistemas inclusivos

O NOTAS original não guardou o script dos subsistemas. Reconstruído em `compara_valcon.py`, os padrões
reproduzem **exatamente** os oito valores publicados (quatro subsistemas × 8 núcleos e 1 vCPU):

| subsistema | padrão (qualquer frame do stack) | 1 vCPU NOTAS / recalc. | 8 núcleos NOTAS / recalc. |
|---|---|---|---|
| render de SQL | `StatementMapper` | 0,01757 / 0,01757 | 0,01754 / 0,01754 |
| exceção (total) | `fillInStackTrace` | 0,00814 / 0,00814 | 0,00741 / 0,00741 |
| `PropertyPath`/`PropertyReferenceException` | `PropertyPath` | 0,00683 / 0,00683 | 0,00611 / 0,00611 |
| propagação de `Context` | `currentContext\|reactor.util.context` | 0,00504 / 0,00504 | 0,00619 / 0,00619 |

## 1. Gap absoluto de CPU do contêiner

| comparação | SB (vCPU) | QJ (vCPU) | gap | razão |
|---|---|---|---|---|
| com val., 20/09 (valor original) | 0,1613 | 0,0631 | **0,0983** | 2,56× |
| com val., 3 rodadas (20/09 + âncora) | 0,1636 | 0,0631 | **0,1005** | 2,59× |
| **sem val., 3 rodadas** | **0,1511** | 0,0631 | **0,0881** | **2,40×** |
| sem val., sem r1 (2 rodadas) | 0,1566 | 0,0631 | 0,0935 | 2,48× |

| contraste | Δ gap | Δ % |
|---|---|---|
| original (0,0983) → sem val. (3) | −0,0102 | −10,4% |
| com val. 3 rodadas → sem val. 3 rodadas | −0,0125 | **−12,4%** |
| com val. 3 rodadas → sem val. sem r1 | −0,0070 | −7,0% |

Welch no total do SB, 3 × 3: t = −1,73 (df ≈ 4; limiar de 5% ≈ 2,78) — **não significativo**. A diferença
entre as duas rodadas de 20/09 com validação (0,0144 vCPU) é da mesma ordem que o efeito médio (0,0125).

## 2. Decomposição por categoria (self time, `analyze.py`)

Colunas: média das 3 rodadas com validação (`val3`) e das 3 sem (`nv3`); `share` = fração da CPU total do SB;
t de Welch 3 × 3; "prop." = queda que a categoria teria se caísse na mesma proporção que o total (−7,6%).

| categoria | com val. | sem val. | Δ vCPU | Δ % | t | share com → sem | Δ esperado prop. |
|---|---|---|---|---|---|---|---|
| **syscall de rede** | 0,02102 | 0,01743 | **−0,00359** | **−17,1%** | **−5,02** | 12,85% → 11,55% | −0,00160 |
| **driver de banco** | 0,00701 | 0,00533 | **−0,00168** | **−23,9%** | **−4,16** | 4,29% → 3,53% | −0,00053 |
| servidor HTTP (Netty) | 0,01556 | 0,01583 | +0,00027 | +1,7% | 0,34 | 9,51% → 10,49% | −0,00118 |
| plumbing reativo | 0,02146 | 0,01912 | −0,00234 | −10,9% | −2,36 | 13,14% → 12,64% | −0,00164 |
| despacho virtual/interface | 0,01378 | 0,01210 | −0,00168 | −12,2% | −3,47 | 8,43% → 8,01% | −0,00105 |
| jdk_outro | 0,03167 | 0,02915 | −0,00252 | −8,0% | −1,70 | 19,35% → 19,29% | −0,00245 |
| nativo da VM | 0,01066 | 0,00931 | −0,00134 | −12,6% | −1,71 | 6,51% → 6,15% | −0,00081 |
| ORM / mapeador | 0,00819 | 0,00737 | −0,00082 | −10,1% | −1,94 | 5,01% → 4,88% | −0,00062 |
| compilador JIT | 0,01406 | 0,01503 | +0,00097 | +6,9% | 0,70 | 8,59% → 9,91% | −0,00107 |
| **TOTAL** | 0,16358 | 0,15112 | −0,01246 | −7,6% | −1,73 | | |

Por grupo de threads e frames específicos da validação:

| item | com val. | sem val. | Δ % | t |
|---|---|---|---|---|
| thread `reactor-tcp-epoll` (event loop do R2DBC) | 0,10496 | 0,09103 | −13,3% | −3,29 |
| thread `reactor-http-epoll` (servidor HTTP) | 0,04308 | 0,04368 | +1,4% | 0,32 |
| `io.r2dbc.pool.Validation` (inclusivo, só o lado de envio) | 0,00206 | 0,00054 | −73,9% | −10,44 |

(O resíduo de 0,00054 sem validação é o `Validation.validate` em modo `LOCAL`, checagem sem ida ao banco.
A frame só cobre a montagem e o envio: a resposta do `SELECT 1` é processada pelo pipeline genérico do
event loop e cai em syscall/driver/Netty, sem marca da validação no stack.)

**Categorias de rede/socket/driver caem de forma desproporcional:** `syscall de rede` (−17%) e
`driver de banco` (−24%) são as duas únicas categorias com queda relativa bem acima da do total e
estatisticamente distinguível (|t| > 4). Juntas perdem 0,00527 vCPU, contra 0,00213 esperados
por proporcionalidade. A thread do event loop do banco cai 13%, a do HTTP não se move. `servidor HTTP
(Netty)` não cai (+1,7%), mesmo sendo Netty também o transporte do R2DBC.

Como % do gap (contra QJ) as mesmas duas categorias passam de: syscall de rede **4,6% → 1,1%**, driver
de banco **5,5% → 4,3%** (tabela completa em `results/COMPARACAO.txt`, seção 2).

## 3. Os três mecanismos em vCPU absoluto

| mecanismo | com val. (20/09) | com val. (3) | **sem val. (3)** | Δ % (3 vs 3) | t | share do SB com → sem | sem val., sem r1 |
|---|---|---|---|---|---|---|---|
| render de SQL (`StatementMapper`) | 0,01757 | 0,01808 | **0,01680** | −7,1% | −1,29 | 11,05% → 11,12% | 0,01736 (−4,0%) |
| exceção `fillInStackTrace` (total) | 0,00814 | 0,00844 | **0,00735** | −12,9% | −1,73 | 5,15% → 4,86% | 0,00775 (−8,2%) |
| — `PropertyPath` / `PropertyReferenceException` | 0,00683 | 0,00709 | **0,00651** | −8,2% | −1,39 | 4,33% → 4,31% | 0,00678 (−4,4%) |
| plumbing reativo (self) | 0,02168 | 0,02146 | **0,01912** | −10,9% | −2,36 | 13,14% → 12,64% | 0,02004 (−6,6%) |
| despacho virtual/interface (self) | 0,01378 | 0,01378 | **0,01210** | −12,2% | −3,47 | 8,43% → 8,01% | 0,01249 (−9,4%) |
| — `itable stub` (self) | 0,01263 | 0,01265 | **0,01094** | −13,5% | −3,47 | 7,74% → 7,24% | 0,01135 (−10,3%) |
| propagação de `Context` (inclusivo) | 0,00504 | 0,00490 | **0,00453** | −7,6% | −0,93 | 2,99% → 2,99% | 0,00476 (−2,7%) |

Os mesmos mecanismos como % do gap contra QJ:

| mecanismo | % do gap, com val. (20/09; gap 0,0983) | % do gap, sem val. (gap 0,0881) |
|---|---|---|
| render de SQL | 17,9% | 19,1% |
| `PropertyPath` / `PropertyReferenceException` | 6,9% | 7,4% |
| exceção total | 8,3% | 8,3% |
| plumbing reativo (Δ SB−QJ) | 21,1% | 20,6% |
| despacho virtual/interface (Δ SB−QJ) | 11,8% | 11,3% |
| propagação de `Context` (Δ SB−QJ) | 4,7% | 4,7% |

Quarkus JVM segue em 0 para render de SQL e exceção.

**Os valores absolutos mudaram?** Render de SQL, `PropertyPath` e `Context` **não** mudaram de forma
distinguível do ruído: caem 7–8%, menos que a amplitude entre repetições da mesma condição (render de SQL,
por exemplo, varia 0,0022 vCPU entre `sbnv-r1` e `sbnv-r2`), com |t| < 1,4. A fração deles na CPU do SB fica
constante até a 2ª casa (11,05 → 11,12%; 4,33 → 4,31%; 2,99 → 2,99%). Ou seja, acompanham o total da rodada,
não a validação. **Despacho virtual (`itable stub`) e plumbing reativo caem um pouco mais que o total**
(−12% e −11% contra −7,6%; t = −3,5 e −2,4; share −0,4 a −0,5 pp): juntos, 0,00133 vCPU acima do
proporcional, **≈1,3% do gap original**. A exceção total cai 12,9% (t −1,7), mas a parte do Spring Data
(`PropertyPath`) fica estável; a diferença está no restante do `fillInStackTrace`, que inclui a
`OrderNotFoundException` da aplicação.

## 4. Resposta direta

**Os três mecanismos são, na prática, adicionais ao custo da validação.** Sem validação, o gap
do contêiner ainda mostra os três, em magnitude parecida: render de SQL 0,0168 vCPU (antes 0,0176),
`PropertyPath` 0,0065 (antes 0,0068), plumbing reativo + despacho 0,0312 (antes 0,0355). Em % do gap
ficam iguais ou sobem (render 17,9 → 19,1%). Nenhuma das duas hipóteses do enunciado se aplica por inteiro:

- **o gap sem validação não é "bem menor":** cai 12% (0,1005 → 0,0881 vCPU; 7% sem `sbnv-r1`), e essa queda
  não é estatisticamente distinguível do ruído entre repetições (t = −1,73);
- **as três categorias não encolhem proporcionalmente para dar lugar à validação:** render de SQL,
  `PropertyPath` e `Context` mantêm a fração da CPU do SB. Onde a validação estava sendo contada era em
  `syscall de rede` e `driver de banco` (as duas caem 17% e 24%, t −5,0 e −4,2), no event loop do banco e nas
  próprias frames de `io.r2dbc.pool.Validation`. Nenhuma dessas estava entre os três mecanismos.
- **exceção parcial:** no mecanismo "despacho de interface/Reactor", uma parcela pequena
  (~0,0013 vCPU, ≈1,3% do gap original) cai além do proporcional e é compatível com tráfego de validação
  passando pela cadeia de operadores do Reactor.

Nota factual, sem interpretação: no contêiner, a validação responde por no máximo ~12% do gap de CPU
(melhor estimativa de 7% a 12%, não significativa). Em `pg_stat_statements_rds/`, no RDS, ela respondia por 86%
do gap de CPU do **banco**. As duas medidas são de componentes diferentes.

Latência k6 local, como observação lateral (execução inteira, não a janela): p50 SB com val. 4,50 ms
(média de 3), sem val. 4,01 ms, QJ 2,62 ms.

## Arquivos

| arquivo | conteúdo |
|---|---|
| `smoke_validacao.sh` | smoke da desativação com controle positivo; saída em `results/smoke-val*.{pg.log,k6.log}` e `results/smoke-val.resumo.txt` |
| `run_one_valcon.sh` | cópia de `../run_one.sh` + variável de validação e checagem de `cpu.max` |
| `run_all_valcon.sh` / `run_all_valcon.log` | driver (desacoplado, `systemd-inhibit`) e log |
| `compara_valcon.py` | comparação; importa `../analyze.py`; saída completa em `results/COMPARACAO.txt` |
| `results/{sbnv-r1,sbnv-r2,sbnv-r3,sbval-a1}.*` | mesmo conjunto por rodada do teste original (`.jfr`, `.collapsed`, `.html`, `.cpu.tsv`, `.k6.csv.gz`, `.meta`, logs) |
