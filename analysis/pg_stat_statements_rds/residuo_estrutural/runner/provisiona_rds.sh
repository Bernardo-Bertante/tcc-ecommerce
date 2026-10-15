#!/usr/bin/env bash
# Provisiona o RDS exploratorio (residuo_estrutural). Tag projeto=tcc-pgss-residuo. Exploratorio.
set -euo pipefail
export AWS_PROFILE=pessoal AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
PG=pgss-res-pg16; DB=pgss-res-postgres; TAG="Key=projeto,Value=tcc-pgss-residuo"
aws rds describe-db-parameter-groups --db-parameter-group-name $PG >/dev/null 2>&1 || aws rds copy-db-parameter-group --source-db-parameter-group-identifier order-service-pg16-custom \
  --target-db-parameter-group-identifier $PG --target-db-parameter-group-description "pgss residuo (copia do oficial + auto_explain)" --tags $TAG >/dev/null
cat > /tmp/pgss_res_params.json <<'J'
[{"ParameterName":"shared_preload_libraries","ParameterValue":"pg_stat_statements,pg_tle,auto_explain","ApplyMethod":"pending-reboot"},
{"ParameterName":"auto_explain.log_min_duration","ParameterValue":"0","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_analyze","ParameterValue":"1","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_buffers","ParameterValue":"1","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_timing","ParameterValue":"1","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_verbose","ParameterValue":"1","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_nested_statements","ParameterValue":"1","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_format","ParameterValue":"json","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.sample_rate","ParameterValue":"0.02","ApplyMethod":"immediate"},
{"ParameterName":"auto_explain.log_parameter_max_length","ParameterValue":"-1","ApplyMethod":"immediate"},
{"ParameterName":"pg_stat_statements.track_planning","ParameterValue":"1","ApplyMethod":"pending-reboot"}]
J
aws rds modify-db-parameter-group --db-parameter-group-name $PG --parameters file:///tmp/pgss_res_params.json >/dev/null
aws rds create-db-instance --db-instance-identifier $DB --db-instance-class db.t3.micro --engine postgres --engine-version 16.4 \
  --allocated-storage 20 --storage-type gp3 \
  --master-username orderuser --master-user-password <SENHA_RDS> --db-name orderdb \
  --availability-zone us-east-1d --db-subnet-group-name default --vpc-security-group-ids sg-092b010799f56134f \
  --db-parameter-group-name $PG --publicly-accessible --no-multi-az --no-storage-encrypted \
  --backup-retention-period 0 --no-enable-performance-insights --tags $TAG >/dev/null
echo criado
