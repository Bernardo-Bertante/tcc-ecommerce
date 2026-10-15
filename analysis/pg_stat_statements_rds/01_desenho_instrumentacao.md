# Desenho da instrumentação — decisões e riscos (22/09/2026)

## 1. Parameter group: por que NÃO alterei o oficial

`order-service-pg16-custom` está anexado às **duas** instâncias: `order-service-postgres` (oficial) e
`repro-f3-postgres`. Alterar `shared_preload_libraries` nele marcaria o RDS oficial como
`pending-reboot` e mudaria a configuração declarada na metodologia do TCC.

Criei `repro-f3-pg16-autoexplain` por `copy-db-parameter-group`, que preserva as duas customizações
reais do oficial (`max_connections=100`, `work_mem=16384`), e anexei só ao RDS exploratório. O grupo
oficial **não foi tocado**. No teardown basta apagar o grupo novo — não há reversão a fazer no oficial.

## 2. O conflito entre os dois instrumentos, e como foi resolvido

`auto_explain` com `log_analyze=on` + `log_timing=on` instrumenta **cada nó do plano** com chamadas de
relógio. Esse custo entra no tempo de execução da consulta e, portanto, **é contabilizado dentro do
`total_exec_time`/`mean_exec_time` do `pg_stat_statements`** e na CPU do RDS.

Com `log_min_duration=0` e `sample_rate=1` (todas as consultas instrumentadas), os dois instrumentos
se contaminam:

- os tempos do `pg_stat_statements` ficam inflados em relação à carga oficial;
- pior, a inflação **não é uniforme**: um plano com mais nós recebe mais chamadas de relógio. Se as
  consultas de um framework tiverem mais nós que as do outro, isso **fabricaria** uma diferença de
  tempo entre Spring Boot e Quarkus que não existe na carga real — exatamente o efeito que esta
  investigação existe para medir;
- volume: ~100 mil statements por rodada × ~1,5–4 KB de plano JSON = 150–400 MB de log por rodada.

**Solução adotada: `auto_explain.sample_rate = 0.02`, mantendo `log_min_duration = 0`.**

A decisão de instrumentar é tomada no início de cada statement: os 98 % não sorteados executam sem
nenhum overhead. Consequências:

- a contaminação dos tempos do `pg_stat_statements` fica limitada a 2 % das chamadas, ou seja, bem
  abaixo de 1 % na média — os números do item 6 continuam comparáveis entre as versões;
- ainda sobram ~2.000 planos reais por rodada, com cobertura folgada de todo endpoint do mix
  (inclusive `get_summary`, o mais raro: ~760 chamadas × 5 agregações × 2 % ≈ 76 planos);
- o log cai para ~6 MB por rodada.

**Por que `sample_rate` e não subir o `log_min_duration`,** que foi a alternativa cogitada: elevar o
`log_min_duration` filtra por duração e **enviesa a amostra de planos para as consultas lentas**,
descartando justamente as rápidas e frequentes (`GET /orders/{id}`, 51 % do mix) — que são candidatas
centrais a explicar a CPU do RDS, já que CPU total = custo por chamada × número de chamadas. O
`sample_rate` sorteia de forma uniforme e preserva todos os tipos de consulta. Os dois parâmetros são
dinâmicos, então dá para ajustar entre rodadas sem reboot.

## 3. Reboot: necessário, mas por causa do auto_explain apenas

`shared_preload_libraries` já continha `pg_stat_statements,pg_tle` por default da AWS (`Source=system`).
O valor novo é `pg_stat_statements,pg_tle,auto_explain` — estático, logo **um reboot**, só no RDS
exploratório. Todos os `auto_explain.*` são dinâmicos e ajustáveis depois sem reboot.

## 4. Destino do log

O RDS já exporta `postgresql` para o log group `/aws/rds/instance/repro-f3-postgres/postgresql`
(retenção: never expire). Os planos serão recuperados por `download-db-log-file-portion` direto da
API do RDS (mais rápido e sem custo de ingestão para volume grande) com o CloudWatch como segunda
via. `log_line_prefix = %t:%r:%u@%d:[%p]:` permite separar as linhas por PID na remontagem dos
JSON multilinha.
