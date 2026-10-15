# Investigação L2 — Ambientes de Execução e Limiares de JIT — Resumo Final

Gerado em 2026-08-17. **Nenhum dado oficial foi substituído** — os arquivos em
`analysis/lambda/fase4/l2-*` e os 3 CSVs oficiais (`fase5_estatistica_descritiva.csv`,
`fase5_testes_significancia.csv`, `fase5_teste_global.csv`) permanecem exatamente
como estavam. Esta investigação analisou os logs **originais** de julho/2026,
que continuavam integralmente disponíveis.

## Correção importante sobre a investigação anterior

A investigação original (que concluiu que toda a infraestrutura AWS de julho
havia sido destruída) rodou os comandos AWS **sem `--profile pessoal`**, caindo
no profile default de uma conta diferente (`569794422298`, usada para outros
projetos). A conta correta deste projeto é `776648109551` (`pessoal`). Sob a
conta correta, nada foi destruído: as 3 funções Lambda, os log groups (retenção
infinita), as tabelas DynamoDB, a IAM role, o runner EC2 e seus security
group/key pair — tudo criado em 21/jun/2026 — permanecem ativos até hoje.
Como consequência dessa premissa errada, chegou a ser montado e disparado um
pipeline de recoleta completa (reconstrução de infraestrutura do zero, ~14h
estimadas) antes de essa correção ser descoberta; o pipeline foi abortado sem
nenhum dado novo ter sido gerado, e nenhum recurso original foi tocado.

## Metodologia desta análise

- **Rodadas 1-3** (springboot/quarkus-jvm/quarkus-native): janelas exatas de
  `analysis/lambda/fase4/timestamps.json` (05-06/jul/2026).
- **Rodadas 4-5**: `timestamps.json` só cobria r1-r3. As janelas foram
  reconstruídas empiricamente a partir dos logs reais — busca inicial ancorada
  no mtime do `summary.json`, refinada por uma consulta binada (1min) ao
  CloudWatch Logs Insights que soma invocações a partir do primeiro sinal de
  atividade até bater o total esperado (`http_reqs.count`), isolando
  precisamente onde a rodada de L2 termina e a de L3 (mesmo log group) começa.
  Contagem acumulada reconstruída: 19.907–20.676 invocações, vs. 20.339–20.392
  esperadas (script:
  `scripts/l2_recoleta/reconstruct_windows_r4_r5.py`).
- **Ambientes por rodada**: `scripts/l2_recoleta/cw_env_analysis.py`, consulta
  `filter @type = "REPORT" | stats count(*) by @logStream` (com retry de
  reconciliação já embutido, não precisou de nenhum retry nesta execução — todas
  as 15 combinações reconciliaram na 1ª tentativa).
- **Timestamp de cruzamento de Tier 1/Tier 2**: só calculado para
  springboot/quarkus-jvm (native não tem JIT). Granularidade de 1 minuto.

## Tabela completa — distribuição de invocações por ambiente

| Versão | Rodada | Ambientes | Min | Mediana | **Máx** | Estabiliza cedo | Cruzou Tier 1 (1.000) | Cruzou Tier 2 (10.000) |
|---|---|---|---|---|---|---|---|---|
| springboot | 1 | 49 | 1 | 2 | **16.001** | Sim | 22:36 | 22:43 |
| springboot | 2 | 49 | 1 | 1 | **14.833** | Sim | 23:37 | 23:44 |
| springboot | 3 | 49 | 1 | 2 | **10.158** | Sim | 00:37 | 00:44 |
| springboot | 4 | 67 | 1 | 3 | **12.014** | Não | 09:49 | 09:56 |
| springboot | 5 | 50 | 1 | 1,5 | **10.047** | Não | 10:51 | 10:57 |
| quarkus-jvm | 1 | 50 | 1 | 3 | 7.748 | Sim | 22:57 | — |
| quarkus-jvm | 2 | 50 | 1 | 2 | 8.910 | Sim | 00:02 | — |
| quarkus-jvm | 3 | 51 | 1 | 2 | 7.230 | Não | 00:57 | — |
| quarkus-jvm | 4 | 52 | 1 | 2 | 9.438 | Não | 10:09 | — |
| quarkus-jvm | 5 | 50 | 1 | 3 | 8.633 | Sim | 11:12 | — |
| quarkus-native | 1 | 9 | 1 | 1.502 | 6.874 | Sim | n/a | n/a |
| quarkus-native | 2 | 8 | 1 | 1.217,5 | 7.842 | Sim | n/a | n/a |
| quarkus-native | 3 | 8 | 1 | 1.843 | 8.202 | Sim | n/a | n/a |
| quarkus-native | 4 | 33 | 1 | 2 | 10.956 | Não | n/a | n/a |
| quarkus-native | 5 | 27 | 1 | 2 | 12.490 | Não | n/a | n/a |

Dado bruto completo: `analysis/fase5/fase5_l2_ambientes_execucao.csv`.

## Conclusão

**A resposta é assimétrica entre as duas versões JVM — e isso é o achado central:**

- **Spring Boot**: em **todas as 5 rodadas**, o ambiente mais ativo cruza tanto
  Tier 1 quanto Tier 2 dentro da janela do próprio cenário (máx. 10.047–16.001
  invocações). A distribuição é extremamente assimétrica (mediana 1–3,
  máximo em 5 dígitos) — a carga se concentra fortemente em um único ambiente
  "sortudo" que absorve a maior parte do tráfego, em vez de se fragmentar
  igualmente entre muitos ambientes. **A premissa do L2 se sustenta para
  Spring Boot.**
- **Quarkus JVM**: cruza Tier 1 em todas as 5 rodadas, mas **nunca cruza Tier 2**
  (máx. 7.230–9.438, sempre abaixo de 10.000). **A premissa do L2 NÃO se
  sustenta plenamente para Quarkus JVM** — ele só recebe aquecimento parcial
  (Tier 1) dentro da janela atual, nunca o estado JIT totalmente otimizado que
  o desenho pretendia demonstrar.
- **Quarkus Native**: não se aplica (sem JIT). Achado secundário interessante:
  o número de ambientes concorrentes salta de 8–9 (r1-r3) para 27–33 (r4-r5) —
  vale investigar separadamente se isso reflete uma mudança real de
  comportamento de scaling do Lambda ao longo do tempo ou uma diferença de
  condições entre as duas sessões de coleta (05-06/jul vs 16/jul).

**Implicação prática para o texto do TCC:** a comparação Spring Boot vs.
Quarkus JVM no cenário L2 não é simetricamente justa em termos de oportunidade
de aquecimento — Spring Boot consistentemente tem chance de mostrar
desempenho em Tier 2, Quarkus JVM consistentemente não tem. Isso é
exatamente o tipo de coisa que precisa ser declarado explicitamente no
capítulo de metodologia/limitações, e pode inclusive ajudar a explicar
diferenças de desempenho observadas entre as duas versões no L2 que hoje
podem estar sendo atribuídas apenas à eficiência de cada runtime, quando na
verdade também refletem quanto aquecimento JIT cada uma teve chance real de
acumular.
