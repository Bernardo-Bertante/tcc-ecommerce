# Fargate Runbook — Official Order Service Benchmarks

## Scope

This runbook reflects the current official methodology for ECS Fargate benchmarks.

- Do not run multiple runtimes against the same official database.
- Do not run k6 with raw JSON unless explicitly requested.
- Do not teardown before local artifact validation.

## AWS Defaults (Personal Account)

```env
AWS_PROFILE=pessoal
AWS_REGION=us-east-1
STACK_NAME=order-service-benchmark
```

Resolve account dynamically:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text
```

Do not hardcode account IDs.

Security note: never use `BenchmarkIngressCidr=0.0.0.0/0` as the recommended default. Use the operator public IP in `/32` form. Example to set the runner-allowed CIDR dynamically from the operator machine:

```bash
RUNNER_ALLOWED_CIDR="$(curl -s https://checkip.amazonaws.com)/32"
```

`0.0.0.0/0` is acceptable only for short-lived local debugging; it must never be committed to the repository or used in official runs.

## Official Infrastructure Sizing

- ECS Task: `TaskCpu=8192`, `TaskMemory=16384`
- RDS: `DbInstanceClass=db.t3.medium`
- Spring JVM options: `-Xms512m -Xmx6144m -XX:MaxMetaspaceSize=256m`
- Runner: `t3.large`, `30 GB gp3`
- k6 stress capacity: `PRE_ALLOCATED_VUS=1500`, `MAX_VUS=3000`

## Scenario Model

- `F1`: 30 req/s (normal day)
- `F2`: 60 req/s (predictable peak)
- `F2-S`: 60 req/s, 100% `GET /orders/summary`
- `F3`: Black Friday phases (30 -> 225 -> 300 -> 30)
- `F3-S`: isolated stress at 300 req/s

Important reclassification:

- Any legacy `F2-300` script/result must be classified as `F3-S`, never `F2`.

## Official Run-ID Patterns

- `official-clean-8vcpu16gb-rds-t3medium-f1-30-<runtime>-summaryonly-<timestamp>`
- `official-clean-8vcpu16gb-rds-t3medium-f2-60-<runtime>-summaryonly-<timestamp>`
- `official-clean-8vcpu16gb-rds-t3medium-f2s-summary-60-<runtime>-summaryonly-<timestamp>`
- `official-clean-8vcpu16gb-rds-t3medium-f3-blackfriday-225-300-<runtime>-summaryonly-<timestamp>`
- `official-clean-8vcpu16gb-rds-t3medium-f3s-300-<runtime>-vus1500max3000-summaryonly-<timestamp>`

## IAM Decision Rule Before Deploy

For `order-service-stack.yaml`:

- If `ExistingTaskExecutionRoleArn` and `ExistingTaskRoleArn` are empty:
  - stack creates IAM roles
  - use `CAPABILITY_NAMED_IAM`
- If both are provided:
  - stack reuses existing roles
  - role creation is skipped

For `order-processor-stack.yaml`:

- template creates Lambda execution role
- use `CAPABILITY_IAM`

## CloudWatch Collection

Collect for exact run window with small buffer (`+-60s`):

- ECS: `CPUUtilization`, `MemoryUtilization`
- RDS: `CPUUtilization`, `DatabaseConnections`, `ReadLatency`, `WriteLatency`
- ALB: `HTTPCode_ELB_5XX_Count`
- Target group metrics when available:
  - `HTTPCode_Target_5XX_Count`
  - `TargetConnectionErrorCount`
  - `HealthyHostCount`
  - `UnHealthyHostCount`

## Artifact Rule (Mandatory)

Never terminate runner or delete stack before all checks pass:

1. `tar.gz` exists locally
2. `.sha256` exists locally
3. local SHA256 verification succeeds
4. summary JSON exists inside tar
5. `run.log` exists inside tar

Validation pattern:

```bash
TAR="<artifact>.tar.gz"
SHA="$TAR.sha256"
awk -v tar="$TAR" '{print $1 "  " tar}' "$SHA" | sha256sum -c -
```

## Teardown Rule

After artifact + checksum + CloudWatch are safe:

1. terminate runner
2. wait `instance-terminated`
3. delete runner security group
4. delete CloudFormation stack
5. wait `stack-delete-complete`

If stack deletion fails due to VPC dependency, list and diagnose:

- ENIs
- Security Groups
- ALBs
- Target Groups
- NAT Gateways
- VPC endpoints

Do not manually delete requester-managed ENIs.
If only runner SG remains, delete it and retry stack deletion.
