# Estado da infraestrutura antes de iniciar (verificação do item 1) — 22/09/2026

**Conclusão: o teardown de `analysis/reproducao_f3_instabilidade/` NÃO foi feito.** Todos os recursos
com a tag `projeto=tcc-repro-f3` continuam existindo. Eles estão **parados**, não apagados — o autostop
do orquestrador executou `rds stop-db-instance` + `shutdown -h now`, que param mas não removem.

## Inventário conferido na conta 776648109551 / us-east-1 (`--profile pessoal`)

| recurso | estado hoje |
|---|---|
| RDS `repro-f3-postgres` | **stopped** (parado 22/09 15:20:31Z), db.t3.micro, PG 16.4, 20 GB gp3, público, single-AZ us-east-1f, param group `order-service-pg16-custom`, PI standard 7 d, EM 1 s |
| EC2 `i-095b252567fbdadfb` (repro-f3-runner) | **stopped**, m7i-flex.large, volume 30 GB preservado |
| ECS cluster `repro-f3-cluster` | existe, 0 tasks |
| taskdef `repro-f3-springboot:1` | **ACTIVE**, 1024/2048, imagem `@sha256:276548dd…` |
| taskdef `repro-f3-quarkus-jvm:1` | **ACTIVE**, 1024/2048, imagem `@sha256:abec3583…` |
| log groups `/ecs/repro-f3-*`, `/repro-f3/vpc-flow-logs` | existem |
| VPC flow log `fl-063474c25955b4dd3` | existe |
| IAM roles `repro-f3-*` + instance profile | existem |
| RDS oficial `order-service-postgres` | **available**, intocado (us-east-1d) |

Prazo relevante: RDS parado é religado à força pela AWS 7 dias depois, ou seja **~29/09/2026 15:20Z**,
se não for apagado antes.

## Consequência para esta investigação

Isto é **reaproveitável e dispensa a maior parte do setup** dos itens 2–4:

1. **Item 2 (RDS novo) fica desnecessário.** `repro-f3-postgres` já é db.t3.micro, PG 16.4, mesmo
   parameter group do oficial e **já carrega o esquema oficial** (copiado por `pg_dump --schema-only`
   do `order-service-postgres`; diff de colunas/índices conferido como idêntico em 21/09). Criar outro
   RDS só repetiria esse trabalho e somaria custo.
2. **Item 3 não exige reboot.** O parâmetro estático já está resolvido:
   `shared_preload_libraries = pg_stat_statements,pg_tle`, com `Source = system` — é o default da AWS
   para RDS PostgreSQL, não uma customização, e vale tanto no RDS oficial quanto no repro. A extensão
   `pg_stat_statements` já foi criada nesse banco em 21/09. Resta só confirmar (`CREATE EXTENSION IF
   NOT EXISTS` + `SELECT`) depois de religar. **Não há reboot no caminho crítico.**
3. **Item 4 já está pronto.** As duas task definitions já apontam para o endpoint
   `repro-f3-postgres.ck1kkwa6og4s.us-east-1.rds.amazonaws.com` e já estão em 1024 CPU units / 2048 MB,
   com os mesmos digests de imagem das coletas oficiais.
4. **O runner e o orquestrador também servem.** `runner/orquestrador.sh` já faz, por rodada,
   exatamente o protocolo pedido nos itens 5 e 7: `stop-task → run-task fresca → health → TRUNCATE
   das três tabelas → pg_stat_statements_reset() → k6 → extração`, disparado por `systemd-run`
   (desacoplado de SSH). Falta só trocar o cenário F3 pelo F1 e acrescentar o dump final completo
   da view (item 6).

Nada foi religado, criado ou apagado até aqui — esta seção é só leitura de inventário.
