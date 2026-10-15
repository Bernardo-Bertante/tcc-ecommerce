#!/bin/bash
# Verificação do teste de fumaça (roda localmente com --profile pessoal). Uso: verify_smoke.sh <RUN_ID> <start_epoch_s>
set -uo pipefail
RUN_ID="$1"; START="$2"; END=$(date -u +%s)
P="--profile pessoal --region us-east-1"
B=exp-lazy-results-776648109551
OUT=$(dirname "$0")/smoke_$RUN_ID; mkdir -p "$OUT"
aws s3 cp $P --only-show-errors --recursive "s3://$B/$RUN_ID/" "$OUT/"
echo "== 1. Itens gravados nas tabelas exp-lazy (scan)"
for t in exp-lazy-processed-orders exp-lazy-stock-reservations; do
  echo "-- $t: $(aws dynamodb scan $P --table-name $t --select COUNT --query Count --output text) itens"
  aws dynamodb scan $P --table-name $t --projection-expression orderId --query 'Items[].orderId.S' --output text | tr '\t' '\n' | sort | uniq -c
done
echo "== 2. Pontos sdk_* por tabela (EXP_LAZY, V1/V2) e falhas"
python3 - "$OUT/points.csv" "$OUT/extract_summary.json" <<'EOF'
import csv,sys,json,collections
c=collections.Counter()
for r in csv.DictReader(open(sys.argv[1])):
    if r['pt'].startswith('sdk_'):
        c[(r['pt'], r['x'].split(' table=')[1].split()[0] if ' table=' in r['x'] else '?')]+=1
for k,v in sorted(c.items()): print(k,v)
print(json.load(open(sys.argv[2])))
EOF
echo "== 3. 'AccessDenied' / exceções nos log groups exp-lazy (janela da fumaça)"
for f in v0 v1 v2; do
  for pat in AccessDenied Exception ERROR; do
    n=$(aws logs filter-log-events $P --log-group-name /aws/lambda/exp-lazy-qj-$f --start-time $((START*1000)) --end-time $((END*1000)) --filter-pattern "$pat" --query 'length(events)' --output text)
    echo "exp-lazy-qj-$f $pat: $n"
  done
done
grep -c -i accessdenied "$OUT/run.log" | sed 's/^/run.log AccessDenied: /'
echo "== 4. Escritas nas tabelas OFICIAIS na janela (CloudWatch ConsumedWriteCapacityUnits, Sum/60s)"
for t in processed_orders stock_reservations processing-results; do
  echo "$t: $(aws cloudwatch get-metric-statistics $P --namespace AWS/DynamoDB --metric-name ConsumedWriteCapacityUnits --dimensions Name=TableName,Value=$t --start-time $(date -u -d @$((START-300)) +%FT%TZ) --end-time $(date -u -d @$END +%FT%TZ) --period 60 --statistics Sum --query 'Datapoints[].Sum' --output text) (vazio = nenhuma escrita)"
done
echo "   controle positivo (tabelas exp-lazy, mesma consulta):"
for t in exp-lazy-processed-orders exp-lazy-stock-reservations; do
  echo "$t: $(aws cloudwatch get-metric-statistics $P --namespace AWS/DynamoDB --metric-name ConsumedWriteCapacityUnits --dimensions Name=TableName,Value=$t --start-time $(date -u -d @$((START-300)) +%FT%TZ) --end-time $(date -u -d @$END +%FT%TZ) --period 60 --statistics Sum --query 'Datapoints[].Sum' --output text)"
done
echo "== 5. Funções oficiais inalteradas (vs oficiais_antes.json)"
for f in order-processor-quarkus-jvm order-processor-springboot order-processor-quarkus-native; do
  aws lambda get-function-configuration $P --function-name $f --query '[FunctionName,CodeSha256,RevisionId,LastModified]' --output text
done
