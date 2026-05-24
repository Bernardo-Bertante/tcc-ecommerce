# Benchmark metrics — run `overnight-20260516-215109`

Aggregated from k6 end-of-test summaries, docker container-stats samples (5s cadence) and startup-readiness CSV. Latency values are milliseconds, memory in MiB, CPU in % of one host core (Docker convention).

## 1. Verdict matrix (5 repetitions per cell)

| Scenario | Version | PASS | THRESHOLD_FAIL | RUN_ERROR | Wallclock mean (s) |
|---|---|---:|---:|---:|---:|
| f1_low_load | quarkus-native | 5 | 0 | 0 | 604.8 |
| f1_low_load | quarkus-jvm | 5 | 0 | 0 | 604.4 |
| f1_low_load | springboot | 5 | 0 | 0 | 605.4 |
| f2_high_load | quarkus-native | 0 | 5 | 0 | 2,429.4 |
| f2_high_load | quarkus-jvm | 0 | 5 | 0 | 648.4 |
| f2_high_load | springboot | 0 | 5 | 0 | 2,079.8 |

## 2. Cold start (first health check 200 after container start)

| Version | startup_ms | readiness_wait_ms |
|---|---:|---:|
| quarkus-native | 48725760 | 20 |
| quarkus-jvm | 48725919 | 29 |
| springboot | 48726092 | 25 |

*Note: `startup_ms` in this run reflects total time since the container was created on a previous day; treat it as an upper bound only. `readiness_wait_ms` is the meaningful cold-start signal here (time from precheck start until /health returned 200).*

## 3. Scenario `f1_low_load` — k6 load-phase latency (mean ± stdev across 5 runs)

| Version | avg ms | p95 ms | p99 ms | max ms | fail rate | req/s | total reqs |
|---|---:|---:|---:|---:|---:|---:|---:|
| quarkus-native | 41.39 ± 17.99 | 376.20 ± 215.59 | 568.60 ± 197.05 | 815.44 | 0.0000 | 33.0 | 19,921 |
| quarkus-jvm | 85.03 ± 80.86 | 444.19 ± 272.91 | 835.67 ± 461.42 | 1,061.10 | 0.0000 | 33.0 | 19,921 |
| springboot | 77.57 ± 57.62 | 515.93 ± 251.86 | 857.84 ± 451.92 | 1,308.36 | 0.0000 | 32.9 | 19,921 |

### Scenario `f1_low_load` — resource usage (app container)

| Version | CPU avg % | CPU p95 % | CPU max % | Mem avg MiB | Mem max MiB |
|---|---:|---:|---:|---:|---:|
| quarkus-native | 5.8 | 8.6 | 10.8 | 137.9 | 159.1 |
| quarkus-jvm | 7.1 | 15.5 | 21.3 | 815.5 | 822.1 |
| springboot | 14.0 | 21.1 | 38.6 | 1,595.9 | 1,626.9 |

### Scenario `f1_low_load` — Postgres co-tenant

| Version (test running) | CPU avg % | CPU max % | Mem avg MiB | Mem max MiB |
|---|---:|---:|---:|---:|
| quarkus-native | 222.2 | 772.4 | 728.5 | 751.2 |
| quarkus-jvm | 194.5 | 547.0 | 591.6 | 608.9 |
| springboot | 342.5 | 1,016.8 | 700.2 | 833.0 |

## 4. Scenario `f2_high_load` — k6 load-phase latency (mean ± stdev across 5 runs)

| Version | avg ms | p95 ms | p99 ms | max ms | fail rate | req/s | total reqs |
|---|---:|---:|---:|---:|---:|---:|---:|
| quarkus-native | 17,238.06 ± 5,091.94 | 27,795.81 ± 8,074.38 | 29,246.00 ± 8,564.40 | 31,605.88 | 0.0000 | 93.2 | 224,872 |
| quarkus-jvm | 29,741.38 ± 175.80 | 30,000.45 ± 5.53 | 30,000.00 ± 0.00 | 30,007.28 | 0.3511 | 47.9 | 30,322 |
| springboot | 20,506.83 ± 6,117.92 | 38,560.95 ± 10,484.88 | 41,302.00 ± 11,777.39 | 43,712.70 | 0.0021 | 71.0 | 156,251 |

### Scenario `f2_high_load` — resource usage (app container)

| Version | CPU avg % | CPU p95 % | CPU max % | Mem avg MiB | Mem max MiB |
|---|---:|---:|---:|---:|---:|
| quarkus-native | 27.9 | 46.7 | 79.0 | 181.2 | 232.2 |
| quarkus-jvm | 5.4 | 16.1 | 39.5 | 886.9 | 1,024.7 |
| springboot | 40.3 | 71.0 | 113.8 | 1,482.4 | 2,095.1 |

### Scenario `f2_high_load` — Postgres co-tenant

| Version (test running) | CPU avg % | CPU max % | Mem avg MiB | Mem max MiB |
|---|---:|---:|---:|---:|
| quarkus-native | 1,536.4 | 1,970.9 | 660.7 | 755.5 |
| quarkus-jvm | 23.8 | 929.8 | 591.1 | 607.6 |
| springboot | 1,509.9 | 1,950.9 | 793.8 | 861.6 |

## 5. Per-repetition detail

| Scenario | Version | Run | Verdict | Wall s | avg ms | p95 ms | p99 ms | fail rate | req/s | app CPU avg % | app Mem max MiB |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| f1_low_load | quarkus-native | 1 | PASS | 605.0 | 18.33 | 74.84 | 270.30 | 0 | 33.0 | 6.4 | 166.5 |
| f2_high_load | quarkus-native | 1 | THRESHOLD_FAIL | 2,423.0 | 9,556.35 | 15,692.57 | 16,810.00 | 0 | 148.1 | 42.3 | 239.3 |
| f1_low_load | quarkus-jvm | 1 | PASS | 605.0 | 23.31 | 217.58 | 365.99 | 0 | 32.9 | 12.1 | 592.8 |
| f2_high_load | quarkus-jvm | 1 | THRESHOLD_FAIL | 647.0 | 29,486.65 | 30,002.85 | 30,000.00 | 0.1169 | 48.7 | 5.4 | 645.4 |
| f1_low_load | springboot | 1 | PASS | 605.0 | 29.18 | 228.78 | 413.26 | 0 | 33.0 | 14.1 | 1,978.4 |
| f2_high_load | springboot | 1 | THRESHOLD_FAIL | 2,424.0 | 12,446.87 | 23,748.63 | 25,530.00 | 0 | 105.3 | 57.8 | 2,086.9 |
| f1_low_load | quarkus-native | 2 | PASS | 605.0 | 28.41 | 182.17 | 447.94 | 0 | 33.0 | 5.6 | 156.1 |
| f2_high_load | quarkus-native | 2 | THRESHOLD_FAIL | 2,427.0 | 14,052.05 | 22,612.58 | 23,530.00 | 0 | 102.9 | 31.5 | 245.3 |
| f1_low_load | quarkus-jvm | 2 | PASS | 604.0 | 33.87 | 255.79 | 520.55 | 0 | 33.0 | 6.6 | 639.1 |
| f2_high_load | quarkus-jvm | 2 | THRESHOLD_FAIL | 647.0 | 29,600.91 | 29,989.40 | 30,000.00 | 0.0449 | 47.7 | 4.1 | 833.9 |
| f1_low_load | springboot | 2 | PASS | 605.0 | 42.66 | 393.46 | 582.95 | 0 | 33.0 | 13.7 | 1,679.4 |
| f2_high_load | springboot | 2 | THRESHOLD_FAIL | 2,428.0 | 16,418.71 | 31,659.33 | 33,320.00 | 0 | 81.1 | 44.8 | 2,095.1 |
| f1_low_load | quarkus-native | 3 | PASS | 604.0 | 38.05 | 434.47 | 580.06 | 0 | 33.0 | 6.1 | 171.7 |
| f2_high_load | quarkus-native | 3 | THRESHOLD_FAIL | 2,431.0 | 17,573.01 | 28,254.50 | 29,520.00 | 0 | 83.1 | 26.0 | 241.3 |
| f1_low_load | quarkus-jvm | 3 | PASS | 604.0 | 46.24 | 325.84 | 683.51 | 0 | 33.0 | 5.3 | 840.1 |
| f2_high_load | quarkus-jvm | 3 | THRESHOLD_FAIL | 649.0 | 29,842.36 | 30,003.48 | 30,000.00 | 0.5641 | 48.1 | 6.4 | 1,185.8 |
| f1_low_load | springboot | 3 | PASS | 605.0 | 53.07 | 414.08 | 710.94 | 0 | 32.9 | 14.4 | 1,872.9 |
| f2_high_load | springboot | 3 | THRESHOLD_FAIL | 2,430.0 | 19,898.84 | 38,167.21 | 40,460.00 | 0 | 67.8 | 37.8 | 2,096.1 |
| f1_low_load | quarkus-native | 4 | PASS | 605.0 | 53.02 | 544.76 | 711.35 | 0 | 33.0 | 5.6 | 144.7 |
| f2_high_load | quarkus-native | 4 | THRESHOLD_FAIL | 2,432.0 | 20,939.53 | 33,883.07 | 35,060.00 | 0 | 70.5 | 21.3 | 221.7 |
| f1_low_load | quarkus-jvm | 4 | PASS | 604.0 | 79.45 | 456.57 | 928.29 | 0 | 33.0 | 6.7 | 1,198.1 |
| f2_high_load | quarkus-jvm | 4 | THRESHOLD_FAIL | 648.0 | 29,797.84 | 30,003.23 | 30,000.00 | 0.2202 | 47.5 | 5.9 | 1,488.9 |
| f1_low_load | springboot | 4 | PASS | 605.0 | 73.89 | 573.50 | 872.06 | 0 | 32.9 | 13.7 | 1,463.3 |
| f2_high_load | springboot | 4 | THRESHOLD_FAIL | 2,433.0 | 23,439.51 | 45,250.36 | 47,360.00 | 0 | 57.9 | 32.0 | 2,104.3 |
| f1_low_load | quarkus-native | 5 | PASS | 605.0 | 69.16 | 644.75 | 833.36 | 0 | 33.0 | 5.5 | 156.4 |
| f2_high_load | quarkus-native | 5 | THRESHOLD_FAIL | 2,434.0 | 24,069.38 | 38,536.32 | 41,310.00 | 0 | 61.3 | 18.3 | 213.3 |
| f1_low_load | quarkus-jvm | 5 | PASS | 605.0 | 242.29 | 965.15 | 1,680.00 | 0 | 33.0 | 4.9 | 840.2 |
| f2_high_load | quarkus-jvm | 5 | THRESHOLD_FAIL | 651.0 | 29,979.12 | 30,003.32 | 30,000.00 | 0.8094 | 47.8 | 5.3 | 969.7 |
| f1_low_load | springboot | 5 | PASS | 607.0 | 189.05 | 969.82 | 1,710.00 | 0 | 32.9 | 14.1 | 1,140.7 |
| f2_high_load | springboot | 5 | THRESHOLD_FAIL | 684.0 | 30,330.20 | 53,979.21 | 59,840.00 | 0.0107 | 43.1 | 29.3 | 2,093.1 |

## 6. Caveats for downstream analysis

- f2_high_load runs 2–5 do not have streaming `*.json` (only `*-summary.json`) because `f2_raw_first_rep_only=true`; per-request timeseries is therefore only available for repetition 1 of f2.
- All five f2_high_load reps breached `http_req_duration{phase:load}: p(95)<2000` and `p(99)<5000` for every version, triggering `abortOnFail` early-exit. Wallclock differences between versions on f2 partly reflect *when* the abort fired, not just throughput.
- Container CPU% follows Docker convention (relative to one host core; can exceed 100% on multi-core).
- Startup CSV in this run reports `startup_ms` derived from `container_started_at`, which predates the benchmark; rely on `readiness_wait_ms` for cold-start comparisons.
- 0 OOMKill, 0 container restarts, 0 RUN_ERROR; all three /health endpoints remained 200 throughout the matrix.
