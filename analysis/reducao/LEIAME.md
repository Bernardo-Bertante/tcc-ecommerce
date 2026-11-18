# Números da versão final do TCC

Esta pasta contém os números e as figuras do texto entregue do TCC, na versão de novembro de 2026. As tabelas dos Resultados e da Discussão citam estes CSVs como fonte, com uma exceção: a memória máxima do L1 vem de `analysis/fase5/fase5_l1_memoria_novo.csv` (ver "Cuidados ao citar"). Os CSVs de `analysis/fase5/` são de versões anteriores do texto, que aplicavam outra análise (correção de Holm e testes globais).

## Como conferir

Os comandos abaixo são executados a partir da raiz do repositório. Eles precisam de Python 3 com `numpy` e `scipy`.

```bash
python3 analysis/reducao/reducao_estatistica.py analysis saida_conferencia
```

Os cinco CSVs gerados em `saida_conferencia/` devem ser iguais aos desta pasta, byte a byte.

## Figuras

```bash
python3 analysis/reducao/reducao_figuras.py analysis/reducao analysis figuras
```

- O script lê os CSVs desta pasta e os pontos individuais do `fargate/h1b/h1b_startup_times.json`. Ele não calcula nenhum número.
- Gera `fig_coldstart_lambda.pdf`, `fig_inicializacao_fargate.pdf` e `fig_latencia_aquecida.pdf`. As versões usadas no texto estão em `figuras/`.
- Requer `matplotlib`. Usa a fonte Latin Modern quando ela estiver instalada.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `reducao_por_rodada.csv` | Média, mediana e p95 de cada rodada, tirados do `summary.json` do k6 |
| `reducao_cenarios.csv` | Por cenário e versão: média das 5 rodadas, desvio entre rodadas, IC de 95% e CV, para média, mediana e p95. Traz também as mesmas medidas sobre todas as requisições juntas (`agregado_*`) |
| `reducao_welch.csv` | t de Welch por par de versões sobre as 5 rodadas, com IC de 95% da diferença e razão entre as médias |
| `reducao_l1_h1b.csv` | L1 e H1b: média, desvio, IC de 95%, mínimo, máximo e mediana |
| `reducao_l1_h1b_welch.csv` | t de Welch por par sobre as observações individuais do L1 e do H1b, e se as faixas de valores são disjuntas |

## Fontes

| Cenário | Pasta, dentro de `analysis/` |
|---|---|
| F1 | `fargate/fase3-f1-rerun/` |
| F2 | `fargate/fase3/` (coleta de julho) |
| F3 | `fargate/fase3-f3-rerun/` (recoleta de setembro) |
| L2, L3 | `lambda/fase4/` (ver o aviso sobre o agregado, abaixo) |
| L1 | `lambda/l1/l1_init_durations.json` e `lambda/l1/l1_duration_postinit.csv` |
| H1b | `fargate/h1b/h1b_startup_times.json`. Os 10 ciclos estão em `fargate/h1b/h1b_final_reconciliado.csv`, e a extração do CloudWatch de onde ele veio, em `fargate/h1b/h1b_raw_extraido_cloudwatch.csv` |
| Memória do L1 (no texto) | `fase5/fase5_l1_memoria_novo.csv` |

O agregado de L2 e L3 vem de `fase5/fase5_estatistica_descritiva_novo.csv`, porque o bruto das rodadas 1 a 3 não está no repositório (ver `DADOS_GRANDES.md`).

## Cuidados ao citar

- **Convenções.**
  - O desvio padrão é amostral (n − 1).
  - Nenhuma correção para comparações múltiplas foi aplicada.
- **Mediana e p95.** O `reducao_welch.csv` também traz testes sobre essas duas medidas. No texto, elas são descritivas e os testes servem só de conferência.
- **IC do p95.** O IC de 95% do p95 do Spring Boot no F3 tem limite inferior negativo, porque o desvio entre rodadas é de 443,7 ms. Para o p95, cite a média e o desvio, não o IC.
- **L1 do Quarkus JVM.** Há duas fontes para a inicialização:
  - 1.385,9 ms, de `l1_init_durations.json`, com valores inteiros. O texto usa esta para a inicialização.
  - 1.385,99 ms, de `l1_duration_postinit.csv`, com valores com decimais. O texto usa esta para o tempo faturado.
- **Memória máxima do L1.** O `reducao_l1_h1b.csv` também tem uma linha de memória, calculada a partir de `l1_duration_postinit.csv`. Ela dá 184,8 ± 0,42 MB no Quarkus JVM, contra 184,7 ± 0,5 MB do `fase5_l1_memoria_novo.csv`, que é a fonte citada no texto. No Spring Boot (223,5 MB) e no Native (68,0 MB), as duas fontes coincidem.
- **H1b.**
  - Foram coletados 10 ciclos por versão, e o 10º foi excluído nas três.
  - A causa da exclusão não foi reconstituída. A reextração dos registros do CloudWatch, em 25/08/2026 (`h1b_raw_extraido_cloudwatch.csv`), não encontrou duplicata de log, ao contrário do que dizia a versão anterior do JSON.
  - Os dois CSVs escrevem as versões como `quarkus_jvm` e `quarkus_native`; o JSON, como `quarkus-jvm` e `quarkus-native`.
  - Os campos `std_s` do JSON foram corrigidos em 18/11/2026 para o desvio amostral dos próprios valores: 0,813 s no Spring Boot e 1,219 s no Quarkus JVM. Antes, eram 0,826 s e 1,110 s.
