# warmup_curve — investigação adicional §6.5 (curva de aquecimento por ambiente)

Gerado em 2026-09-08. Reconsulta dos logs REPORT já existentes no CloudWatch
(retenção infinita, conta 776648109551, `--profile pessoal`), cenários L2 e L3,
Spring Boot e Quarkus JVM, 5 rodadas. **Nenhum teste de carga reexecutado.
Nenhum CSV/arquivo oficial sobrescrito** — tudo aqui é saída nova.

## Como reproduzir

```
python3 scripts/warmup_curve/extract_warmup.py    # ~10 min, consulta o CloudWatch
.venv/bin/python scripts/warmup_curve/analyze_warmup.py
```

## Arquivos

| arquivo | conteúdo |
|---|---|
| `warmup_curve_summary.md` | **relatório principal** — tabelas 1-7 + respostas às 2 perguntas |
| `warmup_curve.png` | curva duration × nº de sequência (SB × Quarkus JVM), 3 painéis |
| `invocations_long.csv.gz` | 1 linha por invocação: runtime, rodada, cenário, ts, log_stream, seq, faixa, duration/billed/init ms, memória |
| `band_stats_by_round.csv` | duration por faixa de sequência × runtime × rodada × cenário |
| `band_stats_aggregate.csv` | idem, agregado das 5 rodadas |
| `windows_used.json` | janelas L2/L3 por rodada (r1-r3 de timestamps.json; r3-r5 L3 e r4-r5 L2 reconstruídas dos logs) |

## Definições

- **Ambiente de execução** = `@logStream` do Lambda (1 sandbox ≈ 1 stream/dia).
- **Nº de sequência (`seq`)** = ordem da invocação DENTRO do próprio `@logStream`,
  contada de forma acumulada de L2 para L3 (L3 roda ~4 s após o fim de L2 no
  mesmo log group e reaproveita os ambientes já aquecidos por L2).
- **duration** = campo `@duration` da linha REPORT (execução do handler, **não**
  inclui init; init fica em `@initDuration`).

## Resultado em uma frase

A inversão de ranking em L2/L3 em regime aquecido **não** é artefato de
aquecimento: dentro de um mesmo ambiente bem aquecido (seq ≥ ~1000) o Quarkus
JVM executa cada invocação ~17 % (~3,2 ms) mais devagar que o Spring Boot, com
gap estável e sem convergência até os ambientes mais quentes observados
(~9,5 mil invocações). Ver `warmup_curve_summary.md` para o detalhamento.
