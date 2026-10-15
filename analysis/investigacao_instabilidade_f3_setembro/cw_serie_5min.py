import boto3,datetime as dt,json,glob,os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','fargate','fase3-f3-rerun'))
s=boto3.Session(profile_name='pessoal',region_name='us-east-1'); CW=s.client('cloudwatch')
def P(x): return dt.datetime.fromisoformat(x.replace('Z','')[:19]).replace(tzinfo=dt.timezone.utc)
fam={'springboot':'order-service-springboot','quarkus-jvm':'order-service-quarkus-jvm','quarkus-native':'order-service-quarkus-native'}
runs=[]
for f in sorted(glob.glob('f3-*-timing.json')+glob.glob('saturated-sb-r4-r5/*-timing.json')):
    rt=[k for k in fam if 'f3-'+k+'-' in f][0]; runs.append((('SAT ' if 'sat' in f else '')+f.split('/')[-1][3:-12],rt,P(json.load(open(f))['load_start_utc'])))
runs.append(('probe sb',"springboot",P(json.load(open('_probe-sb-r4-live-2026-09-05/timing.json'))['load_start_utc'])))
runs.sort(key=lambda r:r[2])
def series(ns,m,dims,a,b):
    r=CW.get_metric_statistics(Namespace=ns,MetricName=m,Dimensions=[{'Name':k,'Value':v} for k,v in dims.items()],StartTime=a,EndTime=b,Period=300,Statistics=['Average'])
    return {d['Timestamp']:d['Average'] for d in r['Datapoints']}
print('bin label = offset (min) of 5-min bin START relative to load start; phases: 0-5 base@48, 5-7 ramp, 7-17 peak@240, 17-19 ramp, 19-24 rec@48')
for tag,rt,t0 in runs:
    a=t0-dt.timedelta(minutes=5); b=t0+dt.timedelta(minutes=30)
    c=series('ECS/ContainerInsights','CpuUtilized',{'ClusterName':'order-service-cluster','TaskDefinitionFamily':fam[rt]},a,b)
    r=series('AWS/RDS','CPUUtilization',{'DBInstanceIdentifier':'order-service-postgres'},a,b)
    ks=sorted(set(c)|set(r))
    print(f'{tag:28s}', '  '.join(f'[{(k-t0).total_seconds()/60:+5.1f}] app={c.get(k,float("nan")):5.0f} rds={r.get(k,float("nan")):4.1f}' for k in ks if -5<(k-t0).total_seconds()/60<26))
