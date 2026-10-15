#!/bin/bash
# Verificação do teste de fumaça do Spring Boot (roda localmente com --profile pessoal).
# Uso: verify_smoke.sh <RUN_ID> <start_epoch_s>
set -uo pipefail
RUN_ID="$1"; START="$2"; END=$(date -u +%s)
P="--profile pessoal --region us-east-1"
B=exp-lazy-sb-results-776648109551
DIR=$(cd "$(dirname "$0")" && pwd)
OUT="$DIR/smoke_$RUN_ID"; mkdir -p "$OUT"
aws s3 cp $P --only-show-errors --recursive "s3://$B/$RUN_ID/" "$OUT/"
echo "== 1. Itens gravados nas tabelas exp-lazy-sb (scan; 00000000-… = marcador da V2)"
for t in exp-lazy-sb-processed-orders exp-lazy-sb-stock-reservations; do
  echo "-- $t: $(aws dynamodb scan $P --table-name $t --select COUNT --query Count --output text) itens"
  aws dynamodb scan $P --table-name $t --projection-expression orderId --query 'Items[].orderId.S' --output text | tr '\t' '\n' | sort | uniq -c
done
echo "== 2. Pontos sdk_* por tabela (EXP_LAZY, V1/V2), falhas e resumo da extração"
python3 - "$OUT/points.csv" "$OUT/extract_summary.json" <<'EOF'
import csv,sys,json,collections
c=collections.Counter()
for r in csv.DictReader(open(sys.argv[1])):
    if r['pt'].startswith('sdk_'):
        c[(r['pt'], r['x'].split(' table=')[1].split()[0] if ' table=' in r['x'] else '?')]+=1
for k,v in sorted(c.items()): print(k,v)
print(json.load(open(sys.argv[2])))
EOF
echo "== 3. 'AccessDenied' / 'Exception' / 'ERROR' / sdk_fail / prep_fail nos log groups exp-lazy-sb (janela) e no run.log"
for f in v0 v1 v2; do
  for pat in AccessDenied Exception ERROR sdk_fail prep_fail; do
    n=$(aws logs filter-log-events $P --log-group-name /aws/lambda/exp-lazy-sb-$f --start-time $((START*1000)) --end-time $((END*1000)) --filter-pattern "\"$pat\"" --query 'length(events)' --output text)
    echo "exp-lazy-sb-$f $pat: $n"
  done
done
for pat in AccessDenied Exception ERROR; do echo "run.log $pat: $(grep -c "$pat" "$OUT/run.log")"; done
echo "== 4. Escritas nas tabelas OFICIAIS na janela (ConsumedWriteCapacityUnits, Sum/60s)"
for t in processed_orders stock_reservations processing-results; do
  echo "$t: $(aws cloudwatch get-metric-statistics $P --namespace AWS/DynamoDB --metric-name ConsumedWriteCapacityUnits --dimensions Name=TableName,Value=$t --start-time $(date -u -d @$((START-300)) +%FT%TZ) --end-time $(date -u -d @$END +%FT%TZ) --period 60 --statistics Sum --query 'Datapoints[].Sum' --output text) (vazio ou 0.0 = nenhuma escrita)"
done
echo "   controle positivo (tabelas exp-lazy-sb, mesma consulta):"
for t in exp-lazy-sb-processed-orders exp-lazy-sb-stock-reservations; do
  echo "$t: $(aws cloudwatch get-metric-statistics $P --namespace AWS/DynamoDB --metric-name ConsumedWriteCapacityUnits --dimensions Name=TableName,Value=$t --start-time $(date -u -d @$((START-300)) +%FT%TZ) --end-time $(date -u -d @$END +%FT%TZ) --period 60 --statistics Sum --query 'Datapoints[].Sum' --output text)"
done
echo "== 5. Funções oficiais (comparar com infra/oficiais_antes.json)"
for f in order-processor-quarkus-jvm order-processor-springboot order-processor-quarkus-native; do
  aws lambda get-function-configuration $P --function-name $f --query '[FunctionName,CodeSha256,RevisionId,LastModified]' --output text
done
echo "== 6. Por amostra fria: runtime, CodeSha256, Init, e (V2) preparação antes do START"
python3 - "$OUT" <<'EOF'
import csv,json,sys,collections
d=sys.argv[1]
inv={r['request_id']:r for r in csv.DictReader(open(f'{d}/invocations.csv'))}
pts=collections.defaultdict(dict)
for p in csv.DictReader(open(f'{d}/points.csv')):
    if p['inv']=='0' and p.get('wall'): pts[p['log_stream']][p['pt']]=p
ok=True
for s in (json.loads(l) for l in open(f'{d}/samples.jsonl')):
    if s['kind']!='cold': continue
    r=inv.get(s.get('request_id'),{})
    line=f"{s['variant']} b={s['block']} pos={s['pos']} valid={s['valid_cold']} runtime={r.get('runtime_version')} sha={s['code_sha256'][:12]}… init={r.get('init_ms')} dur={r.get('duration_ms')}"
    if r.get('runtime_version')!='java:21.v68': ok=False
    if s['variant']=='V2':
        pp=pts.get(r.get('log_stream'),{})
        start=float(r['start_ts']); po=pp.get('prep_out'); ie=pp.get('init_end'); pf=pp.get('prep_fail')
        init_end_ts=float(r['init_start_ts'])+float(r['init_ms'])
        inside=po is not None and float(po['wall'])<=init_end_ts
        line+=f" | prep_out dentro do init (<= INIT_START+Init Duration = fim do init): {inside}; antes do START: {po is not None and float(po['wall'])<=start} (prep_out={po and po['wall']}, init_end_pt={ie and ie['wall']}, fim_init={int(init_end_ts)}, START={int(start)}) prep_fail={pf is not None} init<=8000: {float(r['init_ms'])<=8000}"
        if not inside or float(po['wall'])>start or pf is not None or float(r['init_ms'])>8000: ok=False
    if s['variant']=='V0' and s['code_sha256']!='ODLvR0a13wdABKP6LvMTo/xvKxTpEUz3H79fgDg0bbg=': ok=False; line+=' | V0 SHA DIFERENTE DO OFICIAL'
    print(line)
print('TODAS AS CHECAGENS DA SEÇÃO 6:', 'OK' if ok else 'FALHOU')
EOF
