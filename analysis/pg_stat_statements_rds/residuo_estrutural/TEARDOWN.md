# Teardown — 24/09/2026, ~17:10Z

Tudo de `inventario_recursos.txt` apagado:

| recurso | ação |
|---|---|
| RDS `pgss-res-postgres` | apagado (`--skip-final-snapshot --delete-automated-backups`) |
| parameter group `pgss-res-pg16` | apagado depois do RDS. O grupo oficial `order-service-pg16-custom` nunca foi alterado |
| EC2 `i-04ed1220339138fd6` (runner) + volume | terminado (volume com DeleteOnTermination) |
| task defs `pgss-res-springboot-noval:1`, `pgss-res-quarkus-jvm:1` | desregistradas e apagadas |
| cluster ECS `pgss-res-cluster` | apagado (sem tasks rodando) |
| regras de SG `sgr-0c1fb5746fbcac80a`, `sgr-0d7decca6304060e0` (default), `sgr-0fb2ec514cfc620b7` (k6-runner-sg) | revogadas; os SGs oficiais ficaram |
| log groups `/ecs/pgss-res-springboot`, `/ecs/pgss-res-quarkus-jvm` | apagados. O RDS não tinha export de log nem EM/PI, então não criou outros |
| IAM role `pgss-res-runner` + instance profile + política inline | apagados |

Conferido depois: só `order-service-postgres` (`available`, `in-sync`) e `order-service-cluster` existem;
nenhuma EC2 com a tag `tcc-pgss-residuo`, nenhuma role `pgss*`, nenhum log group `pgss-res`.

Backup antes de apagar: `s3://tcc-ecommerce-backup-776648109551-us-east-1/exploratorio/pg_stat_statements_rds/residuo_estrutural/`
(`analysis/` = esta pasta, incluindo `dados/logs_brutos/`; `runner_disco_20260924.tgz` = `~/res` do runner).
