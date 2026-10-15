# F2-150 VUs800 validation summary

- Run ID: `aws-order-service-validation-1vcpu2gb-f2-150-vus800-20260531123228`
- Scenario: `f2_high_load`
- Parameters: `F2_RATE=150`, `F2_PREWARM_DURATION=2m`, `F2_DURATION=3m`, `PRE_ALLOCATED_VUS=800`, `MAX_VUS=1500`, `K6_QUIET=true`.
- Application resources: 1 vCPU / 2 GB, desired count 1, max task count 1, same for all versions.
- Window used for CloudWatch: `2026-05-31T12:37:51Z` to `2026-05-31T13:08:51Z`.

## Result

| version | verdict | load p95 ms | load p99 ms | load error rate | dropped iterations | observed VUs max | iterations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| quarkus-native | PASS | 94.20 | 379.48 | 0.0000 | 0 | 322 | 45001 |
| quarkus-jvm | PASS | 83.69 | 199.44 | 0.0000 | 0 | 228 | 45002 |
| springboot | PASS | 130.72 | 279.21 | 0.0000 | 0 | 597 | 45002 |

## Diagnostics

- Raw k6 error-signature scan: 0 matches in all three raw JSON files for `error`, `error_code`, `no route to host`, `connection reset`, `timeout`, `dial tcp`, TLS, EOF, or broken pipe patterns.
- ECS log scan: 0 suspect matches for OOM, killed process, allocation failure, exception, timeout, reset, route, or dial errors in application and DB reset log groups.
- Target health after run: all three target groups healthy.
- ALB generated 5XX datapoints: 0; target 5XX and target connection errors had no datapoints for each version.
- RDS CPU maximum observed: 38.72%
- RDS DatabaseConnections maximum observed: 62

## Interpretation

- Increasing k6 headroom from `PRE_ALLOCATED_VUS=450`, `MAX_VUS=1000` to `PRE_ALLOCATED_VUS=800`, `MAX_VUS=1500` removed the previous Spring Boot `218 dropped_iterations` signal in this short validation: current dropped iterations are `0`.
- The Spring Boot run still needed the most VUs (`597`) and had slower total-run p95 due to warmup/prewarm behavior, but its load-phase p95/p99 and error rate stayed inside the classification thresholds.
- This validates the short F2-150 configuration for the 1 vCPU / 2 GB methodology; it is still a validation run, not the final 5-repetition experiment.
