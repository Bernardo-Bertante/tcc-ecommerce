# AWS EC2 F2 150 Pilot Summary

- Run ID: `aws-order-service-pilot-ec2-f2-150-20260527-114029`
- Scenario: `F2_RATE=150`, `F2_PREWARM_DURATION=2m`, `F2_DURATION=3m`, `PRE_ALLOCATED_VUS=450`, `MAX_VUS=1000`, `K6_QUIET=true`
- Runner: EC2 `t3.medium` in the benchmark VPC/subnet, SSM access, k6 `v2.0.0`
- Artifact SHA256: `6372447265e5c8eb637819c684bfd86d2368b4a66d01f03ee20bfba3abfbece5`

## k6 Verdicts

| Version | Verdict | Load fail rate | Load p95 | Load p99 | Dropped iterations | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Quarkus Native | PASS | 0.00% | 96.68 ms | 191.85 ms | 0 | No HTTP failures. |
| Quarkus JVM | PASS | 0.00% | 75.19 ms | 130.77 ms | 412 | No HTTP failures; small dropped-iteration count. |
| Spring Boot | THRESHOLD_FAIL | 64.10% | 10.2 s | 13.26 s | 15307 | Target failed during load; ECS stopped task with OOM. |

## Spring Boot Failure Detail

- Raw k6 status counts for Spring Boot: `200=12826`, `201=4800`, `502=5713`, `503=4619`, `504=3417`.
- Load phase failures: `12349` out of `19263` requests.
- Exact k6 log error repeatedly observed: `create order for status update failed with status 502: 502 Bad Gateway`.
- No EC2 raw/log matches for `no route to host`, `connection reset`, `timeout`, `dial tcp`, `TLS handshake`, `EOF`, or `connection refused`.
- ECS stopped task diagnostic: `exitCode=137`, `OutOfMemoryError: container killed due to memory usage`.
- ALB `HTTPCode_ELB_5XX_Count`: total `9496` across two 1-minute datapoints (`2391` then `7105`).
- ALB `TargetConnectionErrorCount` for Spring target group: total `5388` across the same two minutes.
- CloudWatch `HTTPCode_Target_5XX_Count` had no datapoints, which is consistent with ALB-generated errors while the target was unavailable rather than application-generated 5XX responses.

## Resource Observations

- ECS Spring Boot CPU reached `100%` maximum; MemoryUtilization reached `90.38%` maximum before the OOM stop.
- ECS Quarkus JVM CPU reached `100%` maximum but memory stayed around `35.55%`; the run passed.
- ECS Quarkus Native CPU stayed under `37.10%` maximum and memory under `5.62%`; the run passed.
- RDS did not look saturated in the collected window: CPU max `29.775%`, connections max `62`, read latency max `0.002s`, write latency max `0.00527s`.
- EC2 runner prechecks were healthy: `ulimit -n=65535`, ephemeral port range `32768 60999`; vmstat average CPU idle was about `73%`, with transient CPU saturation and free memory dipping to about `100 MB` late in the run.

## Conclusion

F2 150 from inside AWS is viable for Quarkus Native and Quarkus JVM with the pilot sizing. Spring Boot is not viable at `0.5 vCPU / 1 GB` for F2 150 in this pilot: it crossed thresholds because the container was killed for memory usage, producing ALB 502/503/504 responses and dropped iterations. The earlier local `no route to host` issue did not reproduce from the EC2 runner.