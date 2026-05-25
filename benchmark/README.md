# k6 Benchmarks

These scripts run short local smoke checks and longer benchmark scenarios for the Order Service and Order Processor variants.

## Order Service Local Targets

The current local Compose stack exposes:

| Version | BASE_URL |
| --- | --- |
| Quarkus Native | `http://localhost:8081` |
| Quarkus JVM | `http://localhost:8082` |
| Spring Boot JVM | `http://localhost:8083` |

The scripts use the API query parameters implemented by the services today: `pageSize`, `fromDate`, and `toDate`.

## Order Processor Local Targets

The local Lambda/RIE Compose stack exposes:

| Version | BASE_URL |
| --- | --- |
| Spring Boot JVM | `http://localhost:9001` |
| Quarkus JVM | `http://localhost:9002` |
| Quarkus Native | `http://localhost:9003` |

The Lambda scenarios post to `/2015-03-31/functions/function/invocations` automatically for localhost targets. AWS Function URLs are invoked directly at their URL root.

## Prerequisites

- k6 installed and available as `k6`, or set `K6_BIN=/path/to/k6`.
- The local benchmark stack running for local tests:

```bash
docker compose -f infrastructure/docker-compose.benchmark.yml up --build -d
```

## Smoke Runs

Smoke mode keeps duration, rates, and seed sizes small. For Order Service:

```bash
SMOKE=true k6 run -e BASE_URL=http://localhost:8081 benchmark/scenarios/f1_low_load.js
SMOKE=true k6 run -e BASE_URL=http://localhost:8082 benchmark/scenarios/f2s_summary_only.js
SMOKE=true REPETITIONS=1 VERSION_REST_SECONDS=0 FARGATE_SCENARIOS="f1_low_load f2s_summary_only" benchmark/run/run-fargate.sh
```

For Order Processor, start the local Lambda/DynamoDB stack and run L2/L3 smoke:

```bash
docker compose -f infrastructure/docker-compose.processor.yml --profile quarkus --profile quarkus-native up --build -d

SMOKE=true REPETITIONS=1 REST_SECONDS=0 LAMBDA_SCENARIOS="l2_warm_burst l3_concurrency_burst" benchmark/run/run-lambda.sh
```

L1 can be executed locally only as a dry run, because local RIE does not force a real AWS Lambda cold start:

```bash
SMOKE=true ALLOW_UNRESET_L1=true LAMBDA_SCENARIOS="l1_sparse_coldstart" benchmark/run/run-lambda.sh
```

## Fargate/Local Runner

The default Fargate runner executes F1, F2, F2-S, and F3 sequentially for all three local versions:

```bash
SMOKE=true benchmark/run/run-fargate.sh
```

Before running the first scenario, the runner checks the health endpoint for each target URL and stops early with a clear message if the service is not reachable.

For the full experiment, omit `SMOKE=true`. Defaults are 5 repetitions and 600 seconds of rest after each version block. Override with `REPETITIONS` and `VERSION_REST_SECONDS` when needed. `REST_SECONDS` is still accepted as a backward-compatible alias.

Results are written to `benchmark/results/` as k6 JSON streams and a run log. When enabled, startup timing and container resource snapshots are also written there as CSV files.

## Fargate/AWS Runner

The same Fargate runner can target AWS ALB URLs by passing `FARGATE_VERSIONS`. When this variable is set, the runner switches to `ENVIRONMENT=aws`, writes outputs under `benchmark/results/<RUN_ID>/`, and disables Docker-only startup/container-stat collection.

```bash
FARGATE_VERSIONS="quarkus-native|http://ALB_DNS:8081 quarkus-jvm|http://ALB_DNS:8082 springboot|http://ALB_DNS:8083" \
  SMOKE=true \
  REPETITIONS=1 \
  VERSION_REST_SECONDS=0 \
  FARGATE_SCENARIOS="f1_low_load f2s_summary_only" \
  benchmark/run/run-fargate.sh
```

For repeatable AWS runs, use a config file based on `benchmark/run/fargate-aws.env.example`:

```bash
RUN_CONFIG=benchmark/run/fargate-aws.env benchmark/run/run-fargate.sh
```

Use `RESET_DB_COMMAND` to reset PostgreSQL before each version block. This prevents `GET /orders/summary` from being biased by data accumulated by a previous version.

```bash
RESET_DB_COMMAND="infrastructure/aws/scripts/reset-order-service-db.sh --stack-name order-service-benchmark --profile PROFILE --region REGION"
```

For the final AWS Fargate experiment, omit `SMOKE=true` and keep the official defaults unless the methodology is revised:

```bash
RUN_ID="aws-order-service-final-$(date +%Y%m%d-%H%M%S)" \
  FARGATE_VERSIONS="quarkus-native|http://ALB_DNS:8081 quarkus-jvm|http://ALB_DNS:8082 springboot|http://ALB_DNS:8083" \
  REPETITIONS=5 \
  VERSION_REST_SECONDS=600 \
  FARGATE_SCENARIOS="f1_low_load f2_high_load f2s_summary_only f3_burst_autoscaling" \
  RESET_DB_COMMAND="infrastructure/aws/scripts/reset-order-service-db.sh --stack-name order-service-benchmark --profile PROFILE --region REGION" \
  benchmark/run/run-fargate.sh
```

After an AWS run, collect CloudWatch metrics for the same time window:

```bash
benchmark/run/collect-fargate-cloudwatch-metrics.sh \
  --stack-name order-service-benchmark \
  --run-id "$RUN_ID" \
  --start-time "2026-05-24T18:00:00Z" \
  --end-time "2026-05-24T20:00:00Z" \
  --profile PROFILE \
  --region REGION
```

## Local Preliminary Overnight Run

Use `benchmark/run/local-preliminary.env` for the long local validation run before the AWS Fargate experiment:

```bash
RUN_CONFIG=benchmark/run/local-preliminary.env benchmark/run/run-fargate.sh
```

This config runs without `SMOKE`, executes only F1 and F2, skips F2-S, and skips F3 because F3 measures autoscaling behavior that only exists in real AWS Fargate. It also captures startup timing before load and Docker CPU/memory snapshots while the run is active.

Default local preliminary timing is 3 repetitions. Each repetition runs F1 and F2 for Quarkus Native, Quarkus JVM, and Spring Boot JVM, with a 600 second rest after each version block. With the normal scenario durations, this is roughly 8 to 9 hours depending on startup and cleanup time.

Generated files include:

- `benchmark/results/fargate-$RUN_ID.log`
- `benchmark/results/startup-$RUN_ID.csv`
- `benchmark/results/container-stats-$RUN_ID.csv`
- `benchmark/results/<scenario>_<version>_run<repetition>.json`

## Lambda Runner

The Lambda runner executes L1, L2, and L3 against configurable HTTP endpoints. Without `LAMBDA_VERSIONS`, it uses the local Processor ports `9001`, `9002`, and `9003`:

```bash
SMOKE=true LAMBDA_SCENARIOS="l2_warm_burst l3_concurrency_burst" benchmark/run/run-lambda.sh
```

For AWS Function URLs, pass the same invocation method for all versions:

```bash
LAMBDA_VERSIONS="springboot|https://example.lambda-url" RESET_URL=https://example.reset-url benchmark/run/run-lambda.sh
```

L1 requires `RESET_URL` so each measured invocation can force a cold start. For local dry runs only, set `ALLOW_UNRESET_L1=true`.

Lambda runner outputs are written to `benchmark/results/<RUN_ID>/` with one raw JSON stream, one summary file, and one `run.log` per run.

## Single Scenario Output

All scenarios support k6 JSON output:

```bash
k6 run \
  -e BASE_URL=http://localhost:8081 \
  --out json=benchmark/results/f1_quarkus_native_run1.json \
  benchmark/scenarios/f1_low_load.js
```

## Scenario Summary

- `f1_low_load.js`: 30 req/s for 10 minutes.
- `f2_high_load.js`: 10 minutes pre-warm plus 30 minutes at 300 req/s.
- `f2s_summary_only.js`: 50 req/s summary-only for 5 minutes.
- `f3_burst_autoscaling.js`: burst from 50 to 500 req/s using the F1/F2 endpoint mix.
- `l1_sparse_coldstart.js`: sparse calls, with cold reset coordinated by `RESET_URL`.
- `l2_warm_burst.js`: one call every 3 seconds, first 10 iterations tagged as warmup.
- `l3_concurrency_burst.js`: 200 concurrent shared iterations.

F1, F2, and F3 use this measured mix: 50% `GET /orders/{id}`, 20% `POST /orders`, 15% `GET /orders/customer/{customerId}`, 10% `PUT /orders/{id}/status`, and 5% `GET /orders/summary`.
