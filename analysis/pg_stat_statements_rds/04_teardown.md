# Teardown — 23/09/2026, 16:40–16:45Z

Tudo o que foi criado para esta investigação **e** para a `reproducao_f3_instabilidade`
(tag `projeto=tcc-repro-f3`, pendente desde 22/09) foi apagado.

| recurso | ação |
|---|---|
| RDS `repro-f3-postgres` | apagado (`--skip-final-snapshot --delete-automated-backups`), 16:44:32Z. O Performance Insights dele se foi junto. |
| parameter group `repro-f3-pg16-autoexplain` | apagado. **O grupo oficial `order-service-pg16-custom` nunca foi alterado**, então não havia nada a reverter nele. |
| EC2 `i-095b252567fbdadfb` (runner) + volume 30 GB | terminado; volume removido junto |
| task defs `repro-f3-springboot:1`, `repro-f3-quarkus-jvm:1`, `repro-f3-springboot-noval:1` | desregistradas e apagadas |
| cluster ECS `repro-f3-cluster` | apagado |
| VPC flow log `fl-063474c25955b4dd3` | apagado |
| regras de SG `sgr-0c9766427f9d3acb7`, `sgr-0005fee7f0c178113`, `sgr-0eb09fbe6efc7d16f` | revogadas (só essas; os SGs em si são oficiais e ficaram) |
| log groups `/ecs/repro-f3-*`, `/repro-f3/vpc-flow-logs`, `/aws/ecs/containerinsights/repro-f3-cluster/performance`, `/aws/rds/instance/repro-f3-postgres/postgresql` | apagados |
| stream `RDSOSMetrics/db-6YS6HH4RVDLLF3GYEWRKEPPNEA` | apagado (o RDS oficial está com Enhanced Monitoring desligado; era o único stream) |
| IAM roles `repro-f3-runner`, `repro-f3-flowlogs`, `repro-f3-rds-monitoring` + instance profile | apagados (com as políticas inline, inclusive a `s3pgss` criada nesta investigação) |

Conferido depois: `order-service-postgres` `available`, param group `order-service-pg16-custom`
`in-sync`; cluster `order-service-cluster` intacto.

## Backup antes de apagar

`s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds/`:
- `analysis/` — espelho desta pasta (259 arquivos)
- `runner_disco_completo_20260923.tgz` — `~/pgss`, `~/pgss2`, `~/pgss3` e `~/repro` do runner,
  inclusive o `orquestrador.log` do dia 2 da reprodução do F3, que só existia no disco do runner

Não recuperável depois do teardown: dados do Performance Insights e do Enhanced Monitoring
(os valores de EM usados na análise estão salvos em `coleta3/resultados/` e `coleta2/resultados/`).
