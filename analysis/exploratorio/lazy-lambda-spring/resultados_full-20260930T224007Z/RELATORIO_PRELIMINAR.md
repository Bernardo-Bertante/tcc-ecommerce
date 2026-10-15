# Relatório preliminar automático — exp-lazy-sb, Spring Boot (EXPLORATÓRIO, fora do desenho oficial)

RUN_ID `full-20260930T224007Z`. Gerado pelo driver na EC2. Apenas descritivo. Nenhum intervalo aqui é confirmatório. Fonte de cada número: `samples_final.csv`, `invocations.csv`, `points.csv`, `intervals.csv`, `phases.csv`, `summary.json`; L1 oficial: `l1_duration_postinit.csv`.

## 1. Amostras

- Frias válidas: {'V0': 30, 'V1': 30, 'V2': 30}; tentativas não frias/erro: {'V0': 0, 'V1': 0, 'V2': 0}
- Versões de runtime (INIT_START): {'V0': ['java:21.v68'], 'V1': ['java:21.v68'], 'V2': ['java:21.v68']}
- CodeSha256: {'V0': ['ODLvR0a13wdABKP6LvMTo/xvKxTpEUz3H79fgDg0bbg='], 'V1': ['L404Qp+XeWSAaSujHlNAfXB5lGJOeaOJxCkHlkbwSKI='], 'V2': ['L404Qp+XeWSAaSujHlNAfXB5lGJOeaOJxCkHlkbwSKI=']}
- Handler: {'V0': ['org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest'], 'V1': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest'], 'V2': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest']}

## 2. Por variante (ms; mediana [Q1–Q3] min–max, n)

| Variante | Init | Duration | Init + Duration | Duration 2ª chamada (quente) | Gap fim-init→START |
|---|---|---|---|---|---|
| V0 | 3834.0 [3704.7–4379.9] 3244.3–4844.7, n=30 | 2751.8 [2664.2–2803.1] 2524.3–2996.6, n=30 | 6630.5 [6369.8–7154.1] 5855.7–7841.3, n=30 | 83.1 [63.3–100.5] 48.8–139.0, n=30 | 3.9 [3.7–4.1] 2.9–5.1, n=30 |
| V1 | 3839.0 [3646.9–4252.9] 2452.7–4759.3, n=30 | 2729.7 [2626.8–2806.4] 1670.2–2949.1, n=30 | 6588.4 [6292.8–6964.7] 4122.9–7693.1, n=30 | 111.1 [75.2–126.0] 45.1–176.3, n=30 | 3.9 [3.5–4.0] 2.3–5.0, n=30 |
| V2 | 4539.0 [4434.1–4941.7] 4188.2–5447.7, n=30 | 304.0 [266.4–329.7] 233.9–382.3, n=30 | 4832.1 [4736.1–5270.1] 4449.2–5810.4, n=30 | 106.3 [80.4–118.0] 50.6–171.0, n=30 | 4.0 [3.6–4.3] 2.7–10.2, n=30 |
| L1 oficial SB | 3768.9 [3668.6–3821.2] 3105.5–4153.7, n=11 | 2773.7 [2693.1–2815.7] 2568.9–3058.7, n=11 | 6509.2 [6330.8–6643.1] 5879.2–7212.4, n=11 | — | — |

## 3. Controle (V0 × L1 oficial)

```
{
 "init_ms": {
  "v0_median": 3834.0,
  "l1_median": 3768.9,
  "diff_pct": 1.7,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -68.1,
   585.4
  ]
 },
 "duration_ms": {
  "v0_median": 2751.8,
  "l1_median": 2773.7,
  "diff_pct": -0.8,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -97.6,
   88.6
  ]
 },
 "rule": "controle OK se |diff| das medianas de Duration <= 10% (regra pré-definida na A3, descritiva); Init só reportado",
 "ok": true
}
```

Instrumentação (V1 x V0): {"rule": "sinalizar se |diff| das medianas de Duration V1 x V0 > 5% (regra pré-definida na A3)", "diff_pct": -0.8, "flag": false}

## 3b. Marcas do Spring (ms, log)

```
{
 "V0": {
  "spring_started_s": {
   "n": 30,
   "median": 2.94,
   "mean": 2.92,
   "q1": 2.77,
   "q3": 3.12,
   "iqr": 0.35,
   "min": 2.4,
   "max": 3.51,
   "sd": 0.26
  },
  "spring_process_running_s": {
   "n": 30,
   "median": 3.76,
   "mean": 3.92,
   "q1": 3.59,
   "q3": 4.28,
   "iqr": 0.69,
   "min": 3.19,
   "max": 4.75,
   "sd": 0.4
  },
  "start_to_received_ms": {
   "n": 30,
   "median": 170.0,
   "mean": 170.2,
   "q1": 165.75,
   "q3": 181.75,
   "iqr": 16.0,
   "min": 140.0,
   "max": 189.0,
   "sd": 12.1
  }
 },
 "V1": {
  "spring_started_s": {
   "n": 30,
   "median": 2.9,
   "mean": 2.82,
   "q1": 2.73,
   "q3": 2.99,
   "iqr": 0.26,
   "min": 1.81,
   "max": 3.23,
   "sd": 0.29
  },
  "spring_process_running_s": {
   "n": 30,
   "median": 3.79,
   "mean": 3.82,
   "q1": 3.57,
   "q3": 4.15,
   "iqr": 0.58,
   "min": 2.4,
   "max": 4.61,
   "sd": 0.43
  },
  "start_to_received_ms": {
   "n": 30,
   "median": 164.0,
   "mean": 160.7,
   "q1": 153.25,
   "q3": 170.75,
   "iqr": 17.5,
   "min": 91.0,
   "max": 182.0,
   "sd": 16.56
  },
  "w_in_to_received_ms": {
   "n": 30,
   "median": 162.5,
   "mean": 158.93,
   "q1": 152.25,
   "q3": 169.0,
   "iqr": 16.75,
   "min": 90.0,
   "max": 179.0,
   "sd": 16.3
  },
  "received_to_h_in_ms": {
   "n": 30,
   "median": 59.0,
   "mean": 55.43,
   "q1": 56.25,
   "q3": 60.0,
   "iqr": 3.75,
   "min": 21.0,
   "max": 76.0,
   "sd": 10.13
  }
 },
 "V2": {
  "spring_started_s": {
   "n": 30,
   "median": 2.95,
   "mean": 2.88,
   "q1": 2.81,
   "q3": 3.0,
   "iqr": 0.19,
   "min": 2.35,
   "max": 3.2,
   "sd": 0.21
  },
  "spring_process_running_s": {
   "n": 30,
   "median": 3.77,
   "mean": 3.86,
   "q1": 3.67,
   "q3": 4.11,
   "iqr": 0.44,
   "min": 3.44,
   "max": 4.49,
   "sd": 0.29
  },
  "start_to_received_ms": {
   "n": 30,
   "median": 49.5,
   "mean": 50.1,
   "q1": 45.0,
   "q3": 56.75,
   "iqr": 11.75,
   "min": 33.0,
   "max": 63.0,
   "sd": 8.4
  },
  "w_in_to_received_ms": {
   "n": 30,
   "median": 48.5,
   "mean": 48.33,
   "q1": 43.0,
   "q3": 54.75,
   "iqr": 11.75,
   "min": 31.0,
   "max": 61.0,
   "sd": 8.34
  },
  "received_to_h_in_ms": {
   "n": 30,
   "median": 63.0,
   "mean": 66.83,
   "q1": 59.0,
   "q3": 77.75,
   "iqr": 18.75,
   "min": 46.0,
   "max": 81.0,
   "sd": 9.91
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
  "v1_invoke_ms": 262.9,
  "v2_init_ms": 67.1,
  "ratio": 3.92,
  "v1_thread_cpu_ms": 67.5,
  "v2_thread_cpu_ms": 56.4,
  "n": [
   30,
   30
  ]
 },
 {
  "op": "serialização, credenciais, assinatura",
  "v1_invoke_key": "sdk_before_exec -> sdk_before_tx",
  "v2_init_key": "sdk_before_exec -> sdk_before_tx",
  "v1_invoke_ms": 384.6,
  "v2_init_ms": 97.4,
  "ratio": 3.95,
  "v1_thread_cpu_ms": 103.2,
  "v2_thread_cpu_ms": 89.7,
  "n": [
   30,
   30
  ]
 },
 {
  "op": "1ª transmissão HTTP",
  "v1_invoke_key": "sdk_before_tx -> sdk_after_tx",
  "v2_init_key": "sdk_before_tx -> sdk_after_tx",
  "v1_invoke_ms": 1347.5,
  "v2_init_ms": 362.8,
  "ratio": 3.71,
  "v1_thread_cpu_ms": 256.9,
  "v2_thread_cpu_ms": 233.1,
  "n": [
   30,
   30
  ]
 },
 {
  "op": "pós-transmissão",
  "v1_invoke_key": "sdk_after_tx -> sdk_after_exec",
  "v2_init_key": "sdk_after_tx -> sdk_after_exec",
  "v1_invoke_ms": 89.0,
  "v2_init_ms": 21.0,
  "ratio": 4.24,
  "v1_thread_cpu_ms": 23.5,
  "v2_thread_cpu_ms": 20.3,
  "n": [
   30,
   30
  ]
 },
 {
  "op": "Jackson (mapper)",
  "v1_invoke_key": "h_in -> h_mapped",
  "v2_init_key": "prep_beans_done -> prep_json_in_done",
  "v1_invoke_ms": 182.5,
  "v2_init_ms": 81.9,
  "ratio": 2.23,
  "v1_thread_cpu_ms": 48.0,
  "v2_thread_cpu_ms": 69.6,
  "n": [
   30,
   30
  ]
 }
]
```

## 4. Comparações (diferença de medianas, IC bootstrap 95% descritivo)

```
{
 "V1_vs_V0": {
  "init_ms": {
   "median_a": 3839.0,
   "median_b": 3834.0,
   "diff": 4.9,
   "diff_pct": 0.1,
   "boot95": [
    -560.2,
    228.8
   ]
  },
  "duration_ms": {
   "median_a": 2729.7,
   "median_b": 2751.8,
   "diff": -22.1,
   "diff_pct": -0.8,
   "boot95": [
    -88.9,
    47.0
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 6588.4,
   "median_b": 6630.5,
   "diff": -42.2,
   "diff_pct": -0.6,
   "boot95": [
    -540.1,
    265.7
   ]
  },
  "warm_duration_ms": {
   "median_a": 111.1,
   "median_b": 83.1,
   "diff": 28.0,
   "diff_pct": 33.7,
   "boot95": [
    0.7,
    42.2
   ]
  }
 },
 "V2_vs_V1": {
  "init_ms": {
   "median_a": 4539.0,
   "median_b": 3839.0,
   "diff": 700.0,
   "diff_pct": 18.2,
   "boot95": [
    484.2,
    898.6
   ]
  },
  "duration_ms": {
   "median_a": 304.0,
   "median_b": 2729.7,
   "diff": -2425.7,
   "diff_pct": -88.9,
   "boot95": [
    -2485.9,
    -2371.6
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 4832.1,
   "median_b": 6588.4,
   "diff": -1756.3,
   "diff_pct": -26.7,
   "boot95": [
    -2009.2,
    -1506.8
   ]
  },
  "warm_duration_ms": {
   "median_a": 106.3,
   "median_b": 111.1,
   "diff": -4.8,
   "diff_pct": -4.3,
   "boot95": [
    -22.3,
    21.3
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
   "n": 30,
   "median": 3358.72,
   "mean": 3288.55,
   "q1": 3169.21,
   "q3": 3482.37,
   "iqr": 313.16,
   "min": 2120.57,
   "max": 3762.15,
   "sd": 333.39
  },
  "cls": {
   "n": 30,
   "median": 6118.5,
   "mean": 6119.33,
   "q1": 6112.25,
   "q3": 6124.75,
   "iqr": 12.5,
   "min": 6103,
   "max": 6137,
   "sd": 9.54
  },
  "jit_ms": {
   "n": 30,
   "median": 951.0,
   "mean": 927.97,
   "q1": 909.75,
   "q3": 997.75,
   "iqr": 88.0,
   "min": 615,
   "max": 1060,
   "sd": 106.5
  },
  "gc_ms": {
   "n": 30,
   "median": 177.0,
   "mean": 177.17,
   "q1": 170.25,
   "q3": 185.0,
   "iqr": 14.75,
   "min": 142,
   "max": 211,
   "sd": 13.59
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 2127.18,
   "mean": 2053.87,
   "q1": 2019.67,
   "q3": 2195.56,
   "iqr": 175.89,
   "min": 1296.41,
   "max": 2278.1,
   "sd": 224.7
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 3305.0,
   "mean": 3194.33,
   "q1": 3135.0,
   "q3": 3390.0,
   "iqr": 255.0,
   "min": 2100.0,
   "max": 3510.0,
   "sd": 322.05
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.47,
   "mean": 0.47,
   "q1": 0.46,
   "q3": 0.48,
   "iqr": 0.02,
   "min": 0.44,
   "max": 0.49,
   "sd": 0.01
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.01,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.01,
   "min": 0.0,
   "max": 0.07,
   "sd": 0.02
  },
  "jiffies_total": {
   "n": 30,
   "median": 654.5,
   "mean": 643.3,
   "q1": 612.0,
   "q3": 681.0,
   "iqr": 69.0,
   "min": 414,
   "max": 771,
   "sd": 69.09
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.99,
   "mean": 0.97,
   "q1": 0.95,
   "q3": 0.99,
   "iqr": 0.04,
   "min": 0.93,
   "max": 1.0,
   "sd": 0.02
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.63,
   "mean": 0.62,
   "q1": 0.61,
   "q3": 0.64,
   "iqr": 0.03,
   "min": 0.59,
   "max": 0.64,
   "sd": 0.02
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
   "n": 30,
   "median": 2688.97,
   "mean": 2643.88,
   "q1": 2592.9,
   "q3": 2761.16,
   "iqr": 168.26,
   "min": 1648.48,
   "max": 2891.37,
   "sd": 227.66
  },
  "cls": {
   "n": 30,
   "median": 1916.0,
   "mean": 1917.57,
   "q1": 1913.5,
   "q3": 1925.0,
   "iqr": 11.5,
   "min": 1903,
   "max": 1925,
   "sd": 8.17
  },
  "jit_ms": {
   "n": 30,
   "median": 324.5,
   "mean": 322.23,
   "q1": 297.5,
   "q3": 363.0,
   "iqr": 65.5,
   "min": 170,
   "max": 441,
   "sd": 60.77
  },
  "gc_ms": {
   "n": 30,
   "median": 223.5,
   "mean": 221.9,
   "q1": 206.0,
   "q3": 237.0,
   "iqr": 31.0,
   "min": 162,
   "max": 278,
   "sd": 23.8
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 595.1,
   "mean": 578.13,
   "q1": 562.23,
   "q3": 617.08,
   "iqr": 54.84,
   "min": 357.63,
   "max": 645.21,
   "sd": 61.04
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 770.0,
   "mean": 741.33,
   "q1": 720.0,
   "q3": 787.5,
   "iqr": 67.5,
   "min": 480.0,
   "max": 830.0,
   "sd": 72.53
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.12,
   "mean": 0.12,
   "q1": 0.12,
   "q3": 0.13,
   "iqr": 0.01,
   "min": 0.09,
   "max": 0.13,
   "sd": 0.01
  },
  "steal_frac_procstat": {
   "n": 30,
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
   "n": 30,
   "median": 528.5,
   "mean": 518.17,
   "q1": 504.75,
   "q3": 540.75,
   "iqr": 36.0,
   "min": 323,
   "max": 569,
   "sd": 45.24
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.29,
   "mean": 0.28,
   "q1": 0.28,
   "q3": 0.29,
   "iqr": 0.01,
   "min": 0.23,
   "max": 0.29,
   "sd": 0.02
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.22,
   "mean": 0.22,
   "q1": 0.22,
   "q3": 0.23,
   "iqr": 0.01,
   "min": 0.18,
   "max": 0.23,
   "sd": 0.02
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ],
  "start_to_w_in_ms": {
   "n": 30,
   "median": 2.0,
   "mean": 1.77,
   "q1": 1.25,
   "q3": 2.0,
   "iqr": 0.75,
   "min": 1.0,
   "max": 3.0,
   "sd": 0.5
  },
  "w_out_to_end_ms": {
   "n": 30,
   "median": 39.17,
   "mean": 38.7,
   "q1": 36.1,
   "q3": 42.12,
   "iqr": 6.02,
   "min": 19.01,
   "max": 61.76,
   "sd": 11.76
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 30,
   "median": 0.98,
   "mean": 0.99,
   "q1": 0.98,
   "q3": 0.99,
   "iqr": 0.0,
   "min": 0.98,
   "max": 0.99,
   "sd": 0.0
  }
 },
 "V1/inv2": {
  "wall_ms": {
   "n": 30,
   "median": 96.53,
   "mean": 94.18,
   "q1": 63.25,
   "q3": 119.29,
   "iqr": 56.03,
   "min": 42.89,
   "max": 154.92,
   "sd": 31.92
  },
  "cls": {
   "n": 30,
   "median": 1.0,
   "mean": 1.0,
   "q1": 1.0,
   "q3": 1.0,
   "iqr": 0.0,
   "min": 1,
   "max": 1,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 42.5,
   "mean": 970.7,
   "q1": 15.0,
   "q3": 70.25,
   "iqr": 55.25,
   "min": 5,
   "max": 5266,
   "sd": 1841.14
  },
  "gc_ms": {
   "n": 30,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0,
   "max": 0,
   "sd": 0.0
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 19.33,
   "mean": 19.15,
   "q1": 14.34,
   "q3": 23.66,
   "iqr": 9.32,
   "min": 10.82,
   "max": 26.76,
   "sd": 4.98
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 30.0,
   "mean": 31.67,
   "q1": 20.0,
   "q3": 40.0,
   "iqr": 20.0,
   "min": 10.0,
   "max": 50.0,
   "sd": 12.06
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.14,
   "mean": 0.13,
   "q1": 0.09,
   "q3": 0.16,
   "iqr": 0.07,
   "min": 0.0,
   "max": 0.22,
   "sd": 0.05
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.05,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 19.5,
   "mean": 17.87,
   "q1": 12.0,
   "q3": 22.0,
   "iqr": 10.0,
   "min": 7,
   "max": 28,
   "sd": 6.23
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.33,
   "mean": 0.34,
   "q1": 0.3,
   "q3": 0.39,
   "iqr": 0.09,
   "min": 0.21,
   "max": 0.51,
   "sd": 0.07
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.2,
   "mean": 0.21,
   "q1": 0.2,
   "q3": 0.22,
   "iqr": 0.03,
   "min": 0.16,
   "max": 0.28,
   "sd": 0.03
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
   "n": 30,
   "median": 428.5,
   "mean": 544.7,
   "q1": 374.75,
   "q3": 717.5,
   "iqr": 342.75,
   "min": 296.0,
   "max": 903.0,
   "sd": 190.5
  },
  "cpus": {
   "n": 30,
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
   "n": 30,
   "median": 147.0,
   "mean": 237.6,
   "q1": 130.0,
   "q3": 372.25,
   "iqr": 242.25,
   "min": 114.0,
   "max": 447.0,
   "sd": 123.65
  }
 },
 "V2/init": {
  "wall_ms": {
   "n": 30,
   "median": 4115.81,
   "mean": 4059.15,
   "q1": 3941.58,
   "q3": 4225.64,
   "iqr": 284.07,
   "min": 3380.8,
   "max": 4560.83,
   "sd": 286.07
  },
  "cls": {
   "n": 30,
   "median": 8023.0,
   "mean": 8022.23,
   "q1": 8021.0,
   "q3": 8023.75,
   "iqr": 2.75,
   "min": 8015,
   "max": 8028,
   "sd": 3.05
  },
  "jit_ms": {
   "n": 30,
   "median": 1090.5,
   "mean": 1073.77,
   "q1": 1038.75,
   "q3": 1133.75,
   "iqr": 95.0,
   "min": 788,
   "max": 1268,
   "sd": 116.8
  },
  "gc_ms": {
   "n": 30,
   "median": 248.0,
   "mean": 244.93,
   "q1": 238.25,
   "q3": 254.75,
   "iqr": 16.5,
   "min": 199,
   "max": 286,
   "sd": 18.21
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 2685.49,
   "mean": 2602.2,
   "q1": 2583.29,
   "q3": 2720.17,
   "iqr": 136.87,
   "min": 2055.27,
   "max": 2859.93,
   "sd": 220.46
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 4020.0,
   "mean": 3908.33,
   "q1": 3875.0,
   "q3": 4077.5,
   "iqr": 202.5,
   "min": 3120.0,
   "max": 4270.0,
   "sd": 304.78
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.47,
   "mean": 0.46,
   "q1": 0.45,
   "q3": 0.47,
   "iqr": 0.02,
   "min": 0.44,
   "max": 0.48,
   "sd": 0.01
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.01,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.01,
   "min": 0.0,
   "max": 0.05,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 801.5,
   "mean": 793.83,
   "q1": 765.75,
   "q3": 835.5,
   "iqr": 69.75,
   "min": 665,
   "max": 907,
   "sd": 57.3
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.98,
   "mean": 0.96,
   "q1": 0.94,
   "q3": 0.99,
   "iqr": 0.05,
   "min": 0.92,
   "max": 0.99,
   "sd": 0.03
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.65,
   "mean": 0.64,
   "q1": 0.63,
   "q3": 0.66,
   "iqr": 0.03,
   "min": 0.6,
   "max": 0.66,
   "sd": 0.02
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
   "n": 30,
   "median": 249.51,
   "mean": 257.36,
   "q1": 227.71,
   "q3": 290.78,
   "iqr": 63.07,
   "min": 188.42,
   "max": 334.85,
   "sd": 39.77
  },
  "cls": {
   "n": 30,
   "median": 50.0,
   "mean": 50.0,
   "q1": 50.0,
   "q3": 50.0,
   "iqr": 0.0,
   "min": 50,
   "max": 50,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 68.5,
   "mean": 77.43,
   "q1": 51.5,
   "q3": 89.5,
   "iqr": 38.0,
   "min": 29,
   "max": 182,
   "sd": 34.29
  },
  "gc_ms": {
   "n": 30,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0,
   "max": 0,
   "sd": 0.0
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 51.98,
   "mean": 53.33,
   "q1": 48.97,
   "q3": 58.2,
   "iqr": 9.24,
   "min": 46.78,
   "max": 61.86,
   "sd": 4.99
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 70.0,
   "mean": 76.0,
   "q1": 70.0,
   "q3": 80.0,
   "iqr": 10.0,
   "min": 60.0,
   "max": 100.0,
   "sd": 10.03
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.12,
   "mean": 0.12,
   "q1": 0.1,
   "q3": 0.13,
   "iqr": 0.03,
   "min": 0.05,
   "max": 0.17,
   "sd": 0.03
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.05,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 47.5,
   "mean": 49.57,
   "q1": 44.25,
   "q3": 56.5,
   "iqr": 12.25,
   "min": 37,
   "max": 64,
   "sd": 7.5
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.3,
   "mean": 0.3,
   "q1": 0.28,
   "q3": 0.32,
   "iqr": 0.04,
   "min": 0.24,
   "max": 0.37,
   "sd": 0.03
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.21,
   "mean": 0.21,
   "q1": 0.2,
   "q3": 0.23,
   "iqr": 0.03,
   "min": 0.16,
   "max": 0.25,
   "sd": 0.02
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ],
  "start_to_w_in_ms": {
   "n": 30,
   "median": 2.0,
   "mean": 1.77,
   "q1": 1.25,
   "q3": 2.0,
   "iqr": 0.75,
   "min": 1.0,
   "max": 3.0,
   "sd": 0.5
  },
  "w_out_to_end_ms": {
   "n": 30,
   "median": 41.3,
   "mean": 43.05,
   "q1": 39.43,
   "q3": 54.99,
   "iqr": 15.56,
   "min": 19.56,
   "max": 77.5,
   "sd": 14.07
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 30,
   "median": 0.85,
   "mean": 0.85,
   "q1": 0.82,
   "q3": 0.88,
   "iqr": 0.06,
   "min": 0.76,
   "max": 0.93,
   "sd": 0.04
  }
 },
 "V2/inv2": {
  "wall_ms": {
   "n": 30,
   "median": 98.41,
   "mean": 91.6,
   "q1": 75.13,
   "q3": 107.97,
   "iqr": 32.84,
   "min": 45.63,
   "max": 150.27,
   "sd": 25.24
  },
  "cls": {
   "n": 30,
   "median": 1.0,
   "mean": 1.0,
   "q1": 1.0,
   "q3": 1.0,
   "iqr": 0.0,
   "min": 1,
   "max": 1,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 42.0,
   "mean": 1566.47,
   "q1": 25.0,
   "q3": 2603.75,
   "iqr": 2578.75,
   "min": 4,
   "max": 5225,
   "sd": 2087.87
  },
  "gc_ms": {
   "n": 30,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0,
   "max": 0,
   "sd": 0.0
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 18.64,
   "mean": 18.22,
   "q1": 14.23,
   "q3": 21.75,
   "iqr": 7.52,
   "min": 12.93,
   "max": 24.31,
   "sd": 3.85
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 30.0,
   "mean": 28.0,
   "q1": 20.0,
   "q3": 37.5,
   "iqr": 17.5,
   "min": 10.0,
   "max": 40.0,
   "sd": 9.25
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.11,
   "mean": 0.11,
   "q1": 0.06,
   "q3": 0.14,
   "iqr": 0.09,
   "min": 0.0,
   "max": 0.22,
   "sd": 0.05
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.07,
   "sd": 0.02
  },
  "jiffies_total": {
   "n": 30,
   "median": 18.0,
   "mean": 16.87,
   "q1": 14.0,
   "q3": 19.75,
   "iqr": 5.75,
   "min": 9,
   "max": 29,
   "sd": 4.69
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.31,
   "mean": 0.31,
   "q1": 0.26,
   "q3": 0.37,
   "iqr": 0.11,
   "min": 0.13,
   "max": 0.44,
   "sd": 0.08
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.2,
   "mean": 0.21,
   "q1": 0.18,
   "q3": 0.22,
   "iqr": 0.03,
   "min": 0.16,
   "max": 0.29,
   "sd": 0.03
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
   "n": 30,
   "median": 407.5,
   "mean": 526.93,
   "q1": 381.0,
   "q3": 709.75,
   "iqr": 328.75,
   "min": 349.0,
   "max": 777.0,
   "sd": 168.58
  },
  "cpus": {
   "n": 30,
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
   "n": 30,
   "median": 153.5,
   "mean": 225.47,
   "q1": 137.0,
   "q3": 330.75,
   "iqr": 193.75,
   "min": 103.0,
   "max": 407.0,
   "sd": 105.39
  }
 }
}
```

## 6. Intervalos da 1ª chamada (medianas, ms) — ver `intervals.csv`

### V1 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| sdk_before_tx -> sdk_after_tx | 30 | 1347.5 | 899 | 226 | 256.9 |
| sdk_before_exec -> sdk_before_tx | 30 | 384.6 | 392 | 3 | 103.2 |
| svc_calc_done -> sdk_before_exec | 30 | 262.9 | 266 | 1 | 67.5 |
| w_in -> h_in | 30 | 215.6 | 138 | 3 | 62.5 |
| h_in -> h_mapped | 30 | 182.5 | 120 | 5 | 48.0 |
| h_out -> w_out | 30 | 104.3 | 28 | 45 | 20.6 |
| sdk_after_tx -> sdk_after_exec | 30 | 89.0 | 71 | 0 | 23.5 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 11 | 21.5 | 0 | 19 | 2.1 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 30 | 21.0 | 0 | 0 | 2.4 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 19 | 12.8 | 0 | 0 | 2.1 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 30 | 2.3 | 0 | 1 | 2.1 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 19 | 1.8 | 0 | 2 | 1.8 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 11 | 1.7 | 0 | 1 | 1.8 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 11 | 0.9 | 0 | 0 | 0.7 |
| svc_in -> svc_calc_done | 30 | 0.9 | 1 | 1 | 0.9 |
| svc_order_put_done -> sdk_before_exec#2 | 30 | 0.7 | 0 | 0 | 0.7 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 30 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 19 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 19 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 11 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec -> svc_order_put_done | 30 | 0.4 | 1 | 0 | 0.3 |
| h_mapped -> svc_in | 30 | 0.2 | 0 | 0 | 0.1 |
| sdk_after_exec#4 -> svc_stock_puts_done | 11 | 0.2 | 0 | 0 | 0.1 |
| sdk_after_exec#2 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#3 -> svc_stock_puts_done | 8 | 0.1 | 0 | 0 | 0.1 |
| svc_stock_puts_done -> h_out | 30 | 0.1 | 0 | 0 | 0.1 |

### V2 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| w_in -> h_in | 30 | 114.2 | 44 | 22 | 29.5 |
| h_out -> w_out | 30 | 40.1 | 5 | 22 | 7.3 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 19 | 21.3 | 0 | 1 | 2.1 |
| sdk_before_tx -> sdk_after_tx | 30 | 21.2 | 0 | 0 | 2.2 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 30 | 18.6 | 0 | 1 | 2.2 |
| sdk_before_exec -> sdk_before_tx | 30 | 18.6 | 1 | 1 | 2.4 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 11 | 18.4 | 0 | 1 | 2.1 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 19 | 1.7 | 0 | 2 | 1.8 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 11 | 1.7 | 0 | 0 | 1.6 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 30 | 1.6 | 0 | 2 | 1.7 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 19 | 0.7 | 0 | 0 | 0.6 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 30 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 11 | 0.6 | 0 | 1 | 0.6 |
| sdk_after_tx -> sdk_after_exec | 30 | 0.6 | 0 | 0 | 0.5 |
| svc_calc_done -> sdk_before_exec | 30 | 0.5 | 0 | 1 | 0.6 |
| h_in -> h_mapped | 30 | 0.5 | 0 | 0 | 0.4 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 11 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 19 | 0.5 | 0 | 0 | 0.5 |
| svc_order_put_done -> sdk_before_exec#2 | 30 | 0.4 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> svc_stock_puts_done | 8 | 0.2 | 0 | 0 | 0.1 |
| svc_in -> svc_calc_done | 30 | 0.2 | 0 | 0 | 0.2 |
| sdk_after_exec#4 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.2 |
| svc_stock_puts_done -> h_out | 30 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec -> svc_order_put_done | 30 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#2 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.1 |
| h_mapped -> svc_in | 30 | 0.1 | 0 | 0 | 0.1 |

## 7. JVM

- JAVA_TOOL_OPTIONS: {'V1': [''], 'V2': ['']}
- args: {'V1': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so'], 'V2': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so']}
- /tmp na 1ª chamada: {'V1': ['hsperfdata_sbx_user1051'], 'V2': ['hsperfdata_sbx_user1051']}
