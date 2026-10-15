# Relatório preliminar automático — exp-lazy (EXPLORATÓRIO, fora do desenho oficial)

RUN_ID `smoke-20260929T221245Z`. Gerado pelo driver na EC2. Apenas descritivo. Nenhum intervalo aqui é confirmatório. Fonte de cada número: `samples_final.csv`, `invocations.csv`, `points.csv`, `intervals.csv`, `phases.csv`, `summary.json`; L1 oficial: `l1_duration_postinit.csv`.

## 1. Amostras

- Frias válidas: {'V0': 3, 'V1': 3, 'V2': 3}; tentativas não frias/erro: {'V0': 0, 'V1': 0, 'V2': 0}
- Versões de runtime (INIT_START): {'V0': ['java:21.v68'], 'V1': ['java:21.v68'], 'V2': ['java:21.v68']}
- CodeSha256: {'V0': ['qqGaGUSyL1rtWwcwOeIMNhFYfsW+HvIh8QiUTPe+WME='], 'V1': ['RTtmKw35s7nPa1IzWSFMtzk8lznzf9Dy72LqBZdfSn4='], 'V2': ['RTtmKw35s7nPa1IzWSFMtzk8lznzf9Dy72LqBZdfSn4=']}
- Handler: {'V0': ['io.quarkus.funqy.lambda.FunqyStreamHandler::handleRequest'], 'V1': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest'], 'V2': ['com.tcc.orderprocessor.exp.LazyProbeHandler::handleRequest']}

## 2. Por variante (ms; mediana [Q1–Q3] min–max, n)

| Variante | Init | Duration | Init + Duration | Duration 2ª chamada (quente) | Gap fim-init→START |
|---|---|---|---|---|---|
| V0 | 1364.1 [1348.8–1503.7] 1333.6–1643.4, n=3 | 5366.8 [5361.4–5378.3] 5356.0–5389.9, n=3 | 6723.5 [6721.8–6866.8] 6720.1–7010.1, n=3 | 95.9 [64.5–97.4] 33.1–98.8, n=3 | 3.9 [3.8–4.2] 3.6–4.4, n=3 |
| V1 | 1416.6 [1385.0–1597.0] 1353.3–1777.3, n=3 | 5372.8 [5272.1–5575.1] 5171.5–5777.4, n=3 | 6789.3 [6657.1–7172.1] 6524.9–7554.8, n=3 | 115.3 [86.3–126.1] 57.2–136.8, n=3 | 3.6 [3.5–3.6] 3.4–3.6, n=3 |
| V2 | 2901.5 [2866.9–3284.2] 2832.3–3666.9, n=3 | 345.7 [335.1–380.9] 324.4–416.2, n=3 | 3247.2 [3202.0–3665.1] 3156.8–4083.1, n=3 | 100.8 [82.3–110.6] 63.9–120.3, n=3 | 3.7 [3.6–3.9] 3.5–4.1, n=3 |
| L1 oficial QJ | 1382.6 [1366.5–1406.4] 1314.9–1470.1, n=10 | 5620.4 [5468.8–5729.8] 5315.1–5842.5, n=10 | 6999.7 [6896.7–7141.4] 6637.5–7254.3, n=10 | — | — |

## 3. Controle (V0 × L1 oficial)

```
{
 "init_ms": {
  "v0_median": 1364.1,
  "l1_median": 1382.6,
  "diff_pct": -1.3,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -67.5,
   275.3
  ]
 },
 "duration_ms": {
  "v0_median": 5366.8,
  "l1_median": 5620.4,
  "diff_pct": -4.5,
  "v0_median_inside_l1_range": true,
  "boot95_v0_minus_l1": [
   -381.3,
   -65.6
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
   "median_a": 1416.6,
   "median_b": 1364.1,
   "diff": 52.5,
   "diff_pct": 3.8,
   "boot95": [
    -290.0,
    443.8
   ]
  },
  "duration_ms": {
   "median_a": 5372.8,
   "median_b": 5366.8,
   "diff": 6.0,
   "diff_pct": 0.1,
   "boot95": [
    -218.4,
    421.4
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 6789.3,
   "median_b": 6723.5,
   "diff": 65.8,
   "diff_pct": 1.0,
   "boot95": [
    -485.2,
    834.6
   ]
  },
  "warm_duration_ms": {
   "median_a": 115.3,
   "median_b": 95.9,
   "diff": 19.4,
   "diff_pct": 20.3,
   "boot95": [
    -41.6,
    103.7
   ]
  }
 },
 "V2_vs_V1": {
  "init_ms": {
   "median_a": 2901.5,
   "median_b": 1416.6,
   "diff": 1484.9,
   "diff_pct": 104.8,
   "boot95": [
    1055.0,
    2313.6
   ]
  },
  "duration_ms": {
   "median_a": 345.7,
   "median_b": 5372.8,
   "diff": -5027.1,
   "diff_pct": -93.6,
   "boot95": [
    -5453.0,
    -4755.3
   ]
  },
  "init_plus_duration_ms": {
   "median_a": 3247.2,
   "median_b": 6789.3,
   "diff": -3542.2,
   "diff_pct": -52.2,
   "boot95": [
    -4398.0,
    -2441.8
   ]
  },
  "warm_duration_ms": {
   "median_a": 100.8,
   "median_b": 115.3,
   "diff": -14.5,
   "diff_pct": -12.6,
   "boot95": [
    -73.0,
    63.1
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
   "median": 1057.76,
   "mean": 1058.98,
   "q1": 1048.9,
   "q3": 1068.46,
   "iqr": 19.56,
   "min": 1040.03,
   "max": 1079.15,
   "sd": 19.59
  },
  "cls": {
   "n": 3,
   "median": 2481,
   "mean": 2481.0,
   "q1": 2481.0,
   "q3": 2481.0,
   "iqr": 0.0,
   "min": 2481,
   "max": 2481,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 283,
   "mean": 286.33,
   "q1": 267.0,
   "q3": 304.0,
   "iqr": 37.0,
   "min": 251,
   "max": 325,
   "sd": 37.11
  },
  "gc_ms": {
   "n": 3,
   "median": 27,
   "mean": 27.33,
   "q1": 27.0,
   "q3": 27.5,
   "iqr": 0.5,
   "min": 27,
   "max": 28,
   "sd": 0.58
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 763.25,
   "mean": 751.32,
   "q1": 728.44,
   "q3": 780.17,
   "iqr": 51.73,
   "min": 693.63,
   "max": 797.08,
   "sd": 52.75
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 1020.0,
   "mean": 1010.0,
   "q1": 985.0,
   "q3": 1040.0,
   "iqr": 55.0,
   "min": 950.0,
   "max": 1060.0,
   "sd": 55.68
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.48,
   "mean": 0.47,
   "q1": 0.46,
   "q3": 0.48,
   "iqr": 0.02,
   "min": 0.44,
   "max": 0.48,
   "sd": 0.02
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.0,
   "mean": 0.0,
   "q1": 0.0,
   "q3": 0.0,
   "iqr": 0.0,
   "min": 0.0,
   "max": 0.01,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 3,
   "median": 208,
   "mean": 206.33,
   "q1": 204.0,
   "q3": 209.5,
   "iqr": 5.5,
   "min": 200,
   "max": 211,
   "sd": 5.69
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.98,
   "mean": 0.95,
   "q1": 0.94,
   "q3": 0.98,
   "iqr": 0.04,
   "min": 0.9,
   "max": 0.98,
   "sd": 0.05
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.73,
   "mean": 0.71,
   "q1": 0.69,
   "q3": 0.74,
   "iqr": 0.04,
   "min": 0.66,
   "max": 0.74,
   "sd": 0.05
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
   "median": 5330.13,
   "mean": 5393.61,
   "q1": 5229.25,
   "q3": 5526.23,
   "iqr": 296.98,
   "min": 5128.36,
   "max": 5722.33,
   "sd": 302.03
  },
  "cls": {
   "n": 3,
   "median": 3331,
   "mean": 3331.0,
   "q1": 3331.0,
   "q3": 3331.0,
   "iqr": 0.0,
   "min": 3331,
   "max": 3331,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 1406,
   "mean": 1425.33,
   "q1": 1347.0,
   "q3": 1494.0,
   "iqr": 147.0,
   "min": 1288,
   "max": 1582,
   "sd": 147.95
  },
  "gc_ms": {
   "n": 3,
   "median": 304,
   "mean": 302.67,
   "q1": 296.5,
   "q3": 309.5,
   "iqr": 13.0,
   "min": 289,
   "max": 315,
   "sd": 13.05
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 1100.8,
   "mean": 1064.98,
   "q1": 1032.59,
   "q3": 1115.29,
   "iqr": 82.7,
   "min": 964.37,
   "max": 1129.77,
   "sd": 88.33
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 1490.0,
   "mean": 1460.0,
   "q1": 1415.0,
   "q3": 1520.0,
   "iqr": 105.0,
   "min": 1340.0,
   "max": 1550.0,
   "sd": 108.17
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.12,
   "mean": 0.11,
   "q1": 0.1,
   "q3": 0.12,
   "iqr": 0.01,
   "min": 0.09,
   "max": 0.12,
   "sd": 0.02
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
   "median": 1033,
   "mean": 1043.0,
   "q1": 1011.0,
   "q3": 1070.0,
   "iqr": 59.0,
   "min": 989,
   "max": 1107,
   "sd": 59.63
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.29,
   "mean": 0.27,
   "q1": 0.26,
   "q3": 0.29,
   "iqr": 0.03,
   "min": 0.23,
   "max": 0.29,
   "sd": 0.03
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.21,
   "mean": 0.2,
   "q1": 0.19,
   "q3": 0.21,
   "iqr": 0.02,
   "min": 0.17,
   "max": 0.21,
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
   "median": 3.0,
   "mean": 7.0,
   "q1": 3.0,
   "q3": 9.0,
   "iqr": 6.0,
   "min": 3.0,
   "max": 15.0,
   "sd": 6.93
  },
  "w_out_to_end_ms": {
   "n": 3,
   "median": 39.77,
   "mean": 39.9,
   "q1": 39.59,
   "q3": 40.15,
   "iqr": 0.56,
   "min": 39.41,
   "max": 40.53,
   "sd": 0.57
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
   "median": 113.39,
   "mean": 97.16,
   "q1": 84.38,
   "q3": 118.06,
   "iqr": 33.68,
   "min": 55.37,
   "max": 122.72,
   "sd": 36.49
  },
  "cls": {
   "n": 3,
   "median": 2,
   "mean": 2.0,
   "q1": 2.0,
   "q3": 2.0,
   "iqr": 0.0,
   "min": 2,
   "max": 2,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 25,
   "mean": 32.33,
   "q1": 15.0,
   "q3": 46.0,
   "iqr": 31.0,
   "min": 5,
   "max": 67,
   "sd": 31.64
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
   "median": 20.51,
   "mean": 18.72,
   "q1": 16.7,
   "q3": 21.63,
   "iqr": 4.94,
   "min": 12.89,
   "max": 22.76,
   "sd": 5.17
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 40.0,
   "mean": 33.33,
   "q1": 30.0,
   "q3": 40.0,
   "iqr": 10.0,
   "min": 20.0,
   "max": 40.0,
   "sd": 11.55
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.1,
   "mean": 0.08,
   "q1": 0.07,
   "q3": 0.1,
   "iqr": 0.03,
   "min": 0.05,
   "max": 0.1,
   "sd": 0.03
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
   "median": 21,
   "mean": 17.67,
   "q1": 15.5,
   "q3": 21.5,
   "iqr": 6.0,
   "min": 10,
   "max": 22,
   "sd": 6.66
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.35,
   "mean": 0.35,
   "q1": 0.34,
   "q3": 0.36,
   "iqr": 0.02,
   "min": 0.33,
   "max": 0.36,
   "sd": 0.02
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.2,
   "mean": 0.2,
   "q1": 0.18,
   "q3": 0.22,
   "iqr": 0.03,
   "min": 0.17,
   "max": 0.23,
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
   "n": 3,
   "median": 295.0,
   "mean": 401.67,
   "q1": 288.0,
   "q3": 462.0,
   "iqr": 174.0,
   "min": 281.0,
   "max": 629.0,
   "sd": 197.0
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
   "median": 136.0,
   "mean": 195.0,
   "q1": 127.0,
   "q3": 233.5,
   "iqr": 106.5,
   "min": 118.0,
   "max": 331.0,
   "sd": 118.12
  }
 },
 "V2/init": {
  "wall_ms": {
   "n": 3,
   "median": 2560.76,
   "mean": 2653.2,
   "q1": 2524.67,
   "q3": 2735.51,
   "iqr": 210.84,
   "min": 2488.58,
   "max": 2910.26,
   "sd": 225.52
  },
  "cls": {
   "n": 3,
   "median": 5811,
   "mean": 5811.0,
   "q1": 5811.0,
   "q3": 5811.0,
   "iqr": 0.0,
   "min": 5811,
   "max": 5811,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 715,
   "mean": 726.67,
   "q1": 710.0,
   "q3": 737.5,
   "iqr": 27.5,
   "min": 705,
   "max": 760,
   "sd": 29.3
  },
  "gc_ms": {
   "n": 3,
   "median": 121,
   "mean": 125.0,
   "q1": 121.0,
   "q3": 127.0,
   "iqr": 6.0,
   "min": 121,
   "max": 133,
   "sd": 6.93
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 1851.39,
   "mean": 1866.21,
   "q1": 1822.39,
   "q3": 1902.63,
   "iqr": 80.24,
   "min": 1793.38,
   "max": 1953.87,
   "sd": 81.26
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 2500.0,
   "mean": 2526.67,
   "q1": 2470.0,
   "q3": 2570.0,
   "iqr": 100.0,
   "min": 2440.0,
   "max": 2640.0,
   "sd": 102.63
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.47,
   "mean": 0.46,
   "q1": 0.46,
   "q3": 0.47,
   "iqr": 0.02,
   "min": 0.44,
   "max": 0.48,
   "sd": 0.02
  },
  "steal_frac_procstat": {
   "n": 3,
   "median": 0.01,
   "mean": 0.01,
   "q1": 0.0,
   "q3": 0.01,
   "iqr": 0.01,
   "min": 0.0,
   "max": 0.01,
   "sd": 0.01
  },
  "jiffies_total": {
   "n": 3,
   "median": 494,
   "mean": 516.0,
   "q1": 488.0,
   "q3": 533.0,
   "iqr": 45.0,
   "min": 482,
   "max": 572,
   "sd": 48.87
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.98,
   "mean": 0.95,
   "q1": 0.94,
   "q3": 0.98,
   "iqr": 0.04,
   "min": 0.91,
   "max": 0.98,
   "sd": 0.04
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.72,
   "mean": 0.7,
   "q1": 0.7,
   "q3": 0.72,
   "iqr": 0.03,
   "min": 0.67,
   "max": 0.72,
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
   "n": 3,
   "median": 281.57,
   "mean": 305.69,
   "q1": 271.82,
   "q3": 327.49,
   "iqr": 55.67,
   "min": 262.08,
   "max": 373.42,
   "sd": 59.46
  },
  "cls": {
   "n": 3,
   "median": 37,
   "mean": 35.33,
   "q1": 34.5,
   "q3": 37.0,
   "iqr": 2.5,
   "min": 32,
   "max": 37,
   "sd": 2.89
  },
  "jit_ms": {
   "n": 3,
   "median": 41,
   "mean": 40.33,
   "q1": 27.0,
   "q3": 54.0,
   "iqr": 27.0,
   "min": 13,
   "max": 67,
   "sd": 27.01
  },
  "gc_ms": {
   "n": 3,
   "median": 99,
   "mean": 103.67,
   "q1": 99.0,
   "q3": 106.0,
   "iqr": 7.0,
   "min": 99,
   "max": 113,
   "sd": 8.08
  },
  "thread_cpu_ms": {
   "n": 3,
   "median": 40.08,
   "mean": 41.95,
   "q1": 38.58,
   "q3": 44.38,
   "iqr": 5.81,
   "min": 37.07,
   "max": 48.69,
   "sd": 6.03
  },
  "process_cpu_ms": {
   "n": 3,
   "median": 90.0,
   "mean": 93.33,
   "q1": 85.0,
   "q3": 100.0,
   "iqr": 15.0,
   "min": 80.0,
   "max": 110.0,
   "sd": 15.28
  },
  "busy_frac_procstat": {
   "n": 3,
   "median": 0.11,
   "mean": 0.11,
   "q1": 0.1,
   "q3": 0.12,
   "iqr": 0.01,
   "min": 0.1,
   "max": 0.12,
   "sd": 0.01
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
   "median": 52,
   "mean": 58.0,
   "q1": 51.0,
   "q3": 62.0,
   "iqr": 11.0,
   "min": 50,
   "max": 72,
   "sd": 12.17
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.31,
   "mean": 0.31,
   "q1": 0.3,
   "q3": 0.31,
   "iqr": 0.01,
   "min": 0.29,
   "max": 0.32,
   "sd": 0.01
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.14,
   "mean": 0.14,
   "q1": 0.14,
   "q3": 0.14,
   "iqr": 0.01,
   "min": 0.13,
   "max": 0.14,
   "sd": 0.01
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
   "mean": 2.33,
   "q1": 2.0,
   "q3": 2.5,
   "iqr": 0.5,
   "min": 2.0,
   "max": 3.0,
   "sd": 0.58
  },
  "w_out_to_end_ms": {
   "n": 3,
   "median": 60.43,
   "mean": 54.43,
   "q1": 50.8,
   "q3": 61.06,
   "iqr": 10.26,
   "min": 41.18,
   "max": 61.69,
   "sd": 11.5
  },
  "w_in_to_w_out_share_of_duration": {
   "n": 3,
   "median": 0.81,
   "mean": 0.84,
   "q1": 0.81,
   "q3": 0.86,
   "iqr": 0.04,
   "min": 0.81,
   "max": 0.9,
   "sd": 0.05
  }
 },
 "V2/inv2": {
  "wall_ms": {
   "n": 3,
   "median": 86.53,
   "mean": 84.58,
   "q1": 67.6,
   "q3": 102.53,
   "iqr": 34.93,
   "min": 48.68,
   "max": 118.53,
   "sd": 34.97
  },
  "cls": {
   "n": 3,
   "median": 2,
   "mean": 2.0,
   "q1": 2.0,
   "q3": 2.0,
   "iqr": 0.0,
   "min": 2,
   "max": 2,
   "sd": 0.0
  },
  "jit_ms": {
   "n": 3,
   "median": 40,
   "mean": 34.0,
   "q1": 24.5,
   "q3": 46.5,
   "iqr": 22.0,
   "min": 9,
   "max": 53,
   "sd": 22.61
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
   "median": 17.94,
   "mean": 17.74,
   "q1": 15.14,
   "q3": 20.44,
   "iqr": 5.29,
   "min": 12.35,
   "max": 22.93,
   "sd": 5.3
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
   "median": 0.17,
   "mean": 0.16,
   "q1": 0.13,
   "q3": 0.19,
   "iqr": 0.07,
   "min": 0.09,
   "max": 0.22,
   "sd": 0.07
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
   "median": 18,
   "mean": 16.33,
   "q1": 13.5,
   "q3": 20.0,
   "iqr": 6.5,
   "min": 9,
   "max": 22,
   "sd": 6.66
  },
  "process_cpu_per_wall": {
   "n": 3,
   "median": 0.35,
   "mean": 0.34,
   "q1": 0.3,
   "q3": 0.38,
   "iqr": 0.08,
   "min": 0.25,
   "max": 0.41,
   "sd": 0.08
  },
  "thread_cpu_per_wall": {
   "n": 3,
   "median": 0.21,
   "mean": 0.22,
   "q1": 0.2,
   "q3": 0.23,
   "iqr": 0.03,
   "min": 0.19,
   "max": 0.25,
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
   "n": 3,
   "median": 306.0,
   "mean": 424.33,
   "q1": 304.5,
   "q3": 485.0,
   "iqr": 180.5,
   "min": 303.0,
   "max": 664.0,
   "sd": 207.56
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
   "median": 139.0,
   "mean": 203.33,
   "q1": 133.0,
   "q3": 241.5,
   "iqr": 108.5,
   "min": 127.0,
   "max": 344.0,
   "sd": 121.97
  }
 }
}
```

## 6. Intervalos da 1ª chamada (medianas, ms) — ver `intervals.csv`

### V1 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| client_build_in -> client_build_out | 3 | 2697.3 | 1520 | 715 | 547.8 |
| sdk_before_tx -> sdk_after_tx | 3 | 1278.0 | 835 | 425 | 240.0 |
| sdk_before_exec -> sdk_before_tx | 3 | 403.5 | 392 | 27 | 102.7 |
| ctor_repo_orders -> sdk_before_exec | 3 | 343.0 | 282 | 121 | 77.6 |
| ctor_mapper -> h_mapped | 3 | 201.5 | 110 | 43 | 41.5 |
| h_out -> w_out | 3 | 121.0 | 45 | 47 | 25.4 |
| sdk_after_tx -> sdk_after_exec | 3 | 87.0 | 72 | 2 | 21.9 |
| w_in -> ctor_function | 3 | 42.7 | 36 | 1 | 15.3 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 3 | 28.0 | 2 | 1 | 2.8 |
| svc_calc_done -> client_build_in | 3 | 24.4 | 29 | 1 | 8.3 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 1 | 20.5 | 0 | 2 | 2.4 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 3 | 19.9 | 0 | 0 | 2.4 |
| h_mapped -> ctor_service | 3 | 17.8 | 1 | 1 | 0.6 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 2 | 14.9 | 0 | 0 | 2.3 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 2 | 14.4 | 0 | 2 | 2.2 |
| sdk_after_exec -> svc_order_put_done | 3 | 13.1 | 2 | 0 | 0.8 |
| ctor_function -> h_in | 3 | 12.9 | 0 | 0 | 0.3 |
| client_build_out -> ctor_repo_orders | 3 | 12.5 | 0 | 0 | 0.4 |
| sdk_after_exec#4 -> svc_stock_puts_done | 1 | 12.3 | 0 | 0 | 0.2 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 2 | 6.6 | 0 | 1 | 0.8 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 2 | 4.0 | 0 | 0 | 0.7 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 3 | 2.2 | 0 | 0 | 0.7 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 1 | 1.6 | 0 | 1 | 1.7 |
| svc_in -> svc_calc_done | 3 | 1.3 | 5 | 0 | 1.5 |
| ctor_repo_stock -> sdk_before_exec#2 | 3 | 0.9 | 0 | 1 | 0.8 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 1 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 1 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> svc_stock_puts_done | 1 | 0.4 | 0 | 0 | 0.1 |
| svc_order_put_done -> ctor_repo_stock | 3 | 0.4 | 0 | 0 | 0.3 |
| ctor_service -> svc_in | 3 | 0.3 | 0 | 0 | 0.1 |
| h_in -> ctor_mapper | 3 | 0.3 | 0 | 0 | 0.2 |
| sdk_after_exec#2 -> svc_stock_puts_done | 1 | 0.2 | 0 | 0 | 0.1 |
| svc_stock_puts_done -> h_out | 3 | 0.1 | 0 | 0 | 0.1 |

### V2 inv1

| intervalo | n | mediana ms | classes | JIT ms | CPU thread ms |
|---|---|---|---|---|---|
| w_in -> h_in | 3 | 142.4 | 16 | 1 | 10.0 |
| h_out -> w_out | 3 | 73.5 | 20 | 16 | 14.6 |
| sdk_before_tx#3 -> sdk_after_tx#3 | 2 | 27.4 | 0 | 0 | 2.1 |
| sdk_before_tx#4 -> sdk_after_tx#4 | 1 | 23.0 | 0 | 1 | 2.4 |
| sdk_before_tx#2 -> sdk_after_tx#2 | 3 | 23.0 | 0 | 17 | 2.2 |
| sdk_before_exec -> sdk_before_tx | 3 | 18.8 | 1 | 1 | 2.8 |
| sdk_before_tx -> sdk_after_tx | 3 | 9.1 | 0 | 1 | 2.3 |
| sdk_before_exec#2 -> sdk_before_tx#2 | 3 | 1.8 | 0 | 2 | 1.8 |
| sdk_before_exec#3 -> sdk_before_tx#3 | 2 | 1.8 | 0 | 2 | 1.8 |
| sdk_before_exec#4 -> sdk_before_tx#4 | 1 | 1.7 | 0 | 0 | 1.7 |
| svc_calc_done -> sdk_before_exec | 3 | 1.3 | 0 | 2 | 0.9 |
| h_in -> h_mapped | 3 | 0.8 | 0 | 1 | 0.8 |
| sdk_after_tx#4 -> sdk_after_exec#4 | 1 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_tx#3 -> sdk_after_exec#3 | 2 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_tx#2 -> sdk_after_exec#2 | 3 | 0.6 | 0 | 0 | 0.5 |
| sdk_after_tx -> sdk_after_exec | 3 | 0.6 | 0 | 0 | 0.5 |
| svc_order_put_done -> sdk_before_exec#2 | 3 | 0.6 | 0 | 0 | 0.6 |
| sdk_after_exec#2 -> sdk_before_exec#3 | 2 | 0.5 | 0 | 0 | 0.5 |
| sdk_after_exec#3 -> sdk_before_exec#4 | 1 | 0.5 | 0 | 0 | 0.5 |
| svc_in -> svc_calc_done | 3 | 0.2 | 0 | 0 | 0.2 |
| h_mapped -> svc_in | 3 | 0.2 | 0 | 0 | 0.1 |
| sdk_after_exec -> svc_order_put_done | 3 | 0.2 | 0 | 0 | 0.1 |
| sdk_after_exec#4 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#2 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.1 |
| sdk_after_exec#3 -> svc_stock_puts_done | 1 | 0.1 | 0 | 0 | 0.1 |
| svc_stock_puts_done -> h_out | 3 | 0.0 | 0 | 0 | 0.0 |

## 7. JVM

- JAVA_TOOL_OPTIONS: {'V2': [''], 'V1': ['']}
- args: {'V2': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so'], 'V1': ['-XX:MaxHeapSize=445645k -javaagent:/var/runtime/lib/Log4jHotPatch.jar=log4jFixerVerbose=false -XX:+UseSerialGC -Xshare:on -XX:SharedArchiveFile=/var/lang/lib/server/runtime.jsa -XX:+TieredCompilation -XX:TieredStopAtLevel=1 --add-opens=java.base/java.io=ALL-UNNAMED -Dorg.crac.Core.Compat=com.amazonaws.services.lambda.crac -XX:+ErrorFileToStderr -Dcom.amazonaws.services.lambda.runtime.api.client.runtimeapi.NativeClient.JNI=/var/runtime/lib/jni/libaws-lambda-jni.linux-x86_64.so']}
- /tmp na 1ª chamada: {'V1': ['hsperfdata_sbx_user1051'], 'V2': ['hsperfdata_sbx_user1051']}
