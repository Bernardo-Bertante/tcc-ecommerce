# F2/F3 — setup e plano (23/09/2026)

Exploratório, continuação da coleta 3 (`../06_resultado_consolidado.md`, `../07_latencia_e_origem_da_validacao.md`).
Fora do desenho oficial. Nenhum `.tex`/`.md` do projeto principal tocado, sem branch.

## Infraestrutura: recriada do zero

O teardown de 23/09 tinha apagado tudo. Recriado com o mesmo procedimento; inventário completo em
`inventario_recursos.txt` (tag `projeto=tcc-pgss-f2f3`).

| item | valor | observação |
|---|---|---|
| RDS | `pgss-f2f3-postgres`, db.t3.micro, PG 16.4, 20 GB gp3 3000/125, sem backup, sem criptografia, público, subnet group `default`, SG `default` | espelha o oficial. **AZ us-east-1d, a mesma do oficial** (a repro/coleta 3 caiu em 1f) |
| parameter group | `pgss-f2f3-pg16` = cópia de `order-service-pg16-custom` (`max_connections=100`, `work_mem=16384`) + `auto_explain` pré-carregado (`log_min_duration=0`, analyze/buffers/timing/verbose/nested, JSON, `sample_rate=0,02`) + `track_planning=on` | igual à coleta 3; aplicado já na criação, sem reboot. O grupo oficial não foi tocado |
| esquema | `../../reproducao_f3_instabilidade/esquema_oficial_schema_only.sql` (4 tabelas, 10 índices) + a linha `<< Flyway Baseline >>` copiada do `flyway_schema_history` oficial | sem a linha de baseline o Flyway do SB tentava aplicar a V1 e a app não subia (`relation "orders" already exists`). O oficial tem exatamente essa linha; copiada com leitura apenas no oficial |
| instrumentação | Performance Insights 7 d, Enhanced Monitoring 1 s, export `postgresql` → CloudWatch | idem coleta 3 |
| task defs | `pgss-f2f3-springboot`, `pgss-f2f3-springboot-noval`, `pgss-f2f3-quarkus-jvm`, 1024/2048 | geradas das oficiais (`order-service-springboot:12`, `order-service-quarkus-jvm:10`) com as **mesmas** diferenças da repro/coleta 3: imagem por digest (`@sha256:276548dd…`, `@sha256:abec3583…`, os mesmos de antes), host do banco, log de GC em `JAVA_OPTS_APPEND`. `noval` = + `SPRING_R2DBC_POOL_VALIDATION_QUERY=""` |
| runner | `pgss-f2f3-runner`, m7i-flex.large, AL2023, us-east-1c, `k6-runner-sg`, k6 v0.45.0, psql 16 | cenário F3 = blob `0ff2140` (o mesmo das coletas oficiais) |

## Mudança pedida em relação à coleta 3: saída completa do k6

Cada rodada grava `k6 --out json` (NDJSON gz) **e** `requests.csv.gz` (uma linha por requisição:
epoch, duração, `phase`, `operation`, status), e sobe **os dois** para o S3 ao fim da rodada, antes de
qualquer teardown. Isso dá p99 e recorte por endpoint. Validado no smoke: o número de linhas extraídas
bate exatamente com `http_reqs` do k6 (6.827 em F2, 18.119 em F3).

## Smoke (23/09, 21:10–21:18Z)

F2 com SB sem validação + F3 com QJ, durações encurtadas: health, TRUNCATE, reset, k6, dump, estado
físico, parada da task, extração e upload ao S3 funcionaram nos dois cenários. `SELECT $1` na condição
sem validação: 0. Tasks ao fim: 0. Arquivado em `~/f2f3/out_smoke` no runner e no S3 (`f2/r0-*`, `f3/r0-*`).

## Decisões de desenho

**Ordem:** palíndromo ABCCBA com A = SB, B = SB sem validação, C = QJ:
`1:springboot 2:springboot-noval 3:quarkus-jvm 4:quarkus-jvm 5:springboot-noval 6:springboot`, primeiro
F2, depois F3, numa única execução desacoplada.

**F2 reduzido.** Taxas oficiais (48 → 96), durações encurtadas:

| | oficial | aqui |
|---|---|---|
| pré-aquecimento a 48 | 10 min | 2 min |
| rampa 48 → 96 | 90 s | 90 s |
| platô a 96 | 30 min | **7 min** |
| descida | 3 min | 1 min |
| iterações na fase `load` | ~187.900 | ~49.700 |

~49,7 mil iterações de carga ≈ o volume da coleta 3 (~43 mil). O platô de 7 min a 96 sozinho já tem ~40 mil.
**Consequência para a validação contra o oficial:** com 30 min de platô, a tabela `orders` do oficial
fica ~4× maior no fim, e o custo do `get_summary` cresce com ela. A comparação com
`fase5_estatistica_descritiva_novo.csv` de F2 vai mostrar o sentido e a ordem de grandeza, não
números iguais.

**F3 completo** (rampa oficial 48/240/48, 5m/2m/10m/2m/5m/1m, VUs 1500/3000). Justificativa: o que
distingue F3 é o regime de saturação. A reprodução de 21–22/09 mostrou o custo do `get_summary` indo de
~30 ms a 300–1.600 ms por chamada com a tabela crescendo durante o pico, e a CPU do db.t3.micro
saturando no fim dele. Encurtar o pico muda o tamanho da tabela no pico, e portanto exatamente o
mecanismo que pode passar a dominar em carga alta — que é a pergunta desta coleta. Custo extra de
fazer inteiro: ~1h30 a mais que uma versão pela metade.

**Latência:** `http_req_duration` com `phase = load` (no F2 exclui o pré-aquecimento; no F3 é a rodada
inteira menos o setup). Média, mediana, p90, p95, p99, por rodada, por condição e por endpoint.

## Riscos conhecidos

- **F3 do SB é instável neste hardware.** Na reprodução, o p95 do SB variou de 51 ms a 3,1 s entre
  rodadas, com efeito de dia associado ao *steal* do host do RDS. Com 2 réplicas por condição, as
  frações do gap em F3 podem ficar dominadas por variação entre rodadas. O palíndromo protege contra
  deriva monotônica, mas não contra variância entre rodadas. Se acontecer, será reportado como tal.
- RDS t3 em modo *unlimited*: sob saturação consome créditos excedentes (cobrados, não estrangulados).
