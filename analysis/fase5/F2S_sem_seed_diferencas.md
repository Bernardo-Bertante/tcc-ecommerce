# F2-S sem as 120 amostras de semeadura — diferenças

Oficial = `fase5_estatistica_descritiva_novo.csv`, `fase5_testes_significancia.csv`, `fase5_teste_global.csv` (distribuição com os 120 POST do `setup()`). Sem seed = 120 primeiras amostras de cada rodada descartadas (15 rodadas; n por versão cai de ~33,0 mil para ~32,4 mil). Script: `analysis/fase5_f2s_sem_seed.py` (validado: com seed=0 reproduz os CSVs oficiais com diferença relativa < 1e-13). Diferença relativa = (sem seed − oficial)/oficial.

## 1. Estatística descritiva por versão

| Versão | Estatística | Oficial | Sem seed | Δ abs | Δ rel |
|---|---|---:|---:|---:|---:|
| SB | n | 32.997 | 32.397 | -600 | -1.82% |
| SB | mean | 241.30 | 245.01 | 3.71 | +1.54% |
| SB | median | 100.65 | 100.70 | 0.05 | +0.05% |
| SB | std | 512.29 | 516.25 | 3.96 | +0.77% |
| SB | min | 14.74 | 54.12 | 39.38 | +267.08% |
| SB | max | 6447.40 | 6447.40 | 0.00 | +0.00% |
| SB | p90 | 365.31 | 376.14 | 10.83 | +2.96% |
| SB | p95 | 1232.01 | 1254.60 | 22.59 | +1.83% |
| SB | p99 | 2443.74 | 2462.38 | 18.64 | +0.76% |
| SB | cv_entre_rodadas | 0.2964 | 0.2973 | 0.0009 | +0.29% |
| SB | cv_dentro_rodada | 2.1231 | 2.1070 | -0.0160 | -0.75% |
| SB | p95_p50_ratio | 12.24 | 12.46 | 0.22 | +1.78% |
| QJ | n | 32.999 | 32.399 | -600 | -1.82% |
| QJ | mean | 125.29 | 127.34 | 2.05 | +1.64% |
| QJ | median | 77.18 | 77.21 | 0.03 | +0.04% |
| QJ | std | 244.96 | 246.73 | 1.77 | +0.72% |
| QJ | min | 7.39 | 42.33 | 34.94 | +472.70% |
| QJ | max | 3443.82 | 3443.82 | 0.00 | +0.00% |
| QJ | p90 | 111.44 | 113.06 | 1.62 | +1.46% |
| QJ | p95 | 235.68 | 240.57 | 4.89 | +2.07% |
| QJ | p99 | 1600.07 | 1607.86 | 7.79 | +0.49% |
| QJ | cv_entre_rodadas | 0.0497 | 0.0498 | 0.0001 | +0.15% |
| QJ | cv_dentro_rodada | 1.9552 | 1.9375 | -0.0177 | -0.90% |
| QJ | p95_p50_ratio | 3.05 | 3.12 | 0.06 | +2.03% |
| QN | n | 32.995 | 32.395 | -600 | -1.82% |
| QN | mean | 140.08 | 142.55 | 2.47 | +1.76% |
| QN | median | 77.09 | 77.12 | 0.03 | +0.04% |
| QN | std | 331.94 | 334.50 | 2.56 | +0.77% |
| QN | min | 5.22 | 42.75 | 37.53 | +719.39% |
| QN | max | 5088.48 | 5088.48 | 0.00 | +0.00% |
| QN | p90 | 116.68 | 117.78 | 1.10 | +0.94% |
| QN | p95 | 293.27 | 310.08 | 16.81 | +5.73% |
| QN | p99 | 1780.69 | 1796.88 | 16.19 | +0.91% |
| QN | cv_entre_rodadas | 0.1812 | 0.1814 | 0.0002 | +0.11% |
| QN | cv_dentro_rodada | 2.3697 | 2.3466 | -0.0231 | -0.98% |
| QN | p95_p50_ratio | 3.80 | 4.02 | 0.22 | +5.69% |

_`min` muda muito porque o mínimo oficial (14,7 / 7,4 / 5,2 ms) era um POST de semeadura; sem seed passa a ser o mínimo do GET /summary (54,1 / 42,3 / 42,7 ms)._

## 2. Razões entre versões

| Razão | Oficial | Sem seed | Δ rel |
|---|---:|---:|---:|
| Média SB÷QJ | 1.926 | 1.924 | -0.10% |
| Média SB÷QN | 1.723 | 1.719 | -0.22% |
| Média QN÷QJ | 1.118 | 1.119 | +0.12% |
| Mediana SB÷QJ | 1.304 | 1.304 | +0.01% |
| Mediana SB÷QN | 1.305 | 1.306 | +0.02% |
| p95 SB÷QJ | 5.227 | 5.215 | -0.23% |
| p95 SB÷QN | 4.201 | 4.046 | -3.69% |

## 3. Comparações par a par (distribuição concatenada)

| Comparação | Estatística | Oficial | Sem seed | Mudou? |
|---|---|---:|---:|---|
| SB vs QJ | cliffs_delta | 0.7469 | 0.772 | |
| SB vs QJ | cohens_d | 0.2889 | 0.2908 | |
| SB vs QJ | mannwhitney_p_holm | 0 | 0 | |
| SB vs QJ | ttest_p_holm | 1.065e-296 | 3.931e-295 | |
| SB vs QJ | classe Cliff (Romano 2006) | grande | grande | não |
| SB vs QJ | classe d de Cohen (0,2/0,5/0,8) | pequeno | pequeno | não |
| SB vs QJ | significativo (MW e Welch, Holm, p<0,05) | True | True | não |
| SB vs QJ | sinal da diferença de médias | + | + | não |
| SB vs QN | cliffs_delta | 0.7366 | 0.7611 | |
| SB vs QN | cohens_d | 0.2345 | 0.2356 | |
| SB vs QN | mannwhitney_p_holm | 0 | 0 | |
| SB vs QN | ttest_p_holm | 1.916e-197 | 1.296e-195 | |
| SB vs QN | classe Cliff (Romano 2006) | grande | grande | não |
| SB vs QN | classe d de Cohen (0,2/0,5/0,8) | pequeno | pequeno | não |
| SB vs QN | significativo (MW e Welch, Holm, p<0,05) | True | True | não |
| SB vs QN | sinal da diferença de médias | + | + | não |
| QJ vs QN | cliffs_delta | 0.01902 | 0.0191 | |
| QJ vs QN | cohens_d | -0.05069 | -0.05173 | |
| QJ vs QN | mannwhitney_p_holm | 2.324e-05 | 2.537e-05 | |
| QJ vs QN | ttest_p_holm | 7.508e-11 | 4.606e-11 | |
| QJ vs QN | classe Cliff (Romano 2006) | desprezível | desprezível | não |
| QJ vs QN | classe d de Cohen (0,2/0,5/0,8) | desprezível | desprezível | não |
| QJ vs QN | significativo (MW e Welch, Holm, p<0,05) | True | True | não |
| QJ vs QN | sinal da diferença de médias | − | − | não |

## 4. Teste global (média por rodada, N=5 por versão)

| Estatística | Oficial | Sem seed |
|---|---:|---:|
| kruskal_h | 10.22 | 10.22 |
| kruskal_p | 0.0060361 | 0.0060361 |
| anova_f | 10.314 | 10.217 |
| anova_p | 0.0024747 | 0.0025645 |
| método indicado | Kruskal-Wallis | Kruskal-Wallis |

_O H de Kruskal–Wallis é idêntico (10,22) porque depende só dos postos das 15 médias por rodada, e a ordenação entre rodadas não mudou ao remover o seed._

