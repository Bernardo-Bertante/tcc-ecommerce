# Relatório preliminar automático — exp-lazy (EXPLORATÓRIO, fora do desenho oficial)

RUN_ID `full-20260929T221755Z`. Gerado pelo driver na EC2. Apenas descritivo. Nenhum intervalo aqui é confirmatório. Fonte de cada número: `samples_final.csv`, `invocations.csv`, `points.csv`, `intervals.csv`, `phases.csv`, `summary.json`; L1 oficial: `l1_duration_postinit.csv`.

## 1. Amostras

- Frias válidas: {'V0': 30, 'V1': 30, 'V2': 30}; tentativas não frias/erro: {'V0': 0, 'V1': 0, 'V2': 0}
- Versões de runtime (INIT_START): {'V0': ['java:21.v68'], 'V1': ['java:21.v68'], 'V2': ['java:21.v68']}
- CodeSha256: {'V0': ['qqGaGUSyL1rtWwcwOeIMNhFYfsW+HvIh8QiUTPe+WME='], 'V1': ['RTtmKw35s7nPa1IzWSFMtzk8lznzf9Dy72LqBZdfSn4='], 'V2': ['RTtmKw35s7nPa1IzWSFMtzk8lznzf9Dy72LqBZdfSn4=']}
- Handler: {'V0': ['io.quarkus.funqy.lambda.FunqyStreamHandler::handleRequest'], 'V1': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest'], 'V2': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest']}

## 2. Por variante (ms; mediana [Q1–Q3] min–max, n)

| Variante | Init | Duration | Init + Duration | Duration 2ª chamada (quente) | Gap fim-init→START |
|---|---|---|---|---|---|
| V0 | 1454.8 [1393.9–1804.0] 1196.1–1990.2, n=30 | 5500.8 [5359.4–5715.7] 3610.7–6004.7, n=30 | 6968.3 [6772.2–7420.6] 5307.9–7890.5, n=30 | 73.3 [54.8–91.5] 31.2–107.8, n=30 | 3.9 [3.6–4.1] 2.8–5.4, n=30 |
| V1 | 1459.5 [1403.3–1841.9] 1146.8–1972.7, n=30 | 5432.5 [5326.1–5544.5] 4685.5–5871.3, n=30 | 6904.3 [6729.1–7350.6] 5899.2–7661.1, n=30 | 96.4 [58.0–119.7] 47.5–146.8, n=30 | 3.9 [3.3–4.1] 2.4–5.1, n=30 |
| V2 | 2927.2 [2863.8–3184.2] 2766.2–3678.1, n=30 | 347.1 [328.4–394.5] 306.0–447.1, n=30 | 3298.0 [3202.1–3616.5] 3091.5–4081.8, n=30 | 94.7 [71.1–122.5] 50.0–160.3, n=30 | 3.8 [3.3–4.3] 3.0–6.2, n=30 |
| L1 oficial QJ | 1382.6 [1366.5–1406.4] 1314.9–1470.1, n=10 | 5620.4 [5468.8–5729.8] 5315.1–5842.5, n=10 | 6999.7 [6896.7–7141.4] 6637.5–7254.3, n=10 | — | — |

## 3. Controle (V0 × L1 oficial)

```
{
 "init_ms": {
  "v0_median": 1454.8,
  "l1_median": 1382.6,
  "diff_pct": 5.2,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   9.9,
   355.0
  ]
 },
 "duration_ms": {
  "v0_median": 5500.8,
  "l1_median": 5620.4,
  "diff_pct": -2.1,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -280.6,
   92.1
  ]
 },
 "rule": "controle OK se |diff| das medianas <= 10% em Init e Duration (regra pré-definida, descritiva)",
 "ok": true
}
```

## 4. Comparações (diferença de medianas, IC bootstrap 95% descritivo)

```
{
 "V1_vs_V0": {
  "init_ms": {
   "median_a": 1459.6,
   "median_b": 1454.8,
   "diff": 4.8,
   "diff_pct": 0.3,
   "boot95": [
    -281.5,
    229.1
   ]
  },
  "duration_ms": {
   "median_a": 5432.5,
   "median_b": 5500.8,
   "diff": -68.3,
   "diff_pct": -1.2,
   "boot95": [
    -220.3,
    53.5
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 6904.3,
   "median_b": 6968.3,
   "diff": -63.9,
   "diff_pct": -0.9,
   "boot95": [
    -438.7,
    212.7
   ]
  },
  "warm_duration_ms": {
   "median_a": 96.4,
   "median_b": 73.3,
   "diff": 23.1,
   "diff_pct": 31.6,
   "boot95": [
    -13.0,
    49.2
   ]
  }
 },
 "V2_vs_V1": {
  "init_ms": {
   "median_a": 2927.2,
   "median_b": 1459.6,
   "diff": 1467.6,
   "diff_pct": 100.6,
   "boot95": [
    1236.8,
    1629.6
   ]
  },
  "duration_ms": {
   "median_a": 347.1,
   "median_b": 5432.5,
   "diff": -5085.4,
   "diff_pct": -93.6,
   "boot95": [
    -5164.3,
    -4996.6
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 3298.0,
   "median_b": 6904.3,
   "diff": -3606.3,
   "diff_pct": -52.2,
   "boot95": [
    -3866.4,
    -3391.6
   ]
  },
  "warm_duration_ms": {
   "median_a": 94.7,
   "median_b": 96.4,
   "diff": -1.7,
   "diff_pct": -1.8,
   "boot95": [
    -26.0,
    36.6
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
   "median": 1101.62,
   "mean": 1096.3,
   "q1": 1066.29,
   "q3": 1159.77,
   "iqr": 93.48,
   "min": 897.81,
   "max": 1221.8,
   "sd": 76.42
  },
  "cls": {
   "n": 30,
   "median": 2481.0,
   "mean": 2481.0,
   "q1": 2481.0,
   "q3": 2481.0,
   "iqr": 0.0,
   "min": 2481,
   "max": 2481,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 294.5,
   "mean": 290.47,
   "q1": 270.25,
   "q3": 316.25,
   "iqr": 46.0,
   "min": 211,
   "max": 384,
   "sd": 39.46
  },
  "gc_ms": {
   "n": 30,
   "median": 28.0,
   "mean": 28.83,
   "q1": 28.0,
   "q3": 30.5,
   "iqr": 2.5,
   "min": 24,
   "max": 33,
   "sd": 2.41
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 799.42,
   "mean": 781.76,
   "q1": 781.31,
   "q3": 815.23,
   "iqr": 33.92,
   "min": 619.36,
   "max": 853.24,
   "sd": 58.11
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 1070.0,
   "mean": 1047.0,
   "q1": 1042.5,
   "q3": 1090.0,
   "iqr": 47.5,
   "min": 830.0,
   "max": 1130.0,
   "sd": 71.64
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.47,
   "mean": 0.46,
   "q1": 0.45,
   "q3": 0.48,
   "iqr": 0.03,
   "min": 0.43,
   "max": 0.49,
   "sd": 0.02
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.01,
   "min": 0.0,
   "max": 0.03,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 215.0,
   "mean": 214.0,
   "q1": 208.0,
   "q3": 224.0,
   "iqr": 16.0,
   "min": 174,
   "max": 242,
   "sd": 16.2
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.98,
   "mean": 0.96,
   "q1": 0.91,
   "q3": 0.98,
   "iqr": 0.07,
   "min": 0.89,
   "max": 1.0,
   "sd": 0.04
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.73,
   "mean": 0.71,
   "q1": 0.69,
   "q3": 0.74,
   "iqr": 0.05,
   "min": 0.66,
   "max": 0.74,
   "sd": 0.03
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
   "median": 5401.25,
   "mean": 5379.91,
   "q1": 5290.66,
   "q3": 5501.79,
   "iqr": 211.13,
   "min": 4644.0,
   "max": 5826.95,
   "sd": 217.53
  },
  "cls": {
   "n": 30,
   "median": 3331.0,
   "mean": 3331.0,
   "q1": 3331.0,
   "q3": 3331.0,
   "iqr": 0.0,
   "min": 3331,
   "max": 3331,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 1427.5,
   "mean": 1463.83,
   "q1": 1405.25,
   "q3": 1528.75,
   "iqr": 123.5,
   "min": 1156,
   "max": 1683,
   "sd": 118.11
  },
  "gc_ms": {
   "n": 30,
   "median": 252.5,
   "mean": 254.47,
   "q1": 227.25,
   "q3": 271.0,
   "iqr": 43.75,
   "min": 203,
   "max": 362,
   "sd": 37.05
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 1137.72,
   "mean": 1110.97,
   "q1": 1106.35,
   "q3": 1156.14,
   "iqr": 49.79,
   "min": 892.6,
   "max": 1180.79,
   "sd": 76.14
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 1540.0,
   "mean": 1507.33,
   "q1": 1502.5,
   "q3": 1560.0,
   "iqr": 57.5,
   "min": 1230.0,
   "max": 1600.0,
   "sd": 93.44
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.12,
   "mean": 0.11,
   "q1": 0.11,
   "q3": 0.12,
   "iqr": 0.01,
   "min": 0.09,
   "max": 0.12,
   "sd": 0.01
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.01,
   "sd": 0.0
  },
  "jiffies_total": {
   "n": 30,
   "median": 1051.5,
   "mean": 1042.17,
   "q1": 1020.0,
   "q3": 1065.75,
   "iqr": 45.75,
   "min": 898,
   "max": 1127,
   "sd": 43.62
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.29,
   "mean": 0.28,
   "q1": 0.28,
   "q3": 0.29,
   "iqr": 0.01,
   "min": 0.24,
   "max": 0.29,
   "sd": 0.02
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.21,
   "mean": 0.21,
   "q1": 0.21,
   "q3": 0.21,
   "iqr": 0.01,
   "min": 0.17,
   "max": 0.22,
   "sd": 0.01
  },
  "from": [
   "w_in"
  ],
  "to": [
   "w_out"
  ],
  "start_to_w_in_ms": {
   "n": 30,
   "median": 3.0,
   "mean": 2.97,
   "q1": 3.0,
   "q3": 3.0,
   "iqr": 0.0,
   "min": 2.0,
   "max": 5.0,
   "sd": 0.76
  },
  "w_out_to_end_ms": {
   "n": 30,
   "median": 39.43,
   "mean": 34.54,
   "q1": 23.8,
   "q3": 41.54,
   "iqr": 17.75,
   "min": 19.92,
   "max": 42.79,
   "sd": 9.0
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 30,
   "median": 0.99,
   "mean": 0.99,
   "q1": 0.99,
   "q3": 1.0,
   "iqr": 0.0,
   "min": 0.99,
   "max": 1.0,
   "sd": 0.0
  }
 },
 "V1/inv2": {
  "wall_ms": {
   "n": 30,
   "median": 84.52,
   "mean": 84.77,
   "q1": 51.93,
   "q3": 114.13,
   "iqr": 62.2,
   "min": 45.71,
   "max": 144.13,
   "sd": 31.32
  },
  "cls": {
   "n": 30,
   "median": 2.0,
   "mean": 2.0,
   "q1": 2.0,
   "q3": 2.0,
   "iqr": 0.0,
   "min": 2,
   "max": 2,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 17.0,
   "mean": 19.67,
   "q1": 8.25,
   "q3": 27.0,
   "iqr": 18.75,
   "min": 5,
   "max": 43,
   "sd": 12.49
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
   "median": 18.65,
   "mean": 18.09,
   "q1": 12.98,
   "q3": 22.91,
   "iqr": 9.93,
   "min": 10.9,
   "max": 24.14,
   "sd": 4.71
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 30.0,
   "mean": 27.67,
   "q1": 20.0,
   "q3": 30.0,
   "iqr": 10.0,
   "min": 10.0,
   "max": 40.0,
   "sd": 8.17
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.11,
   "mean": 0.11,
   "q1": 0.09,
   "q3": 0.13,
   "iqr": 0.04,
   "min": 0.04,
   "max": 0.2,
   "sd": 0.04
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.06,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 16.0,
   "mean": 15.6,
   "q1": 10.0,
   "q3": 21.0,
   "iqr": 11.0,
   "min": 8,
   "max": 26,
   "sd": 5.68
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.35,
   "mean": 0.34,
   "q1": 0.28,
   "q3": 0.39,
   "iqr": 0.11,
   "min": 0.19,
   "max": 0.47,
   "sd": 0.07
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.22,
   "mean": 0.22,
   "q1": 0.2,
   "q3": 0.25,
   "iqr": 0.04,
   "min": 0.17,
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
   "median": 304.0,
   "mean": 414.53,
   "q1": 286.0,
   "q3": 630.75,
   "iqr": 344.75,
   "min": 227.0,
   "max": 660.0,
   "sd": 171.67
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
   "median": 135.5,
   "mean": 208.6,
   "q1": 126.0,
   "q3": 327.75,
   "iqr": 201.75,
   "min": 80.0,
   "max": 391.0,
   "sd": 114.62
  }
 },
 "V2/init": {
  "wall_ms": {
   "n": 30,
   "median": 2546.03,
   "mean": 2577.11,
   "q1": 2475.46,
   "q3": 2731.94,
   "iqr": 256.48,
   "min": 2231.7,
   "max": 2886.55,
   "sd": 180.94
  },
  "cls": {
   "n": 30,
   "median": 5811.0,
   "mean": 5811.0,
   "q1": 5811.0,
   "q3": 5811.0,
   "iqr": 0.0,
   "min": 5811,
   "max": 5811,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 690.0,
   "mean": 670.8,
   "q1": 659.5,
   "q3": 715.75,
   "iqr": 56.25,
   "min": 471,
   "max": 798,
   "sd": 78.13
  },
  "gc_ms": {
   "n": 30,
   "median": 123.0,
   "mean": 123.5,
   "q1": 113.75,
   "q3": 134.0,
   "iqr": 20.25,
   "min": 103,
   "max": 144,
   "sd": 12.05
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 1839.6,
   "mean": 1794.86,
   "q1": 1783.31,
   "q3": 1866.29,
   "iqr": 82.98,
   "min": 1419.07,
   "max": 1942.29,
   "sd": 144.69
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 2490.0,
   "mean": 2443.0,
   "q1": 2422.5,
   "q3": 2537.5,
   "iqr": 115.0,
   "min": 1970.0,
   "max": 2650.0,
   "sd": 180.98
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.47,
   "mean": 0.46,
   "q1": 0.44,
   "q3": 0.48,
   "iqr": 0.03,
   "min": 0.43,
   "max": 0.48,
   "sd": 0.02
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.07,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 491.5,
   "mean": 504.27,
   "q1": 479.25,
   "q3": 536.0,
   "iqr": 56.75,
   "min": 437,
   "max": 575,
   "sd": 39.22
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.97,
   "mean": 0.95,
   "q1": 0.9,
   "q3": 0.98,
   "iqr": 0.08,
   "min": 0.88,
   "max": 0.99,
   "sd": 0.04
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.72,
   "mean": 0.7,
   "q1": 0.67,
   "q3": 0.72,
   "iqr": 0.06,
   "min": 0.63,
   "max": 0.73,
   "sd": 0.03
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
   "median": 294.44,
   "mean": 305.06,
   "q1": 279.66,
   "q3": 345.03,
   "iqr": 65.37,
   "min": 181.6,
   "max": 393.21,
   "sd": 50.41
  },
  "cls": {
   "n": 30,
   "median": 37.0,
   "mean": 35.83,
   "q1": 37.0,
   "q3": 37.0,
   "iqr": 0.0,
   "min": 32,
   "max": 37,
   "sd": 2.15
  },
  "jit_ms": {
   "n": 30,
   "median": 48.5,
   "mean": 48.63,
   "q1": 35.0,
   "q3": 59.75,
   "iqr": 24.75,
   "min": 14,
   "max": 100,
   "sd": 20.64
  },
  "gc_ms": {
   "n": 30,
   "median": 104.0,
   "mean": 100.37,
   "q1": 99.75,
   "q3": 114.25,
   "iqr": 14.5,
   "min": 0,
   "max": 135,
   "sd": 29.09
  },
  "thread_cpu_ms": {
   "n": 30,
   "median": 40.7,
   "mean": 41.08,
   "q1": 36.44,
   "q3": 44.84,
   "iqr": 8.4,
   "min": 34.22,
   "max": 51.0,
   "sd": 4.81
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 90.0,
   "mean": 88.33,
   "q1": 80.0,
   "q3": 90.0,
   "iqr": 10.0,
   "min": 50.0,
   "max": 110.0,
   "sd": 14.16
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.11,
   "mean": 0.12,
   "q1": 0.1,
   "q3": 0.13,
   "iqr": 0.02,
   "min": 0.06,
   "max": 0.16,
   "sd": 0.02
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.02,
   "iqr": 0.02,
   "min": 0.0,
   "max": 0.05,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 30,
   "median": 58.0,
   "mean": 59.0,
   "q1": 54.0,
   "q3": 65.75,
   "iqr": 11.75,
   "min": 32,
   "max": 76,
   "sd": 10.33
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.3,
   "mean": 0.29,
   "q1": 0.28,
   "q3": 0.31,
   "iqr": 0.03,
   "min": 0.23,
   "max": 0.34,
   "sd": 0.03
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.13,
   "mean": 0.14,
   "q1": 0.13,
   "q3": 0.14,
   "iqr": 0.01,
   "min": 0.11,
   "max": 0.21,
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
   "mean": 2.3,
   "q1": 2.0,
   "q3": 3.0,
   "iqr": 1.0,
   "min": 1.0,
   "max": 3.0,
   "sd": 0.53
  },
  "w_out_to_end_ms": {
   "n": 30,
   "median": 42.62,
   "mean": 54.23,
   "q1": 41.59,
   "q3": 57.81,
   "iqr": 16.22,
   "min": 23.27,
   "max": 181.44,
   "sd": 33.31
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 30,
   "median": 0.86,
   "mean": 0.84,
   "q1": 0.85,
   "q3": 0.88,
   "iqr": 0.03,
   "min": 0.5,
   "max": 0.93,
   "sd": 0.09
  }
 },
 "V2/inv2": {
  "wall_ms": {
   "n": 30,
   "median": 81.12,
   "mean": 90.44,
   "q1": 62.17,
   "q3": 113.22,
   "iqr": 51.06,
   "min": 48.24,
   "max": 144.74,
   "sd": 31.66
  },
  "cls": {
   "n": 30,
   "median": 2.0,
   "mean": 2.0,
   "q1": 2.0,
   "q3": 2.0,
   "iqr": 0.0,
   "min": 2,
   "max": 2,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 30,
   "median": 25.0,
   "mean": 197.8,
   "q1": 10.75,
   "q3": 32.0,
   "iqr": 21.25,
   "min": 6,
   "max": 5238,
   "sd": 952.06
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
   "median": 18.07,
   "mean": 18.36,
   "q1": 14.07,
   "q3": 22.89,
   "iqr": 8.82,
   "min": 12.24,
   "max": 25.44,
   "sd": 4.44
  },
  "process_cpu_ms": {
   "n": 30,
   "median": 30.0,
   "mean": 31.33,
   "q1": 20.0,
   "q3": 40.0,
   "iqr": 20.0,
   "min": 20.0,
   "max": 50.0,
   "sd": 9.73
  },
  "busy_frac_procstat": {
   "n": 30,
   "median": 0.08,
   "mean": 0.09,
   "q1": 0.06,
   "q3": 0.11,
   "iqr": 0.05,
   "min": 0.0,
   "max": 0.25,
   "sd": 0.06
  },
  "steal_frac_procstat": {
   "n": 30,
   "median": 0.0,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.11,
   "sd": 0.02
  },
  "jiffies_total": {
   "n": 30,
   "median": 14.5,
   "mean": 16.57,
   "q1": 12.0,
   "q3": 21.5,
   "iqr": 9.5,
   "min": 8,
   "max": 28,
   "sd": 6.1
  },
  "process_cpu_per_wall": {
   "n": 30,
   "median": 0.36,
   "mean": 0.36,
   "q1": 0.29,
   "q3": 0.39,
   "iqr": 0.1,
   "min": 0.22,
   "max": 0.6,
   "sd": 0.09
  },
  "thread_cpu_per_wall": {
   "n": 30,
   "median": 0.21,
   "mean": 0.21,
   "q1": 0.19,
   "q3": 0.24,
   "iqr": 0.05,
   "min": 0.16,
   "max": 0.27,
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
   "median": 324.0,
   "mean": 431.6,
   "q1": 296.75,
   "q3": 635.0,
   "iqr": 338.25,
   "min": 283.0,
   "max": 676.0,
   "sd": 166.21
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
   "median": 142.0,
   "mean": 212.37,
   "q1": 127.0,
   "q3": 332.5,
   "iqr": 205.5,
   "min": 91.0,
   "max": 410.0,
   "sd": 110.54
  }
 }
}
```

## 6. Intervalos da 1ª chamada (medianas, ms) — ver `intervals.csv`

### V1 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| client_build_in -> client_build_out | 30 | 2759.7 | 1524 | 740 | 575.5 |
| sdk_before_tx -> sdk_after_tx | 30 | 1255.7 | 831 | 476 | 246.2 |
| sdk_before_exec -> sdk_before_tx | 30 | 420.4 | 392 | 26 | 107.1 |
| ctor_repo_orders -> sdk_before_exec | 30 | 325.3 | 282 | 104 | 76.8 |
| ctor_mapper -> h_mapped | 30 | 201.0 | 110 | 28 | 43.4 |
| h_out -> w_out | 30 | 122.1 | 45 | 43 | 25.8 |
| sdk_after_tx -> sdk_after_exec | 30 | 100.5 | 72 | 16 | 22.9 |
| w_in -> ctor_function | 30 | 47.4 | 36 | 1 | 15.9 |
| svc_calc_done -> client_build_in | 30 | 31.0 | 29 | 2 | 8.5 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 30 | 25.3 | 2 | 1 | 2.8 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 11 | 20.5 | 0 | 1 | 2.3 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 19 | 18.8 | 0 | 0 | 2.3 |
| client_build_out -> ctor_repo_orders | 30 | 15.7 | 0 | 0 | 0.4 |
| h_mapped -> ctor_service | 30 | 14.8 | 1 | 0 | 0.6 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 11 | 11.9 | 0 | 1 | 1.9 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 30 | 2.2 | 0 | 1 | 2.0 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 19 | 2.0 | 0 | 1 | 2.0 |
| svc_in -> svc_calc_done | 30 | 1.3 | 5 | 0 | 1.4 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 30 | 0.7 | 0 | 0 | 0.6 |
| ctor_repo_stock -> sdk_before_exec#2 | 30 | 0.7 | 0 | 0 | 0.7 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 19 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 11 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_exec -> svc_order_put_done | 30 | 0.6 | 2 | 0 | 0.5 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 11 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 19 | 0.5 | 0 | 0 | 0.5 |
| svc_order_put_done -> ctor_repo_stock | 30 | 0.3 | 0 | 0 | 0.2 |
| ctor_function -> h_in | 30 | 0.2 | 0 | 0 | 0.1 |
| ctor_service -> svc_in | 30 | 0.2 | 0 | 0 | 0.1 |
| h_in -> ctor_mapper | 30 | 0.1 | 0 | 0 | 0.2 |
| sdk_after_exec#2 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#3 -> svc_stock_puts_done | 8 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#4 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.1 |
| svc_stock_puts_done -> h_out | 30 | 0.1 | 0 | 0 | 0.1 |

### V2 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| h_out -> w_out | 30 | 153.3 | 20 | 21 | 15.0 |
| sdk_before_tx -> sdk_after_tx | 30 | 23.9 | 0 | 1 | 2.4 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 19 | 22.2 | 0 | 0 | 2.2 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 30 | 21.7 | 0 | 1 | 2.2 |
| w_in -> h_in | 30 | 21.7 | 16 | 1 | 7.6 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 11 | 18.2 | 0 | 1 | 2.0 |
| sdk_before_exec -> sdk_before_tx | 30 | 3.1 | 1 | 2 | 2.5 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 19 | 1.9 | 0 | 2 | 1.9 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 30 | 1.9 | 0 | 2 | 1.9 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 11 | 1.9 | 0 | 1 | 1.9 |
| h_in -> h_mapped | 30 | 1.1 | 0 | 0 | 0.8 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 30 | 0.6 | 0 | 0 | 0.6 |
| svc_calc_done -> sdk_before_exec | 30 | 0.6 | 0 | 0 | 0.7 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 19 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 11 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_tx -> sdk_after_exec | 30 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 19 | 0.5 | 0 | 0 | 0.5 |
| svc_order_put_done -> sdk_before_exec#2 | 30 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 11 | 0.5 | 0 | 0 | 0.5 |
| svc_in -> svc_calc_done | 30 | 0.2 | 0 | 0 | 0.2 |
| h_mapped -> svc_in | 30 | 0.2 | 0 | 0 | 0.1 |
| sdk_after_exec#3 -> svc_stock_puts_done | 8 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#4 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.2 |
| sdk_after_exec#2 -> svc_stock_puts_done | 11 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec -> svc_order_put_done | 30 | 0.1 | 0 | 0 | 0.1 |
| svc_stock_puts_done -> h_out | 30 | 0.1 | 0 | 0 | 0.0 |

## 7. JVM

- JAVA_TOOL_OPTIONS: {'V2': [''], 'V1': ['']}
- args: {'V2': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so'], 'V1': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so']}
- /tmp na 1ª chamada: {'V1': ['hsperfdata_sbx_user1051'], 'V2': ['hsperfdata_sbx_user1051']}
