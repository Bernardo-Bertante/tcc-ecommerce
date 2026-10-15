# F2-150 Validation Summary

Run ID: `aws-order-service-validation-1vcpu2gb-f2-150-20260528-224008`

Scope: validation-only pilot for the 1 vCPU / 2 GB common Fargate profile. This is not the final 5-repetition experiment.

## Configuration

- AWS profile/region: `awslab`, `us-east-1`
- ECS task sizing: `TaskCpu=1024`, `TaskMemory=2048`
- Desired/max tasks: `DesiredCount=1`, `MaxTaskCount=1`
- Runner: EC2 `t3.large`, k6 `v2.0.0`
- Runner limits: `ulimit -n=1048576`, ephemeral ports `1024 65000`
- Scenario: `f2_high_load`
- Parameters: `F2_RATE=150`, `F2_PREWARM_DURATION=2m`, `F2_DURATION=3m`, `PRE_ALLOCATED_VUS=450`, `MAX_VUS=1000`, `K6_QUIET=true`

## Result

All three versions completed with k6 exit code `0` and verdict `PASS`.

| Version | Load error rate | Load p95 | Load p99 | Dropped iterations | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| quarkus-native | 0% | 80.64 ms | 168.65 ms | 0 | PASS |
| quarkus-jvm | 0% | 90.20 ms | 182.84 ms | 0 | PASS |
| springboot | 0% | 133.60 ms | 1.61 s | 218 | PASS |

Notes:

- `F2_RATE=150` is the k6 constant-arrival-rate iteration rate used by the scenario. Observed total HTTP throughput was about 162-164 HTTP requests/s because some workload operations issue more than one HTTP request.
- Spring Boot had 218 dropped iterations, but still completed the run with 0 HTTP failures and passed the configured latency/error thresholds.

## Diagnostics

- Raw k6 JSON scan found 0 lines with `no route to host`, `connection reset`, `timeout`, `dial tcp`, TLS error signatures, `EOF`, or `broken pipe`.
- ECS services had `running_count=1`, `stopped_count=0` for all three versions after the run.
- Application log scan found 0 matches for `OutOfMemory`, `Killed`, `Cannot allocate memory`, `ERROR`, `Exception`, `timeout`, `connection reset`, `no route to host`, or `dial tcp` during the validation window.
- ALB `HTTPCode_ELB_5XX_Count`: 0 datapoints / 0 sum.
- Per-version ALB `HTTPCode_Target_5XX_Count`: 0 for all versions.
- Per-version ALB `TargetConnectionErrorCount`: 0 for all versions.
- `HealthyHostCount`: minimum 1 for all versions.
- `UnHealthyHostCount`: maximum 0 for all versions.

## Resource Metrics

| Version | ECS CPU max | ECS memory max | ALB target response max |
| --- | ---: | ---: | ---: |
| quarkus-native | 16.63% | 2.91% | 0.586 s |
| quarkus-jvm | 84.30% | 17.82% | 1.142 s |
| springboot | 100.00% | 21.34% | 4.424 s |

RDS maxima in the collected window:

- CPU: 38.51%
- Database connections: 62
- Read latency: 0.002 s
- Write latency: 0.004874 s

## Interpretation

The 1 vCPU / 2 GB profile fixed the invalid-data failure mode from the previous Spring Boot run: no OOM, no ECS task stop, no unhealthy target, no ALB-generated 5XX, and no k6 network errors were observed. The F2-150 validation data is usable for deciding whether to proceed with larger validation or the later final run.
