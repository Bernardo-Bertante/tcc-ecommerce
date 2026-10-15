# pg_stat_statements + auto_explain no RDS — custo por tipo de consulta (SB × QJ)

**Investigação exploratória, 22–23/09/2026.** Fora do desenho experimental oficial do TCC.
Não altera nenhum CSV oficial nem capítulo; nenhum `.tex`/`.md` do projeto principal foi tocado.
Sem branch. Mesmo status de `exploratorio_gc_f3/` e `reproducao_f3_instabilidade/`.

**Pergunta:** o Spring Boot impõe 21–35 % mais CPU ao RDS que as versões Quarkus (oficial,
`fase5_rds_cpu_por_rodada.csv`, §subsec:cpu-rds). Isso é uma consulta estruturalmente mais cara,
ou a mesma consulta executando mais devagar?

**Resposta:** ver [`06_resultado_consolidado.md`](06_resultado_consolidado.md). Resumo: nem consulta
mais cara nem a mesma consulta mais lenta, principalmente. **72–86 % do gap** vem da validação de
conexão do pool R2DBC (`spring.r2dbc.pool.validation-query: SELECT 1`, configurada no `application.yml`
do Spring Boot). Com ela desligada, a CPU do RDS fica em SB/QJ = 1,035× (contra 1,247×).
A resposta da coleta 1 (`03_resposta_direta.md`) está superada.

## Documentos

| arquivo | conteúdo |
|---|---|
| [`00_estado_infra_pre_existente.md`](00_estado_infra_pre_existente.md) | verificação do teardown pendente da `reproducao_f3_instabilidade` (item 1) |
| [`01_desenho_instrumentacao.md`](01_desenho_instrumentacao.md) | por que não alterei o parameter group oficial; por que `sample_rate = 0,02` |
| [`02_comparacao_por_operacao.md`](02_comparacao_por_operacao.md) | comparação lado a lado por endpoint, diferenças estruturais de SQL, planos (item 8) |
| [`03_resposta_direta.md`](03_resposta_direta.md) | resposta à pergunta, com o que ficou em aberto |
| [`05_desenho_coleta2.md`](05_desenho_coleta2.md) | desenho das coletas 2/3: palíndromo ABCCBA, condição sem validação |
| [`coleta2/NOTAS_coleta2.md`](coleta2/NOTAS_coleta2.md) | coleta 2 e o defeito de conexões |
| [`06_resultado_consolidado.md`](06_resultado_consolidado.md) | **resultado final**, coleta 3 |
| [`07_latencia_e_origem_da_validacao.md`](07_latencia_e_origem_da_validacao.md) | latência k6 por condição (coleta 3) e origem da linha no git |
| [`f2_f3/01_resultado_f2_f3.md`](f2_f3/01_resultado_f2_f3.md) | **F2 e F3** (24/09): fração explicada pela validação cai com a taxa; resíduo no `get_summary` + saturação do RDS em F3 |
| [`f2_f3/00_setup_e_plano.md`](f2_f3/00_setup_e_plano.md) | setup recriado e decisões de desenho de F2/F3 |
| [`residuo_estrutural/README.md`](residuo_estrutural/README.md) | **resíduo SB sem validação × QJ** (24/09): não é texto, plano nem fetch; blocos do `get_summary` refletem o layout físico do heap (QJ ~3× mais); latência sem mecanismo |
| [`04_teardown.md`](04_teardown.md) | o que foi desprovisionado |

## Dados

| caminho | conteúdo |
|---|---|
| `dados/f1-springboot/`, `dados/f1-quarkus-jvm/` | por rodada: `pg_stat_statements.csv` (dump completo), `summary.json` do k6, `k6.log`, `meta.json` (janela da carga), `auto_explain_settings.txt`, `pg_stat_user_tables.tsv` |
| `resultados/consultas_classificadas.csv` | toda consulta das duas rodadas, com a operação atribuída |
| `resultados/comparacao_por_operacao.csv` | agregado lado a lado por operação |
| `resultados/decomposicao_do_gap.txt` | quanto cada operação contribui para a diferença |
| `resultados/amostras_planos.csv` | uma linha por plano capturado (10.527) |
| `resultados/planos_por_operacao.txt` | planos agrupados por operação e por texto de consulta |
| `planos/planos_*.json` | planos JSON íntegros, agregados por `queryid` |
| `planos/logs_brutos/` | logs do Postgres baixados do RDS (`.gz`) |

## Scripts

| script | função |
|---|---|
| `runner/orquestrador_pgss.sh` | roda no runner EC2: task fresca → `TRUNCATE` → `pg_stat_statements_reset()` → k6 F1 → dump da view |
| `extrai_planos.py` | baixa os logs do RDS e remonta os planos JSON multilinha do `auto_explain` |
| `extrai_amostras.py` | achata os planos em uma linha por amostra |
| `compara.py` | classifica as consultas por operação e gera a comparação |

## Reprodução

```bash
export AWS_PROFILE=pessoal
# (infra já desprovisionada — seria preciso recriar RDS + taskdefs antes)
ssh ec2-user@<runner> 'cd ~/pgss && F1_DURATION=14m ./orquestrador_pgss.sh "springboot quarkus-jvm"'
python3 extrai_planos.py planos dados/janelas.json
python3 extrai_amostras.py
python3 compara.py dados resultados
```
