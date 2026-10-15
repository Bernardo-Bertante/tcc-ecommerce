# Teardown F2/F3 — 24/09/2026, 04:41–04:43Z

Tudo de `inventario_recursos.txt` apagado: RDS `pgss-f2f3-postgres` (sem snapshot final), parameter group
`pgss-f2f3-pg16`, runner `i-03872601bfa459888` + volume, cluster `pgss-f2f3-cluster`, 3 task definitions,
3 regras de SG (só as descritas `pgss-f2f3`; os SGs oficiais ficaram), log groups `/ecs/pgss-f2f3-*`,
Container Insights do cluster e `/aws/rds/instance/pgss-f2f3-postgres/postgresql`, roles
`pgss-f2f3-runner` (+ instance profile) e `pgss-f2f3-rds-monitoring`.

Também removido: o stream `RDSOSMetrics/db-6YS6HH4RVDLLF3GYEWRKEPPNEA`, do RDS da coleta 3, que
reapareceu depois do teardown de 23/09 (provavelmente eventos entregues com atraso). `RDSOSMetrics`
ficou vazio; o RDS oficial está com Enhanced Monitoring desligado.

Conferido depois: `order-service-postgres` `available` / `in-sync` com `order-service-pg16-custom`;
`order-service-cluster` intacto; nenhum recurso `pgss`/`repro` em IAM, logs, ECS, EC2 ou regras de SG.
O grupo oficial `order-service-pg16-custom` nunca foi alterado.

Backup antes de apagar, em `s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds/`:
`f2_f3/{f2,f3}/r*/` (incluindo 12 `k6_raw.json.gz`, 354 MB, e `requests.csv.gz`), `f2_f3/runner_disco_20260924.tgz`,
e `analysis/` (espelho desta pasta). Perdidos: Performance Insights e Enhanced Monitoring (os valores
usados estão em `resultados/`).
