# Notas de execução — teste exploratório de nível JIT no Fargate

**Exploratório, fora do desenho experimental oficial.** Nada daqui é dado oficial do TCC.
Nenhum `.tex`, guia ou recurso oficial foi ou será alterado. Horários em UTC−3 (local) salvo indicação.

## 29/09/2026 — Fase A1/A2 (reconhecimento, somente leitura)

18:11 — `aws sts get-caller-identity --profile pessoal` → conta `776648109551` (confere).

### Estado da conta (leitura)

- Nenhum recurso `exp-jit-*`, `exp-lazy-*`, `pgss-*` ou `repro-*` em ECS, EC2, IAM, logs, Secrets
  Manager ou S3. A infraestrutura da reprodução de F2/F3 (setembro) foi apagada em 24/09
  (`analysis/pg_stat_statements_rds/f2_f3/02_teardown.md`); **não há o que reaproveitar**.
- Nenhuma EC2 ligada. Único cluster ECS: `order-service-cluster` (oficial).
- Cotas: EC2 On-Demand Standard 32 vCPU; Fargate On-Demand 30 vCPU. Sub-rede `subnet-09021fc5dd37000fc`
  (us-east-1c): 4.091 IPs livres. Folga ampla para este teste (2 vCPU EC2 + 1 vCPU Fargate) e o de lazy.
- ECS account setting `defaultLogDriverMode = non-blocking` (vale para as task defs oficiais, que não
  declaram `mode`). Ver A5.

### Task definitions oficiais vigentes

| | `order-service-springboot:12` | `order-service-quarkus-jvm:10` |
|---|---|---|
| imagem | `order-service-springboot:latest` → hoje `sha256:276548dd…` (push 21/06/2026) | `order-service-quarkus-jvm:20260616-160138` → `sha256:abec3583…` |
| CPU / memória | 1024 / 2048 | 1024 / 2048 |
| porta | 8081 | 8081 |
| env (nomes) | SERVER_PORT, SPRING_R2DBC_{URL,USERNAME,PASSWORD,POOL_INITIAL_SIZE,POOL_MAX_SIZE}, SPRING_FLYWAY_{URL,USER,PASSWORD} | SERVER_PORT, QUARKUS_DATASOURCE_{REACTIVE_URL,REACTIVE_MAX_SIZE,USERNAME,PASSWORD,JDBC_URL,REACTIVE_POSTGRESQL_SSL_MODE,REACTIVE_TRUST_ALL} |
| pool | 40 (initial 15) | 40 |
| log | awslogs `/ecs/order-service-springboot`, sem `mode` | awslogs `/ecs/order-service-quarkus-jvm`, sem `mode` |
| execution role | `ecsTaskExecutionRole` (oficial) | idem |
| task role | nenhuma | nenhuma |

As oficiais têm a senha do banco em texto nas variáveis de ambiente. As `exp-jit-*` **não** repetem
isso: a senha do RDS novo vai por `secrets` (Secrets Manager). A senha oficial não foi copiada.

### Como a JVM recebe flags

Imagem base das duas: `ubi9/openjdk-21-runtime:1.24`, ENTRYPOINT `run-java.sh`, OpenJDK 21.0.11
(Red Hat). Flags extras entram por `JAVA_OPTS_APPEND`. A imagem do Quarkus já define
`JAVA_OPTS_APPEND=-Dquarkus.http.host=0.0.0.0`; como a variável da task def substitui a da imagem, o
valor precisa ser repetido. Linha de comando real nos logs oficiais (CloudWatch):

- SB: `java -XX:MaxRAMPercentage=80.0 -XX:+UseParallelGC -XX:MinHeapFreeRatio=10 -XX:MaxHeapFreeRatio=20 -XX:GCTimeRatio=4 -XX:AdaptiveSizePolicyWeight=90 -XX:+ExitOnOutOfMemoryError -cp "." -jar /deployments/app.jar`
- QJ: idem + `-Dquarkus.http.host=0.0.0.0` antes de `-cp`.

Nenhuma flag de compilação nos oficiais. As imagens trazem `jcmd` (conferido localmente com `docker run`).

### RDS oficial

`order-service-postgres`: db.t3.micro, PG 16.4, 20 GB gp3 (3000 IOPS / 125 MB/s), us-east-1d,
público, subnet group `default` (VPC default `vpc-03a62cf829e1ed006`), SG `sg-092b010799f56134f`,
sem backup, sem criptografia, sem PI. Parameter group `order-service-pg16-custom`, valores
definidos pelo usuário: `max_connections=100`, `work_mem=16384`.

### Esquema e Flyway

O esquema oficial foi criado fora do Flyway: `flyway_schema_history` só tem a linha
`<< Flyway Baseline >>`. As duas imagens carregam `db/migration/V1__create_order_tables.sql` (4.321 bytes)
e usam `baseline-on-migrate=true`. Receita validada em setembro (reprodução F2/F3): carregar
`analysis/reproducao_f3_instabilidade/esquema_oficial_schema_only.sql` + inserir a linha de baseline.
A linha exata não foi guardada em lugar nenhum (repo e backups S3 conferidos; os `db.env` dos
tarballs não foram abertos por conterem senha). Será reconstruída no formato padrão do Flyway
(versão `1`, tipo `BASELINE`); critério de aceitação no teste de fumaça: as duas apps sobem e o
Flyway valida "2 migrations", como no log oficial do QJ de 02/09/2026.

### Protocolo oficial e carga (lido nos scripts)

- Por rodada: `stop-task` → `run-task` fresca → health → `TRUNCATE order_status_history, order_items, orders` → k6
  (`benchmark/run/f1_rerun.sh`, `f3_rerun.sh`).
- F2-S (`09-scripts.md`, `bloco_f2s.sh`): `TRUNCATE` + `popular_orders_summary.sql` (50.000 linhas) +
  `count(*) = 50000`; `F2S_RATE=8`; cenário `f2s_summary_only.js` (30 s / 13 min / 30 s, VUs 50/150).
- F1: `F1_RATE=48`, 2m/20m/2m, VUs 80/200. F2: 48→96, 10m/90s/30m/3m, VUs 800/1500.
  F3: 48/240/48, 5m/2m/10m/2m/5m/1m, VUs 1500/3000.
- Cenários: `benchmark/scenarios` + `benchmark/lib` do HEAD (último commit que os toca: `6b90310`),
  os mesmos das re-coletas de F1 (31/08) e F3 (06/09).
- A mistura tem o tag `operation=get_summary`, o que permite contar as chamadas do summary no tempo.

### A2 — caminho do `GET /orders/summary`

Gravado em `summary_path_springboot.txt` e `summary_path_quarkus.txt` (padrões `Classe::método`,
com camada, certeza e se o método é exclusivo do summary). Lido do código-fonte e conferido nos
jars das imagens oficiais (invoker gerado `OrderResource$quarkusrestinvoker$getSummary_55c945ab…`,
proxies Arc, codecs do driver). `getSummary` não tem interceptador em nenhuma das versões.

## 29/09/2026 — A3 aprovado; ajustes pedidos (a)–(g)

Aprovado pelo Bernardo: criar tudo novo com `exp-jit-`, incluir jcmd via ECS Exec, plano/custo/teardown.
Ajustes: (a) pushedAt vs coletas; (b) `jcmd 1 VM.command_line` pelo ECS Exec nas duas imagens no fumaça;
(c) jcmd só após o k6 e antes de parar a task, `Compiler.codelist` bruto no S3; (d) listas do summary
usadas pelo parser no fumaça; (e) SSM em vez de porta 22; (f) imageDigest/ARN/startedAt por rodada;
(g) Fase C começa listando as tasks do `exp-jit-cluster`.

### (a) Data de publicação das imagens (ECR `imagePushedAt`)

| imagem | digest (índice) | pushedAt (UTC−3) |
|---|---|---|
| `order-service-springboot:latest` | `sha256:276548dd…` | 2026-06-21 15:36:08 |
| `order-service-quarkus-jvm:20260616-160138` | `sha256:abec3583…` | 2026-06-16 16:10:00 |

Coletas oficiais: F1 original 06/07, F2 07/07, F3 13/07 (julho), F2-S 10/08, re-coleta F1 31/08,
re-coleta F3 02–06/09 — todas depois dos dois pushes. CloudTrail `PutImage` desde 2026-07-01 (início da
janela de 90 dias): **nenhum evento** nos dois repositórios. Nenhuma das duas imagens foi reconstruída
ou re-tagueada depois das coletas (o `:latest` não foi movido dentro da janela do CloudTrail; antes de
01/07 só há o push de 21/06, anterior a todas as coletas).

### Teste local (Docker, antes da AWS)

- Postgres 16.4 local + esquema oficial + baseline: o dump tem `SET transaction_timeout` (pg_dump 17),
  rejeitado pelo PG 16.4 com `ON_ERROR_STOP`. Criada cópia `db/esquema_pg16.sql` sem essa linha (resto
  idêntico). SB subiu com "Successfully validated 2 migrations" / "Schema public is up to date", igual ao
  log oficial.
- `jcmd 1 VM.command_line` (root e usuário `default`): `jvm_args` = flags oficiais + `-XX:+PrintCompilation`
  (SB e QJ). `Compiler.codelist` funciona (formato `id nível estado método(assinatura) [endereços]`).
- 18:59:37 — **incidente local**: algo externo à sessão emitiu `docker stop` nos contêineres
  `expjit-pg` e `expjit-sb` (eventos `kill 15`, `kill 9`, `stop`). Não fui eu; possivelmente outra sessão.
  O log daquele contêiner ficou com duas JVMs. Refeito com contêineres novos; o parser passou a contar
  JVMs por log (`jvms_no_log`).
- Parser (`runner/analisa_jit.py`), 6.000 chamadas ao summary a 1 CPU: SB 1.812 métodos no nível 4 pelo
  log = 1.812 pelo jcmd; QJ 1.051 (log, até o fim da carga) vs 1.056 (jcmd, segundos depois).
  1 linha corrompida por rodada (PrintCompilation escreve a linha em vários `write()`; o logback da app
  intercala), que é o único id do codelist ausente do log.
- **Calibração:** sem nenhuma perda de log, faltam ids na sequência (SB 1.333 de ~15,6 mil; QJ 279 de
  ~8,2 mil) — tarefas descartadas da fila de compilação não imprimem linha. Lacuna de id não mede perda;
  a prova é o codelist.
- Correção no parser: wrappers nativos (`(native)`, nome com assinatura) não casavam com a regex.
- Leitura a registrar: métodos pequenos chamados só de dentro de um método compilado (ex.:
  `OrderResource::getSummary`, chamado pelo invoker gerado) podem aparecer "não compilados" por estarem
  inlined no chamador, não por estarem interpretados.

### Infraestrutura criada (19:05–19:20, UTC−3) — inventário em `inventario_recursos.txt`

- Senha do RDS: `secretsmanager get-random-password` direto para `create-secret`; passada ao
  `create-db-instance` por substituição de comando; nunca impressa nem gravada.
- Task defs geradas por `jq` das oficiais, removendo as variáveis `*_PASSWORD` antes de gravar. Diff
  contra as oficiais (sem valores de senha) em `taskdefs/taskdef_diff_*.txt`: só host do banco, imagem
  por digest, `JAVA_OPTS_APPEND`, log group + `mode`/`max-buffer-size`, `secrets`, execution/task role.
- Runner sem par de chaves e sem ingress; acesso só por SSM (`send-command`). IP público 100.61.149.250,
  liberado só na 8081 do `exp-jit-task-sg`.
- RDS `exp-jit-postgres` available em us-east-1d. Esquema carregado do runner: 4 tabelas, 10 índices,
  baseline versão 1, PG 16.4, `max_connections=100`, `work_mem=16MB`.
- Cenários k6: cópia inalterada de `benchmark/scenarios` e `benchmark/lib` (HEAD `6b90310`) em `bench/`
  (`diff -r` vazio).
- ~19:22 o VS Code travou no meio da escrita do `teardown.sh` (nada foi executado nesse intervalo);
  retomado em seguida.
- No SSM aparece também `i-0598e47669b1414b0`, que não é deste teste (provavelmente do teste de lazy); não tocado.

## 29/09/2026 — Teste de fumaça (A9) e lançamento (horários UTC)

**smoke** (22:29–22:42Z), `run_all.sh smoke "f2s:springboot f1:quarkus-jvm"`, via `systemd-run`:
- SB/F2-S interrompido aos 240 s (k6 rc=124 do `timeout`, esperado); TRUNCATE + 50.000 linhas conferidas;
  18.300 eventos de log, 1 JVM; imageDigest `276548dd…`, startedAt 22:29:50Z.
- **ECS Exec falhou no SB**: `AccessDeniedException ... ecs:ExecuteCommand on resource ...:cluster/exp-jit-cluster`
  — a política só dava o ARN das tasks. Corrigido às 22:35Z (statement `EcsExecExpJit` com cluster + tasks,
  `iam/runner-inline.json`). Não houve jcmd nessa rodada.
- QJ/F1 encurtado (30s/2m/30s, só no fumaça): jcmd pelo ECS Exec OK — `jvm_args` = oficiais +
  `-Dquarkus.http.host=0.0.0.0 -XX:+PrintCompilation`; `VM.flags`: `CICompilerCount=2`, sem `TieredStopAtLevel`;
  codelist 9.392 entradas; log 1.532 métodos n4 vs jcmd 1.530.
- Teardown em ensaio: 0 tasks RUNNING, logs confirmados no S3, RDS/cluster/EC2 não tocados.
- Achado no parser: a linha de log da app pode cair no meio da linha do PrintCompilation. Dois formatos:
  (i) "órfã" (uptime antes, resto da linha depois, com id/nível/método íntegros) — uptime estimado pelo
  timestamp do evento; (ii) linha cortada cujo resto chega no evento seguinte — recombinada (prefixo até o
  timestamp da app + evento seguinte). Depois disso: 0 linhas não parseadas e **0 ids do codelist ausentes
  no log** nos 4 conjuntos (2 locais, 2 do fumaça).

**smoke2** (22:43–22:49Z), só SB/F2-S (150 s), para cumprir o ajuste (b) no SB depois da correção de IAM:
jcmd pelo ECS Exec OK — `jvm_args` = oficiais + `-XX:+PrintCompilation`; `CICompilerCount=2`; codelist
12.384 entradas, 0 ausentes no log; log 1.811 métodos n4 vs jcmd 1.802 (jcmd segundos depois do fim da carga).

Observação: no Fargate (1 vCPU) faltam poucos ids (SB 39–79, QJ 11) contra ~1.300 no teste local
(contêiner com `--cpus=1`, mas a JVM enxergava 6 CPUs e usava mais threads de compilação).

**Lançamento (Fase B)**: 22:49:04Z, `systemd-run --unit exp-jit-driver run_all.sh full` com o plano
F1 (SB, QJ) → F2 → F2-S → F3, pausa de 120 s. Primeira carga (F1/SB) às 22:50:06Z.
Cronômetros: `exp-jit-failsafe.timer` no runner (07:49:03Z → teardown completo) e EventBridge Scheduler
`exp-jit-failsafe-rds`/`-ec2` (08:19Z → apaga o RDS e termina a EC2, independentemente do runner).
Risco declarado: o formato de entrada do alvo universal do Scheduler (`DbInstanceIdentifier`) não pôde ser
testado sem disparar; é a terceira camada, depois do teardown do driver e do timer do systemd.

## 30/09/2026 — Fase C

- 08:13Z — (g) `ecs list-tasks --cluster exp-jit-cluster`: cluster INACTIVE, 0 tasks. Sem task órfã.
- `DONE` = "todas as rodadas ok" (8/8); sem `FAILED`. Teardown do driver 03:04–03:06Z: RDS apagado, cluster
  INACTIVE, schedules do Scheduler apagados, EC2 desligada (terminada; `describe-instances` já não a lista).
  Nenhum volume `exp-jit`. RDS oficial `available`/`in-sync`; `order-service-springboot:12` ACTIVE.
- Defeito cosmético no `STATUS`: a lista de sobras omitiu as task defs `exp-jit-*` porque
  `list-task-definitions --family-prefix` exige o nome completo da família. Elas existem (ACTIVE).
- Resultados baixados para `fase_b/` (258 MB). Validação: 1 JVM por log; codelist ausentes no log 0 (6 rodadas) e
  1 (F3/SB, F3/QJ); 3 linhas de boot não recuperáveis; carga igual à oficial (summary.json).
- `RESULTADOS_JIT_FARGATE.md` escrito. Tabelas geradas direto dos CSVs.
- Sobram, a apagar só com aprovação: task defs `exp-jit-springboot:1`/`exp-jit-quarkus-jvm:1`, 3 SGs, 4 roles IAM +
  instance profile, secret `exp-jit-db`, param group `exp-jit-pg16`, schedule group `exp-jit`, log groups
  `exp-jit-*` (expiram em 14 d), bucket `exp-jit-results-776648109551` (já copiado para `fase_b/`).

## 30/09/2026 — Backup e limpeza final (aprovados pelo Bernardo)

- Backup: `analysis/exploratorio/jit-fargate/` → `s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/jit-fargate/`
  (184 arquivos, 269.417.403 bytes, iguais aos locais). Nenhuma senha real nos arquivos (grep: só nomes de
  variáveis `*_PASSWORD`, texto e nomes de métodos).
- Apagados: task defs `exp-jit-springboot:1`/`exp-jit-quarkus-jvm:1` (deregister + delete), SGs `exp-jit-rds-sg`,
  `exp-jit-task-sg`, `exp-jit-runner-sg`, param group `exp-jit-pg16`, schedule group `exp-jit`, log groups
  `exp-jit-springboot`/`exp-jit-quarkus-jvm`, secret `exp-jit-db` (sem janela de recuperação), roles
  `exp-jit-runner-role` (+ profile), `exp-jit-task-exec-role`, `exp-jit-task-role`, `exp-jit-scheduler-role`,
  bucket `exp-jit-results-776648109551`.
- Varredura final: nenhum recurso `exp-jit-*` em EC2, RDS, SG, EBS, logs, IAM, S3, Secrets, Scheduler, ECS.
  A API de tags ainda lista, como entradas antigas do índice, a EC2 terminada, o cluster INACTIVE e as 2 task defs
  em DELETE_IN_PROGRESS (somem sozinhas).
- Oficiais conferidos: `order-service-postgres` available / `order-service-pg16-custom` in-sync; task defs
  `order-service-springboot:12`, `-quarkus-jvm:10`, `-quarkus-native:9` ACTIVE; `order-service-cluster` ACTIVE;
  SGs `default`, `order-service-fargate-sg`, `k6-runner-sg` existem e não foram alterados.
