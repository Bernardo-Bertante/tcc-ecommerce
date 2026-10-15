# Relatório preliminar automático — exp-lazy-sb, Spring Boot (EXPLORATÓRIO, fora do desenho oficial)

RUN_ID `smoke-20260930T223447Z`. Gerado pelo driver na EC2. Apenas descritivo. Nenhum intervalo aqui é confirmatório. Fonte de cada número: `samples_final.csv`, `invocations.csv`, `points.csv`, `intervals.csv`, `phases.csv`, `summary.json`; L1 oficial: `l1_duration_postinit.csv`.

## 1. Amostras

- Frias válidas: {'V0': 3, 'V1': 3, 'V2': 3}; tentativas não frias/erro: {'V0': 0, 'V1': 0, 'V2': 0}
- Versões de runtime (INIT_START): {'V0': ['java:21.v68'], 'V1': ['java:21.v68'], 'V2': ['java:21.v68']}
- CodeSha256: {'V0': ['ODLvR0a13wdABKP6LvMTo/xvKxTpEUz3H79fgDg0bbg='], 'V1': ['L404Qp+XeWSAaSujHlNAfXB5lGJOeaOJxCkHlkbwSKI='], 'V2': ['L404Qp+XeWSAaSujHlNAfXB5lGJOeaOJxCkHlkbwSKI=']}
- Handler: {'V0': ['org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest'], 'V1': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest'], 'V2': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest']}

## 2. Por variante (ms; mediana [Q1–Q3] min–max, n)

| Variante | Init | Duration | Init + Duration | Duration 2ª chamada (quente) | Gap fim-init→START |
|---|---|---|---|---|---|
| V0 | 3673.8 [3537.3–4018.8] 3400.7–4363.7, n=3 | 2692.6 [2659.9–2712.5] 2627.3–2732.4, n=3 | 6366.4 [6197.2–6731.3] 6027.9–7096.1, n=3 | 77.1 [64.0–93.0] 50.9–108.8, n=3 | 3.3 [3.2–3.3] 3.1–3.3, n=3 |
| V1 | 4422.9 [4164.1–4426.5] 3905.3–4430.1, n=3 | 2794.5 [2762.4–2808.3] 2730.2–2822.0, n=3 | 7153.1 [6926.5–7202.6] 6699.8–7252.2, n=3 | 97.8 [76.5–120.6] 55.1–143.4, n=3 | 3.9 [3.8–4.0] 3.7–4.1, n=3 |
| V2 | 4405.9 [4135.4–4416.7] 3865.0–4427.4, n=3 | 285.4 [277.2–303.5] 269.0–321.7, n=3 | 4691.3 [4412.6–4720.2] 4134.0–4749.1, n=3 | 109.4 [88.1–114.6] 66.9–119.8, n=3 | 3.6 [3.3–3.9] 3.0–4.1, n=3 |
| L1 oficial QJ | 3768.9 [3668.6–3821.2] 3105.5–4153.7, n=11 | 2773.7 [2693.1–2815.7] 2568.9–3058.7, n=11 | 6509.2 [6330.8–6643.1] 5879.2–7212.4, n=11 | — | — |

## 3. Controle (V0 × L1 oficial)

```
{
 "init_ms": {
  "v0_median": 3673.8,
  "l1_median": 3768.9,
  "diff_pct": -2.5,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -414.3,
   678.1
  ]
 },
 "duration_ms": {
  "v0_median": 2692.6,
  "l1_median": 2773.7,
  "diff_pct": -2.9,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -157.9,
   20.8
  ]
 },
 "rule": "controle OK se |diff| das medianas de Duration <= 10% (regra pré-definida na A3, descritiva); Init só reportado",
 "ok": true
}
```

Instrumentação (V1 x V0): {"rule": "sinalizar se |diff| das medianas de Duration V1 x V0 > 5% (regra pré-definida na A3)", "diff_pct": 3.8, "flag": false}

## 3b. Marcas do Spring (ms, log)

```
{
 "V0": {
  "spring_started_s": {
   "n": 3,
   "median": 2.89,
   "mean": 2.77,
   "q1": 2.6,
   "q3": 3.0,
   "iqr": 0.41,
   "min": 2.31,
   "max": 3.12,
   "sd": 0.42
  },
  "spring_process_running_s": {
   "n": 3,
   "median": 3.64,
   "mean": 3.74,
   "q1": 3.48,
   "q3": 3.95,
   "iqr": 0.48,
   "min": 3.31,
   "max": 4.27,
   "sd": 0.49
  },
  "start_to_received_ms": {
   "n": 3,
   "median": 165.0,
   "mean": 165.67,
   "q1": 162.0,
   "q3": 169.0,
   "iqr": 7.0,
   "min": 159.0,
   "max": 173.0,
   "sd": 7.02
  }
 },
 "V1": {
  "spring_started_s": {
   "n": 3,
   "median": 3.09,
   "mean": 3.05,
   "q1": 3.03,
   "q3": 3.1,
   "iqr": 0.07,
   "min": 2.96,
   "max": 3.1,
   "sd": 0.08
  },
  "spring_process_running_s": {
   "n": 3,
   "median": 4.32,
   "mean": 4.16,
   "q1": 4.07,
   "q3": 4.33,
   "iqr": 0.25,
   "min": 3.83,
   "max": 4.33,
   "sd": 0.29
  },
  "start_to_received_ms": {
   "n": 3,
   "median": 177.0,
   "mean": 176.67,
   "q1": 174.0,
   "q3": 179.5,
   "iqr": 5.5,
   "min": 171.0,
   "max": 182.0,
   "sd": 5.51
  },
  "w_in_to_received_ms": {
   "n": 3,
   "median": 175.0,
   "mean": 175.0,
   "q1": 172.0,
   "q3": 178.0,
   "iqr": 6.0,
   "min": 169.0,
   "max": 181.0,
   "sd": 6.0
  },
  "received_to_h_in_ms": {
   "n": 3,
   "median": 60.0,
   "mean": 60.0,
   "q1": 60.0,
   "q3": 60.0,
   "iqr": 0.0,
   "min": 60.0,
   "max": 60.0,
   "sd": 0.0
  }
 },
 "V2": {
  "spring_started_s": {
   "n": 3,
   "median": 2.84,
   "mean": 2.72,
   "q1": 2.65,
   "q3": 2.85,
   "iqr": 0.19,
   "min": 2.47,
   "max": 2.86,
   "sd": 0.22
  },
  "spring_process_running_s": {
   "n": 3,
   "median": 3.65,
   "mean": 3.51,
   "q1": 3.43,
   "q3": 3.66,
   "iqr": 0.23,
   "min": 3.21,
   "max": 3.67,
   "sd": 0.26
  },
  "start_to_received_ms": {
   "n": 3,
   "median": 61.0,
   "mean": 56.33,
   "q1": 53.5,
   "q3": 61.5,
   "iqr": 8.0,
   "min": 46.0,
   "max": 62.0,
   "sd": 8.96
  },
  "w_in_to_received_ms": {
   "n": 3,
   "median": 59.0,
   "mean": 54.67,
   "q1": 52.0,
   "q3": 59.5,
   "iqr": 7.5,
   "min": 45.0,
   "max": 60.0,
   "sd": 8.39
  },
  "received_to_h_in_ms": {
   "n": 3,
   "median": 60.0,
   "mean": 67.0,
   "q1": 60.0,
   "q3": 70.5,
   "iqr": 10.5,
   "min": 60.0,
   "max": 81.0,
   "sd": 12.12
  }
 }
}
```

## 3c. Mesmas operações: V1 na 1ª chamada x V2 no init

```
[
 {
  "op": "repositório -> 1º beforeExecution",
  "v1_invoke_key": "svc_calc_done -> sdk_before_exec",
  "v2_init_key": "prep_json_in_done -> sdk_before_exec",
  "v1_invoke_ms": 281.3,
  "v2_init_ms": 64.2,
  "ratio": 4.38,
  "v1_thread_cpu_ms": 70.1,
  "v2_thread_cpu_ms": 56.0,
  "n": [
   3,
   3
  ]
 },
 {
  "op": "serialização, credenciais, assinatura",
  "v1_invoke_key": "sdk_before_exec -> sdk_before_tx",
  "v2_init_key": "sdk_before_exec -> sdk_before_tx",
  "v1_invoke_ms": 403.2,
  "v2_init_ms": 94.4,
  "ratio": 4.27,
  "v1_thread_cpu_ms": 107.0,
  "v2_thread_cpu_ms": 87.0,
  "n": [
   3,
   3
  ]
 },
 {
  "op": "1ª transmissão HTTP",
  "v1_invoke_key": "sdk_before_tx -> sdk_after_tx",
  "v2_init_key": "sdk_before_tx -> sdk_after_tx",
  "v1_invoke_ms": 1344.1,
  "v2_init_ms": 359.1,
  "ratio": 3.74,
  "v1_thread_cpu_ms": 264.6,
  "v2_thread_cpu_ms": 230.6,
  "n": [
   3,
   3
  ]
 },
 {
  "op": "pós-transmissão",
  "v1_invoke_key": "sdk_after_tx -> sdk_after_exec",
  "v2_init_key": "sdk_after_tx -> sdk_after_exec",
  "v1_invoke_ms": 98.0,
  "v2_init_ms": 24.0,
  "ratio": 4.08,
  "v1_thread_cpu_ms": 24.6,
  "v2_thread_cpu_ms": 19.7,
  "n": [
   3,
   3
  ]
 },
 {
  "op": "Jackson (mapper)",
  "v1_invoke_key": "h_in -> h_mapped",
  "v2_init_key": "prep_beans_done -> prep_json_in_done",
  "v1_invoke_ms": 182.9,
  "v2_init_ms": 78.8,
  "ratio": 2.32,
  "v1_thread_cpu_ms": 49.5,
  "v2_thread_cpu_ms": 70.2,
  "n": [
   3,
   3
  ]
 }
]
```

## 4. Comparações (diferença de medianas, IC bootstrap 95% descritivo)

```
{
 "V1_vs_V0": {
  "init_ms": {
   "median_a": 4422.9,
   "median_b": 3673.8,
   "diff": 749.1,
   "diff_pct": 20.4,
   "boot95": [
    -458.4,
    1029.5
   ]
  },
  "duration_ms": {
   "median_a": 2794.5,
   "median_b": 2692.6,
   "diff": 101.9,
   "diff_pct": 3.8,
   "boot95": [
    -2.2,
    194.8
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 7153.1,
   "median_b": 6366.4,
   "diff": 786.7,
   "diff_pct": 12.4,
   "boot95": [
    -396.2,
    1224.2
   ]
  },
  "warm_duration_ms": {
   "median_a": 97.8,
   "median_b": 77.1,
   "diff": 20.7,
   "diff_pct": 26.8,
   "boot95": [
    -53.6,
    92.4
   ]
  }
 },
 "V2_vs_V1": {
  "init_ms": {
   "median_a": 4405.9,
   "median_b": 4422.9,
   "diff": -17.0,
   "diff_pct": -0.4,
   "boot95": [
    -565.2,
    522.1
   ]
  },
  "duration_ms": {
   "median_a": 285.4,
   "median_b": 2794.5,
   "diff": -2509.1,
   "diff_pct": -89.8,
   "boot95": [
    -2553.0,
    -2408.5
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 4691.3,
   "median_b": 7153.1,
   "diff": -2461.8,
   "diff_pct": -34.4,
   "boot95": [
    -3118.2,
    -1950.7
   ]
  },
  "warm_duration_ms": {
   "median_a": 109.4,
   "median_b": 97.8,
   "diff": 11.6,
   "diff_pct": 11.9,
   "boot95": [
    -76.5,
    64.6
   ]
  }
 }
}
```

## 5. Fases (V1/V2): CPU, classes, JIT

```
{
 "V1/init": {
  "wall_ms": {
   "n": 3,
   "median": 3608.29,
   "mean": 3563.15,
   "q1": 3531.98,
   "q3": 3616.88,
   "iqr": 84.9,
   "min": 3455.67,
   "max": 3625.47,
   "sd": 93.47
  },
  "cls": {
   "n": 3,
   "median": 6128,
   "mean": 6127.33,
   "q1": 6127.0,
   "q3": 6128.0,
   "iqr": 1.0,
   "min": 6126,
   "max": 6128,
   "sd": 1.15
  },
  "jit_ms": {
   "n": 3,
   "median": 1009,
   "mean": 998.67,
   "q1": 991.0,
   "q3": 1011.5,
   "iqr": 20.5,
   "min": 973,
   "max": 1014,
   "sd": 22.37
  },
  "gc_ms": {
   "n": 3,
   "median": 178,
   "mean": 183.33,
   "q1": 177.0,
   "q3": 187.0,
   "iqr": 10.0,
   "min": 176,
   "max": 196,
   "sd": 11.02
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 2210.59,
   "mean": 2209.21,
   "q1": 2205.22,
   "q3": 2213.88,
   "iqr": 8.66,
   "min": 2199.85,
   "max": 2217.18,
   "sd": 8.75
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 3430.0,
   "mean": 3430.0,
   "q1": 3430.0,
   "q3": 3430.0,
   "iqr": 0.0,
   "min": 3430.0,
   "max": 3430.0,
   "sd": 0.0
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.45,
   "mean": 0.46,
   "q1": 0.45,
   "q3": 0.46,
   "iqr": 0.01,
   "min": 0.45,
   "max": 0.48,
   "sd": 0.01
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.01,
   "mean": 0.01,
   "q1": 0.01,
   "q3": 0.01,
   "iqr": 0.0,
   "min": 0.01,
   "max": 0.01,
   "sd": 0.0
  },
  "jiffies_total": {
   "n": 3,
   "median": 691,
   "mean": 691.67,
   "q1": 681.0,
   "q3": 702.0,
   "iqr": 21.0,
   "min": 671,
   "max": 713,
   "sd": 21.01
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.95,
   "mean": 0.96,
   "q1": 0.95,
   "q3": 0.97,
   "iqr": 0.02,
   "min": 0.95,
   "max": 0.99,
   "sd": 0.03
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.61,
   "mean": 0.62,
   "q1": 0.61,
   "q3": 0.63,
   "iqr": 0.01,
   "min": 0.61,
   "max": 0.64,
   "sd": 0.01
  },
  "from": [
   "init_wrapper_clinit"
  ],
  "to": [
   "init_end"
  ]
 },
 "V1/inv1": {
  "wall_ms": {
   "n": 3,
   "median": 2753.33,
   "mean": 2748.28,
   "q1": 2731.34,
   "q3": 2767.74,
   "iqr": 36.39,
   "min": 2709.36,
   "max": 2782.15,
   "sd": 36.66
  },
  "cls": {
   "n": 3,
   "median": 1903,
   "mean": 1906.0,
   "q1": 1903.0,
   "q3": 1907.5,
   "iqr": 4.5,
   "min": 1903,
   "max": 1912,
   "sd": 5.2
  },
  "jit_ms": {
   "n": 3,
   "median": 316,
   "mean": 326.0,
   "q1": 313.5,
   "q3": 333.5,
   "iqr": 20.0,
   "min": 311,
   "max": 351,
   "sd": 21.79
  },
  "gc_ms": {
   "n": 3,
   "median": 237,
   "mean": 231.0,
   "q1": 226.0,
   "q3": 239.0,
   "iqr": 13.0,
   "min": 215,
   "max": 241,
   "sd": 14.0
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 612.26,
   "mean": 613.05,
   "q1": 610.96,
   "q3": 614.75,
   "iqr": 3.79,
   "min": 609.65,
   "max": 617.23,
   "sd": 3.85
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 770.0,
   "mean": 776.67,
   "q1": 770.0,
   "q3": 780.0,
   "iqr": 10.0,
   "min": 770.0,
   "max": 790.0,
   "sd": 11.55
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.12,
   "mean": 0.12,
   "q1": 0.12,
   "q3": 0.13,
   "iqr": 0.0,
   "min": 0.12,
   "max": 0.13,
   "sd": 0.0
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.0,
   "sd": 0.0
  },
  "jiffies_total": {
   "n": 3,
   "median": 538,
   "mean": 537.0,
   "q1": 533.5,
   "q3": 541.0,
   "iqr": 7.5,
   "min": 529,
   "max": 544,
   "sd": 7.55
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.28,
   "mean": 0.28,
   "q1": 0.28,
   "q3": 0.28,
   "iqr": 0.0,
   "min": 0.28,
   "max": 0.28,
   "sd": 0.0
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.22,
   "mean": 0.22,
   "q1": 0.22,
   "q3": 0.22,
   "iqr": 0.0,
   "min": 0.22,
   "max": 0.23,
   "sd": 0.0
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ],
  "start_to_w_in_ms": {
   "n": 3,
   "median": 2.0,
   "mean": 1.67,
   "q1": 1.5,
   "q3": 2.0,
   "iqr": 0.5,
   "min": 1.0,
   "max": 2.0,
   "sd": 0.58
  },
  "w_out_to_end_ms": {
   "n": 3,
   "median": 39.04,
   "mean": 32.6,
   "q1": 29.13,
   "q3": 39.29,
   "iqr": 10.16,
   "min": 19.22,
   "max": 39.53,
   "sd": 11.59
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 3,
   "median": 0.99,
   "mean": 0.99,
   "q1": 0.99,
   "q3": 0.99,
   "iqr": 0.0,
   "min": 0.99,
   "max": 0.99,
   "sd": 0.0
  }
 },
 "V1/inv2": {
  "wall_ms": {
   "n": 3,
   "median": 95.43,
   "mean": 96.7,
   "q1": 74.4,
   "q3": 118.35,
   "iqr": 43.95,
   "min": 53.38,
   "max": 141.28,
   "sd": 43.96
  },
  "cls": {
   "n": 3,
   "median": 1,
   "mean": 1.0,
   "q1": 1.0,
   "q3": 1.0,
   "iqr": 0.0,
   "min": 1,
   "max": 1,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 14,
   "mean": 23.0,
   "q1": 12.5,
   "q3": 29.0,
   "iqr": 16.5,
   "min": 11,
   "max": 44,
   "sd": 18.25
  },
  "gc_ms": {
   "n": 3,
   "median": 0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0,
   "max": 0,
   "sd": 0.0
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 19.84,
   "mean": 19.68,
   "q1": 16.78,
   "q3": 22.67,
   "iqr": 5.89,
   "min": 13.71,
   "max": 25.5,
   "sd": 5.89
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 40.0,
   "mean": 30.0,
   "q1": 25.0,
   "q3": 40.0,
   "iqr": 15.0,
   "min": 10.0,
   "max": 40.0,
   "sd": 17.32
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.07,
   "mean": 0.11,
   "q1": 0.06,
   "q3": 0.14,
   "iqr": 0.07,
   "min": 0.06,
   "max": 0.2,
   "sd": 0.08
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.06,
   "mean": 0.04,
   "q1": 0.03,
   "q3": 0.06,
   "iqr": 0.04,
   "min": 0.0,
   "max": 0.07,
   "sd": 0.04
  },
  "jiffies_total": {
   "n": 3,
   "median": 18,
   "mean": 18.67,
   "q1": 14.0,
   "q3": 23.0,
   "iqr": 9.0,
   "min": 10,
   "max": 28,
   "sd": 9.02
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.28,
   "mean": 0.3,
   "q1": 0.24,
   "q3": 0.35,
   "iqr": 0.12,
   "min": 0.19,
   "max": 0.42,
   "sd": 0.12
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.21,
   "mean": 0.22,
   "q1": 0.19,
   "q3": 0.23,
   "iqr": 0.04,
   "min": 0.18,
   "max": 0.26,
   "sd": 0.04
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ]
 },
 "V1/meta": {
  "jvm_uptime_at_clinit_ms": {
   "n": 3,
   "median": 718.0,
   "mean": 614.0,
   "q1": 555.5,
   "q3": 724.5,
   "iqr": 169.0,
   "min": 393.0,
   "max": 731.0,
   "sd": 191.5
  },
  "cpus": {
   "n": 3,
   "median": 2.0,
   "mean": 2.0,
   "q1": 2.0,
   "q3": 2.0,
   "iqr": 0.0,
   "min": 2.0,
   "max": 2.0,
   "sd": 0.0
  },
  "init_start_to_jvm_start_ms": {
   "n": 3,
   "median": 327.0,
   "mean": 268.67,
   "q1": 233.5,
   "q3": 333.0,
   "iqr": 99.5,
   "min": 140.0,
   "max": 339.0,
   "sd": 111.59
  }
 },
 "V2/init": {
  "wall_ms": {
   "n": 3,
   "median": 3988.77,
   "mean": 3823.46,
   "q1": 3731.85,
   "q3": 3997.72,
   "iqr": 265.86,
   "min": 3474.93,
   "max": 4006.66,
   "sd": 301.96
  },
  "cls": {
   "n": 3,
   "median": 8023,
   "mean": 8020.67,
   "q1": 8019.5,
   "q3": 8023.0,
   "iqr": 3.5,
   "min": 8016,
   "max": 8023,
   "sd": 4.04
  },
  "jit_ms": {
   "n": 3,
   "median": 1162,
   "mean": 1104.33,
   "q1": 1069.0,
   "q3": 1168.5,
   "iqr": 99.5,
   "min": 976,
   "max": 1175,
   "sd": 111.33
  },
  "gc_ms": {
   "n": 3,
   "median": 266,
   "mean": 250.33,
   "q1": 239.5,
   "q3": 269.0,
   "iqr": 29.5,
   "min": 213,
   "max": 272,
   "sd": 32.47
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 2618.44,
   "mean": 2502.43,
   "q1": 2433.02,
   "q3": 2629.85,
   "iqr": 196.84,
   "min": 2247.59,
   "max": 2641.26,
   "sd": 220.99
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 3930.0,
   "mean": 3763.33,
   "q1": 3665.0,
   "q3": 3945.0,
   "iqr": 280.0,
   "min": 3400.0,
   "max": 3960.0,
   "sd": 315.01
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.48,
   "mean": 0.47,
   "q1": 0.47,
   "q3": 0.48,
   "iqr": 0.0,
   "min": 0.47,
   "max": 0.48,
   "sd": 0.0
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.01,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.01,
   "sd": 0.0
  },
  "jiffies_total": {
   "n": 3,
   "median": 774,
   "mean": 740.67,
   "q1": 723.0,
   "q3": 775.0,
   "iqr": 52.0,
   "min": 672,
   "max": 776,
   "sd": 59.48
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.99,
   "mean": 0.98,
   "q1": 0.98,
   "q3": 0.99,
   "iqr": 0.0,
   "min": 0.98,
   "max": 0.99,
   "sd": 0.01
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.66,
   "mean": 0.65,
   "q1": 0.65,
   "q3": 0.66,
   "iqr": 0.01,
   "min": 0.65,
   "max": 0.66,
   "sd": 0.01
  },
  "from": [
   "init_wrapper_clinit"
  ],
  "to": [
   "init_end"
  ]
 },
 "V2/inv1": {
  "wall_ms": {
   "n": 3,
   "median": 258.81,
   "mean": 255.48,
   "q1": 252.16,
   "q3": 260.46,
   "iqr": 8.29,
   "min": 245.51,
   "max": 262.1,
   "sd": 8.78
  },
  "cls": {
   "n": 3,
   "median": 50,
   "mean": 50.0,
   "q1": 50.0,
   "q3": 50.0,
   "iqr": 0.0,
   "min": 50,
   "max": 50,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 87,
   "mean": 84.33,
   "q1": 74.5,
   "q3": 95.5,
   "iqr": 21.0,
   "min": 62,
   "max": 104,
   "sd": 21.13
  },
  "gc_ms": {
   "n": 3,
   "median": 0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0,
   "max": 0,
   "sd": 0.0
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 52.54,
   "mean": 51.9,
   "q1": 47.99,
   "q3": 56.12,
   "iqr": 8.13,
   "min": 43.44,
   "max": 59.7,
   "sd": 8.15
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 70.0,
   "mean": 70.0,
   "q1": 65.0,
   "q3": 75.0,
   "iqr": 10.0,
   "min": 60.0,
   "max": 80.0,
   "sd": 10.0
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.1,
   "mean": 0.11,
   "q1": 0.09,
   "q3": 0.12,
   "iqr": 0.02,
   "min": 0.09,
   "max": 0.13,
   "sd": 0.03
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.01,
   "min": 0.0,
   "max": 0.02,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 3,
   "median": 49,
   "mean": 49.33,
   "q1": 48.0,
   "q3": 50.5,
   "iqr": 2.5,
   "min": 47,
   "max": 52,
   "sd": 2.52
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.27,
   "mean": 0.27,
   "q1": 0.26,
   "q3": 0.29,
   "iqr": 0.03,
   "min": 0.24,
   "max": 0.31,
   "sd": 0.03
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.2,
   "mean": 0.2,
   "q1": 0.19,
   "q3": 0.22,
   "iqr": 0.03,
   "min": 0.18,
   "max": 0.23,
   "sd": 0.03
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ],
  "start_to_w_in_ms": {
   "n": 3,
   "median": 2.0,
   "mean": 1.67,
   "q1": 1.5,
   "q3": 2.0,
   "iqr": 0.5,
   "min": 1.0,
   "max": 2.0,
   "sd": 0.58
  },
  "w_out_to_end_ms": {
   "n": 3,
   "median": 25.39,
   "mean": 35.03,
   "q1": 23.71,
   "q3": 41.53,
   "iqr": 17.82,
   "min": 22.03,
   "max": 57.68,
   "sd": 19.68
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 3,
   "median": 0.91,
   "mean": 0.88,
   "q1": 0.86,
   "q3": 0.91,
   "iqr": 0.05,
   "min": 0.81,
   "max": 0.91,
   "sd": 0.05
  }
 },
 "V2/inv2": {
  "wall_ms": {
   "n": 3,
   "median": 107.28,
   "mean": 90.56,
   "q1": 77.06,
   "q3": 112.42,
   "iqr": 35.37,
   "min": 46.84,
   "max": 117.57,
   "sd": 38.21
  },
  "cls": {
   "n": 3,
   "median": 1,
   "mean": 1.0,
   "q1": 1.0,
   "q3": 1.0,
   "iqr": 0.0,
   "min": 1,
   "max": 1,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 28,
   "mean": 21.67,
   "q1": 17.0,
   "q3": 29.5,
   "iqr": 12.5,
   "min": 6,
   "max": 31,
   "sd": 13.65
  },
  "gc_ms": {
   "n": 3,
   "median": 0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0,
   "max": 0,
   "sd": 0.0
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 17.85,
   "mean": 17.76,
   "q1": 15.16,
   "q3": 20.41,
   "iqr": 5.25,
   "min": 12.47,
   "max": 22.96,
   "sd": 5.25
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 30.0,
   "mean": 26.67,
   "q1": 25.0,
   "q3": 30.0,
   "iqr": 5.0,
   "min": 20.0,
   "max": 30.0,
   "sd": 5.77
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.14,
   "mean": 0.17,
   "q1": 0.14,
   "q3": 0.18,
   "iqr": 0.05,
   "min": 0.13,
   "max": 0.22,
   "sd": 0.05
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.02,
   "iqr": 0.02,
   "min": 0.0,
   "max": 0.04,
   "sd": 0.03
  },
  "jiffies_total": {
   "n": 3,
   "median": 21,
   "mean": 17.67,
   "q1": 15.0,
   "q3": 22.0,
   "iqr": 7.0,
   "min": 9,
   "max": 23,
   "sd": 7.57
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.28,
   "mean": 0.32,
   "q1": 0.27,
   "q3": 0.35,
   "iqr": 0.09,
   "min": 0.26,
   "max": 0.43,
   "sd": 0.09
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.2,
   "mean": 0.21,
   "q1": 0.18,
   "q3": 0.23,
   "iqr": 0.05,
   "min": 0.17,
   "max": 0.27,
   "sd": 0.05
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ]
 },
 "V2/meta": {
  "jvm_uptime_at_clinit_ms": {
   "n": 3,
   "median": 374.0,
   "mean": 369.67,
   "q1": 366.0,
   "q3": 375.5,
   "iqr": 9.5,
   "min": 358.0,
   "max": 377.0,
   "sd": 10.21
  },
  "cpus": {
   "n": 3,
   "median": 2.0,
   "mean": 2.0,
   "q1": 2.0,
   "q3": 2.0,
   "iqr": 0.0,
   "min": 2.0,
   "max": 2.0,
   "sd": 0.0
  },
  "init_start_to_jvm_start_ms": {
   "n": 3,
   "median": 131.0,
   "mean": 128.0,
   "q1": 121.5,
   "q3": 136.0,
   "iqr": 14.5,
   "min": 112.0,
   "max": 141.0,
   "sd": 14.73
  }
 }
}
```

## 6. Intervalos da 1ª chamada (medianas, ms) — ver `intervals.csv`

### V1 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| sdk_before_tx -> sdk_after_tx | 3 | 1344.1 | 886 | 224 | 264.6 |
| sdk_before_exec -> sdk_before_tx | 3 | 403.2 | 392 | 3 | 107.0 |
| svc_calc_done -> sdk_before_exec | 3 | 281.3 | 266 | 13 | 70.1 |
| w_in -> h_in | 3 | 234.8 | 138 | 3 | 65.2 |
| h_in -> h_mapped | 3 | 182.9 | 120 | 4 | 49.5 |
| h_out -> w_out | 3 | 117.6 | 28 | 44 | 21.6 |
| sdk_after_tx -> sdk_after_exec | 3 | 98.0 | 71 | 0 | 24.6 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 1 | 21.1 | 0 | 18 | 2.1 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 3 | 18.1 | 0 | 1 | 2.1 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 3 | 17.4 | 0 | 0 | 2.3 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 2 | 16.7 | 0 | 0 | 2.2 |
| h_mapped -> svc_in | 3 | 14.5 | 0 | 0 | 0.3 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 2 | 5.3 | 0 | 2 | 2.0 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 1 | 1.6 | 0 | 1 | 1.6 |
| svc_in -> svc_calc_done | 3 | 1.0 | 1 | 0 | 1.0 |
| svc_order_put_done -> sdk_before_exec#2 | 3 | 0.7 | 0 | 0 | 0.7 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 1 | 0.6 | 0 | 1 | 0.6 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 3 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 2 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 2 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 1 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec -> svc_order_put_done | 3 | 0.4 | 1 | 0 | 0.3 |
| sdk_after_exec#2 -> svc_stock_puts_done | 1 | 0.2 | 0 | 0 | 0.1 |
| sdk_after_exec#4 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#3 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.1 |
| svc_stock_puts_done -> h_out | 3 | 0.1 | 0 | 0 | 0.1 |

### V2 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| w_in -> h_in | 3 | 119.8 | 44 | 35 | 29.2 |
| h_out -> w_out | 3 | 39.5 | 5 | 6 | 7.2 |
| sdk_before_tx -> sdk_after_tx | 3 | 23.6 | 0 | 0 | 2.2 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 3 | 18.1 | 0 | 0 | 2.0 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 1 | 18.1 | 0 | 1 | 2.1 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 2 | 14.6 | 0 | 10 | 0.8 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 2 | 11.6 | 0 | 7 | 2.1 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 2 | 10.5 | 0 | 11 | 1.9 |
| sdk_before_exec -> sdk_before_tx | 3 | 2.2 | 1 | 1 | 2.2 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 3 | 1.7 | 0 | 2 | 1.7 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 1 | 1.6 | 0 | 0 | 1.6 |
| sdk_after_tx -> sdk_after_exec | 3 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 1 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 3 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 1 | 0.6 | 0 | 0 | 0.5 |
| svc_calc_done -> sdk_before_exec | 3 | 0.5 | 0 | 0 | 0.6 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 2 | 0.5 | 0 | 0 | 0.5 |
| h_in -> h_mapped | 3 | 0.5 | 0 | 1 | 0.4 |
| svc_order_put_done -> sdk_before_exec#2 | 3 | 0.4 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> svc_stock_puts_done | 1 | 0.2 | 0 | 0 | 0.1 |
| svc_in -> svc_calc_done | 3 | 0.2 | 0 | 0 | 0.2 |
| sdk_after_exec#4 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.2 |
| sdk_after_exec -> svc_order_put_done | 3 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#2 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.0 |
| svc_stock_puts_done -> h_out | 3 | 0.1 | 0 | 0 | 0.1 |
| h_mapped -> svc_in | 3 | 0.1 | 0 | 0 | 0.0 |

## 7. JVM

- JAVA_TOOL_OPTIONS: {'V1': [''], 'V2': ['']}
- args: {'V1': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so'], 'V2': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so']}
- /tmp na 1ª chamada: {'V1': ['hsperfdata_sbx_user1051'], 'V2': ['hsperfdata_sbx_user1051']}
