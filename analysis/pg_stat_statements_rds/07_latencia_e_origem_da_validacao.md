# Latência da aplicação por condição + origem da `validation-query` (23/09/2026)

Exploratório, **sem coleta nova nem infraestrutura**: reanálise dos `summary.json` da coleta 3
(palíndromo ABCCBA, 6 rodadas, 0 % de falhas). Nenhum `.tex`/`.md` do projeto principal tocado.
Script: `coleta3/latencia_k6.py`. Saídas: `coleta3/resultados/latencia_k6_por_rodada.csv`,
`coleta3/resultados/latencia_k6_por_condicao.csv`.

> **Ressalva obrigatória: carga F1 apenas** (48 req/s, 16 min, mix oficial). Nada aqui vale para
> F2/F3 sem medir. RDS exploratório `db.t3.micro`, não o oficial.

## Fonte e o que ela não tem

Métrica: `http_req_duration{phase:load}` do k6 (latência ponta a ponta vista pelo gerador, só a
fase de carga; exclui as 120 requisições de *seed* do setup).

- **Não há p99.** O `--summary-export` do k6 v0.45 exporta só avg/min/med/max/p90/p95. O threshold
  `p(99)<5000` existe no cenário, mas o valor não é exportado. O orquestrador v3 não gravou a saída
  bruta por requisição (`--out json`), e os logs da aplicação foram apagados no teardown. **Uso p90
  no lugar do p99 pedido.** Não há como recuperar o p99 desta coleta.
- **Não há recorte por endpoint.** O único submétrico exportado é `{phase:load}`. As requisições
  carregam a tag `operation`, mas sem `--out json` ela não chega a nenhum arquivo.

## Por rodada (ms)

| rodada | média | mediana | p90 | p95 | máx |
|---|---|---|---|---|---|
| r1 springboot | 16,14 | 8,00 | 20,90 | 33,12 | 2.375,5 |
| r2 quarkus-jvm | 6,74 | 3,77 | 9,75 | 14,82 | 869,7 |
| r3 springboot-noval | 7,19 | 4,22 | 11,84 | 13,97 | 616,1 |
| r4 springboot-noval | 6,61 | 3,32 | 10,24 | 12,71 | 1.298,3 |
| r5 quarkus-jvm | 7,67 | 3,64 | 10,69 | 16,68 | 1.122,4 |
| r6 springboot | 13,18 | 6,69 | 17,77 | 24,18 | 2.040,7 |

## Média das duas réplicas e fração do gap SB×QJ removida

Mesma forma da tabela de CPU de `06_resultado_consolidado.md`. Fração removida = (SB − SB sem
validação) / (SB − QJ). Acima de 100 % significa que o SB sem validação ficou abaixo do QJ.

| estatística | SB | SB sem validação | QJ | SB/QJ | sem val./QJ | fração do gap removida |
|---|---|---|---|---|---|---|
| média | 14,66 | 6,90 | 7,21 | 2,034 | 0,957 | **104 %** |
| mediana | 7,35 | 3,77 | 3,70 | 1,984 | 1,018 | **98 %** |
| p90 | 19,33 | 11,04 | 10,22 | 1,892 | 1,080 | **91 %** |
| p95 | 28,65 | 13,34 | 15,75 | 1,819 | 0,847 | **119 %** |
| máx | 2.208,1 | 957,2 | 996,1 | 2,217 | 0,961 | 103 % |

Para comparação, na CPU total do RDS a fração removida foi 86 %.

## Leitura da dispersão

- **SB sem validação × QJ: indistinguíveis nesta coleta.** As réplicas se sobrepõem em todas as
  estatísticas: média 6,61–7,19 × 6,74–7,67; mediana 3,32–4,22 × 3,64–3,77; p95 12,71–13,97 ×
  14,82–16,68. As frações acima de 100 % estão dentro dessa sobreposição, então não indicam que o
  SB sem validação seja mais rápido que o QJ. O p95 é a única estatística em que as duas faixas não
  se tocam (o SB sem validação ficou abaixo), mas com 2 réplicas isso não sustenta afirmação.
- **SB × os outros dois: separação clara.** A pior réplica das outras condições (média 7,67, p95
  16,68) fica bem abaixo da melhor réplica do SB (média 13,18, p95 24,18).
- **O SB variou mais entre as pontas do palíndromo** (r1 → r6: média 16,14 → 13,18, p95 33,1 → 24,2)
  que as outras condições. Na CPU dos backends as duas réplicas do SB diferiram só 0,02 ponto (4,91
  × 4,93). A variação de latência do SB não veio acompanhada de variação de CPU no banco.
- **Mesmo sentido nas outras coletas**, com magnitude diferente. p95 SB/QJ: coleta 1 = 18,0/10,2
  (1,76×); coleta 3 = 1,82×. A coleta 2 não entra aqui por causa do defeito de conexões.

## Origem da linha `validation-query: SELECT 1`

`git log -S "validation-query"` em todo o repositório retorna **um único commit**:

| | |
|---|---|
| commit | `330e13fa1e692ec523944baf128368f93be677b1` |
| data | 2026-05-11 18:52:12 −0300 |
| autor | Bernardo |
| trailer | `Co-authored-by: Copilot <copilot@github.com>` |
| título | `feat: Add integration tests and exception handling for order service` |

Fatos verificáveis no histórico:

- O `application.yml` foi criado **vazio** em `067e5d7` (2026-04-30, `chore: set initial project
  structure`). A linha entrou em `330e13f` junto com o arquivo inteiro (0 → 61 linhas): URL/usuário/
  senha do R2DBC, pool (`initial-size: 5`, `max-size: 20`, `max-idle-time: 30m`,
  `validation-query: SELECT 1`), Flyway, Actuator e logging.
- **A mensagem do commit não menciona pool, conexão nem validação.** Os 9 itens descrevem testes de
  integração, DTOs, exceções e repositórios. É um commit grande, que também cria boa parte do
  serviço Quarkus.
- **Não há comentário ao redor da linha.** O único comentário do bloco é o cabeçalho
  `# --- R2DBC (runtime reativo) ---`.
- **O arquivo nunca mais foi alterado** depois de `330e13f`. Nos testes oficiais, o tamanho do pool
  foi sobrescrito por variável de ambiente (`SPRING_R2DBC_POOL_MAX_SIZE=40`,
  `SPRING_R2DBC_POOL_INITIAL_SIZE=15`), mas a validação nunca.
- **Nenhum documento do repositório cita a configuração** fora de `analysis/pg_stat_statements_rds/`:
  nenhum `.md`, `.tex`, README ou comentário de código fala em `validation-query`, `validationQuery`
  ou validação de conexão.
- O `application.properties` do Quarkus, que evoluiu no mesmo período, configura só `max-size=20`
  para o pool reativo, sem validação.

**O que o histórico não permite dizer:** se a linha veio de guia, de template ou de sugestão do
Copilot. O trailer `Co-authored-by: Copilot` indica que o commit foi feito com assistência dele, mas
não atribui linhas específicas. O registro no repositório é compatível com qualquer uma das três
origens e não documenta decisão sobre ela.
