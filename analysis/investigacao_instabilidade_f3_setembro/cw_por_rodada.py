import boto3,datetime as dt,json,glob,statistics as st
s=boto3.Session(profile_name='pessoal',region_name='us-east-1'); CW=s.client('cloudwatch')
U=dt.timezone.utc
def P(x): return dt.datetime.fromisoformat(x.replace('Z','+00:00')[:19]+'+00:00')
def get(ns,m,dims,a,b,per,stat='Average'):
    r=CW.get_metric_statistics(Namespace=ns,MetricName=m,Dimensions=[{'Name':k,'Value':v} for k,v in dims.items()],StartTime=a,EndTime=b,Period=per,Statistics=[stat])
    return sorted((d['Timestamp'],d[stat]) for d in r['Datapoints'])
# retention probe
a=dt.datetime(2026,9,2,15,15,tzinfo=U); b=a+dt.timedelta(minutes=30)
for per in (60,300):
    print('probe CI CpuUtilized SB 02/09 period',per,'->',len(get('ECS/ContainerInsights','CpuUtilized',{'ClusterName':'order-service-cluster','TaskDefinitionFamily':'order-service-springboot'},a,b,per)),'pts')
    print('probe RDS CPU 02/09 period',per,'->',len(get('AWS/RDS','CPUUtilization',{'DBInstanceIdentifier':'order-service-postgres'},a,b,per)),'pts')
    print('probe EC2 runner CPU 02/09 period',per,'->',len(get('AWS/EC2','CPUUtilization',{'InstanceId':'i-03d4feffaa1a0b4f4'},a,b,per)),'pts')
# per-run peak window metrics
runs=[]
base="analysis/fargate/fase3-f3-rerun/"
for f in sorted(glob.glob(base+'f3-*-meta.json')+glob.glob(base+'saturated-sb-r4-r5/*-meta.json')):
    m=json.load(open(f)); pk=[p for p in m['phases'] if p['name']=='peak'][0]
    S=json.load(open(f.replace('-meta','-summary')))['metrics']['http_req_duration']['p(95)']
    tag=('SAT-' if 'saturated' in f else '')+f.split('/')[-1][3:-10]
    runs.append((tag,P(pk['start_utc']),P(pk['end_utc']),S,m['runtime']))
T=json.load(open(base+'_probe-sb-r4-live-2026-09-05/timing.json'))
t0=P(T['load_start_utc']); runs.append(('PROBE-sb',t0+dt.timedelta(seconds=420),t0+dt.timedelta(seconds=1020),72.7,'springboot'))
runs.sort(key=lambda r:r[1])
fam={'springboot':'order-service-springboot','quarkus-jvm':'order-service-quarkus-jvm','quarkus-native':'order-service-quarkus-native'}
rdsm=[('CPUUtilization','Average'),('ReadLatency','Average'),('WriteLatency','Average'),('DatabaseConnections','Maximum'),('DiskQueueDepth','Average'),('CommitLatency','Average'),('NetworkReceiveThroughput','Average'),('CPUCreditBalance','Average'),('CPUSurplusCreditBalance','Maximum'),('WriteIOPS','Average')]
hdr=['run','peak_start','p95']
rows=[]
for tag,a,b,p95,rt in runs:
    # align to 5-min grid fully inside peak
    a5=a+dt.timedelta(seconds=(300-a.timestamp()%300)%300); b5=a5+dt.timedelta(minutes=10) if a5+dt.timedelta(minutes=10)<=b+dt.timedelta(minutes=2) else b
    row={'run':tag,'peak_start':a.strftime('%m-%d %H:%M'),'p95':round(p95,1)}
    for m,stt in rdsm:
        v=[x for _,x in get('AWS/RDS',m,{'DBInstanceIdentifier':'order-service-postgres'},a5,b5,300,stt)]
        row['rds_'+m]=round(st.mean(v),5) if v else None
    for m in ('CpuUtilized','MemoryUtilized','NetworkRxBytes','NetworkTxBytes'):
        v=[x for _,x in get('ECS/ContainerInsights',m,{'ClusterName':'order-service-cluster','TaskDefinitionFamily':fam[rt]},a5,b5,300)]
        row['ci_'+m]=round(st.mean(v),1) if v else None
    for m,stt in (('CPUUtilization','Average'),('CPUUtilization','Maximum'),('NetworkPacketsIn','Sum'),('NetworkPacketsOut','Sum'),('NetworkIn','Sum')):
        v=[x for _,x in get('AWS/EC2',m,{'InstanceId':'i-03d4feffaa1a0b4f4'},a5,b5,300,stt)]
        row['runner_'+m+'_'+stt]=round(st.mean(v),2) if v else None
    rows.append(row)
import csv,sys
w=csv.DictWriter(sys.stdout,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
