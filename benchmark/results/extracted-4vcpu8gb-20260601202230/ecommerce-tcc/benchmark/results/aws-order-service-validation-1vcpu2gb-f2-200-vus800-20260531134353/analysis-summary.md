# F2-200 VUs800 validation summary

- Run ID: `aws-order-service-validation-1vcpu2gb-f2-200-vus800-20260531134353`
- Scenario: `f2_high_load`
- Parameters: `F2_RATE=200`, `F2_PREWARM_DURATION=2m`, `F2_DURATION=3m`, `PRE_ALLOCATED_VUS=800`, `MAX_VUS=1500`, `K6_QUIET=true`.
- Application resources: 1 vCPU / 2 GB, desired count 1, max task count 1, same for all versions.
- Run window: `2026-05-31T14:01:48Z` to `2026-05-31T14:25:33Z`.
- Window used for CloudWatch: `2026-05-31T13:59:48Z` to `2026-05-31T14:30:33Z`.

## Result

| version | verdict | load p95 ms | load p99 ms | load error rate | dropped iterations | observed VUs max | iterations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| quarkus-native | PASS | 135.21 | 227.26 | 0.0000 | 0 | 354 | 60001 |
| quarkus-jvm | PASS | 126.59 | 341.93 | 0.0000 | 0 | 420 | 60000 |
| springboot | PASS | 360.15 | 1770.00 | 0.0000 | 3163 | 1293 | 56839 |

## Diagnostics

- Raw k6 error-signature scan: 0 matches in all three raw JSON files for `error`, `error_code`, `no route to host`, `connection reset`, `timeout`, `dial tcp`, TLS, EOF, or broken pipe patterns.
- ECS log scan: 0 suspect matches for OOM, killed process, allocation failure, exception, timeout, reset, route, or dial errors in application and DB reset log groups.
- Target health after run: all three target groups healthy.
- ALB generated 5XX datapoints: 0; target 5XX and target connection errors had no datapoints for each version.
- RDS CPU maximum observed: 53.53%
- RDS DatabaseConnections maximum observed: 62
- ECS CPU maximum observed: Spring Boot 99.96%, Quarkus JVM 38.89%, Quarkus Native 12.45%.
- ECS memory maximum observed: Spring Boot 54.25%, Quarkus JVM 17.87%, Quarkus Native 2.73%.

## Interpretation

- Quarkus Native and Quarkus JVM sustained the F2-200 short validation cleanly: `PASS`, zero load-phase request failures, zero dropped iterations, and observed VUs stayed well below the configured headroom.
- Spring Boot also passed the latency/error classification thresholds, but it did not sustain the arrival rate cleanly: `3163` dropped iterations, observed VUs max `1293`, aggregate `vus_max` `2098`, and ECS CPU reached ~100%.
- Compared with F2-150 VUs800, Spring Boot moved from dropped iterations `0` to `3163`, observed VUs max `597` to `1293`, load p95 `130.72 ms` to `360.15 ms`, and load p99 `279.21 ms` to `1770.00 ms`.
- This is a useful terrain-preparation result for the 1 vCPU / 2 GB methodology, but it is not the final 5-repetition experiment.
