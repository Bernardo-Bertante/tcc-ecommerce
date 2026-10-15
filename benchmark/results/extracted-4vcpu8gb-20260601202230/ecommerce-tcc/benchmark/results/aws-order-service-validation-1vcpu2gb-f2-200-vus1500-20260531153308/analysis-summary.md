# Analise AWS F2-200 VUs1500

- Run ID: `aws-order-service-validation-1vcpu2gb-f2-200-vus1500-20260531153308`
- Actual remote run ID: `20260531-154955`
- App resources: 1 vCPU / 2 GB, desired count 1 for every version
- k6 parameters: `F2_RATE=200`, `PRE_ALLOCATED_VUS=1500`, `MAX_VUS=3000`, `F2_PREWARM_DURATION=2m`, `F2_DURATION=3m`
- Window: `2026-05-31T15:49:55Z` to `2026-05-31T16:19:17Z`

## k6 summary

| Version | Verdict | p95 load ms | p99 load ms | Error rate | HTTP reqs | Iterations | Dropped | VUs max | vus_max max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Quarkus Native | PASS | 127.46 | 238.79 | 0 | 66121 | 60001 | 0 | 343 | 3000 |
| Quarkus JVM | PASS | 118.42 | 222.29 | 0 | 66121 | 60001 | 0 | 646 | 3000 |
| Spring Boot | PASS | 210.41 | 776.94 | 0 | 63773 | 57873 | 2128 | 1776 | 3285 |

## Diagnostics

- Raw k6 scan found 0 `http_req_failed` points and 0 matching network/TLS/socket error strings (`no route to host`, `connection reset`, timeout, `dial tcp`, TLS, EOF, broken pipe).
- ECS application log filter returned 0 events in the validation window for all three service log groups.
- Target health after run: all target groups healthy.
- ALB global 5XX total: n/a.

## CloudWatch highlights

| Version | ECS CPU max % | ECS Mem max % | ALB resp avg s | ALB resp max s | Target 5XX | Conn errors | Healthy min | Unhealthy max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Quarkus Native | 23.40 | 2.76 | 0.0181 | 0.9016 | n/a | n/a | 1 | 0 |
| Quarkus JVM | 61.69 | 17.50 | 0.0321 | 2.9097 | n/a | n/a | 1 | 0 |
| Spring Boot | 100.00 | 50.78 | 1.8674 | 17.7812 | n/a | n/a | 1 | 0 |

## Interpretation

- With the larger VU headroom, all three versions completed and thresholds classified as `PASS`.
- Quarkus Native and Quarkus JVM sustained the target without dropped iterations; both kept p95 and p99 comfortably under the thresholds.
- Spring Boot improved versus the previous VUs800 F2-200 run, but still showed load-generation demand above steady completion: `2128` dropped iterations, observed VUs `1776`, and `vus_max` max `3285`.
- The absence of k6/network errors, ALB 5XX, target connection errors, and unhealthy targets points away from ALB/k6/network limits as the primary cause. The remaining Spring drops look like application-side saturation/backlog under this shape of F2-200, not a hard runner/socket failure.

## Generated files

- `k6-summary.csv`
- `cloudwatch-summary.csv`
- `error-scan.csv`
- `ecs-log-diagnostics.csv`
- `target-health-summary.csv`
- `analysis-summary.md`
- `SHA256SUMS_ALL.txt`
