"""
Extrai CPU/memoria de container (Fargate) para o cenario F2-S, usando janela
que ISOLA a fase de carga sustentada (hold), ancorada em eventos CloudTrail
RunTask -- NAO no mtime local do summary.json.

MOTIVO: as linhas "f2s" de analysis/fase5/fase5_fargate_recursos_novo.csv foram
geradas por estimate_round_window_from_mtime(padding_sec=600), que monta uma
janela de [mtime - 1440s, mtime + 600s] = 2040s (34 min) para rodadas que estao
apenas ~900s (15 min) umas das outras. As janelas de rodadas consecutivas se
sobrepoem quase inteiramente e capturam o pico de arranque das tasks vizinhas.
Assinatura do defeito no CSV antigo: r2 e r3 compartilham cpu_units_max
identico (520.204...), assim como r4 e r5 (492.026...). Mesmo defeito ja
documentado para F1/F2/F3 (08-known-problems.md #18).

Ancoragem (mesma tecnica de fase5_recursos_fase_isolada.py):
  - RunTask (relogio AWS, o mesmo das metricas do CloudWatch).
  - Coleta de 10/08/2026: ha DOIS blocos de RunTask nesse dia. O bloco valido
    e o segundo (10:11Z-15:46Z), confirmado por casar com os mtimes dos
    summary.json em disco (gap RunTask->mtime ~830-885s para as 15 rodadas).
  - O mtime local NAO entra no calculo da janela (relogio local do autor esta
    dessincronizado, NTP off). Serve so para atribuir rodada -> arquivo, o que
    e inequivoco: 5 rodadas por runtime, em ordem cronologica.

Desenho da rodada (04-experiments.md, recoleta 10/08 sob desenho novo):
  ramp-up 30s -> hold 780s -> ramp-down 30s = 840s de k6.
  Taxa 8 req/s constante, 100% GET /orders/summary, tabela orders com 50.000
  linhas (TRUNCATE+repopulate antes de cada rodada, 08-known-problems.md #1).

  k6_start = RunTask + PRE_K6[runtime]   (provisionamento Fargate + boot +
             health-check + truncate + setup do k6)
  hold     = [k6_start + 30, k6_start + 810]

PRE_K6 vem da calibracao ja usada para F2/F3 (fase5_recursos_fase_isolada.py),
derivada da assinatura de CPU da re-coleta do F1. Incerteza declarada ~+/-40s.
A selecao de datapoints e propositalmente ROBUSTA a essa incerteza: so entram
buckets de 5 min INTEIRAMENTE contidos no hold, e o script verifica que
PRE_K6 +/- 40s nao muda o conjunto selecionado (coluna 'estavel_pre_k6').

RETENCAO: period=60 (1 min) JA EXPIROU para 10/08 (retencao de 15 dias;
verificado: 0 datapoints). Unico disponivel e period=300 (5 min, retencao 63
dias) -> ~2 datapoints por rodada. MARGINAL por rodada, mas 10 datapoints por
runtime no agregado.

Saida: analysis/fase5/fase5_f2s_recursos.csv (schema identico a
fase5_fargate_recursos_novo.csv). NAO sobrescreve nenhum CSV existente.
"""
import os, json, datetime as dt
import numpy as np
import pandas as pd
import boto3

SESSION = boto3.Session(profile_name="pessoal", region_name="us-east-1")
CW = SESSION.client("cloudwatch")
CT = SESSION.client("cloudtrail")

CLUSTER = "order-service-cluster"
CPU_UNITS = 1024
MEM_MB = 2048
FAMILY = {"springboot": "order-service-springboot",
          "quarkus-jvm": "order-service-quarkus-jvm",
          "quarkus-native": "order-service-quarkus-native"}

# Atraso RunTask -> inicio da carga do k6 (provisionamento Fargate: ENI +
# image pull, depois boot + health-check + TRUNCATE/repopulate + setup do k6).
#
# RECALIBRADO para esta coleta -- NAO reaproveita o PRE_K6 de julho de
# fase5_recursos_fase_isolada.py ({springboot:105, jvm:55, native:50}), que e
# incompativel com a cadencia observada em 10/08: as rodadas sao encadeadas com
# RunTask a cada 902-956s, e o k6 sozinho ja ocupa 840s. Logo
# PRE_K6 + teardown = 62..116s (mediana ~74s), o que exclui PRE_K6=105s para o
# springboot -- com esse valor a task seguinte seria lancada ANTES do fim do k6
# desta rodada, o que nao acontece.
#
# O termo dominante e o provisionamento do Fargate (~40-60s), que independe do
# runtime; o boot em si (~1s no native, ~10-30s na JVM) e secundario. Por isso
# um unico valor para os tres, com banda de incerteza larga. A analise de
# sensibilidade (PRE_K6 de 0 a 105s, ver docstring) move a CPU media em menos de
# 1.2 p.p. em qualquer runtime.
PRE_K6 = {"springboot": 60, "quarkus-jvm": 60, "quarkus-native": 60}
PRE_K6_UNCERTAINTY = 40

# Guarda anti-arranque: descarta qualquer bucket que encoste na janela de boot
# da propria task. Com period=300 o pico de arranque vaza para o bucket seguinte
# quando o RunTask cai perto do fim de um bucket (caso do quarkus-jvm, cujos 5
# RunTask caem nos ultimos ~40s do bucket). Independe de PRE_K6.
BOOT_GUARD_BEFORE = 30
BOOT_GUARD_AFTER = 180

RAMP_UP, HOLD, RAMP_DOWN = 30, 780, 30
PERIOD = 300

REPO = os.path.expanduser("~/Programming/ecommerce-tcc")
OUT = os.path.join(REPO, "analysis/fase5/fase5_f2s_recursos.csv")

# Bloco valido da coleta de 10/08 (o segundo do dia). Ver docstring.
BLOCK_START = dt.datetime(2026, 8, 10, 9, 0, tzinfo=dt.timezone.utc)
BLOCK_END = dt.datetime(2026, 8, 10, 17, 0, tzinfo=dt.timezone.utc)


def fetch_runtasks():
    """Eventos RunTask do dia 10/08, por familia de task definition."""
    paginator = CT.get_paginator("lookup_events")
    events = []
    for page in paginator.paginate(
            LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "RunTask"}],
            StartTime=dt.datetime(2026, 8, 10, tzinfo=dt.timezone.utc),
            EndTime=dt.datetime(2026, 8, 11, tzinfo=dt.timezone.utc)):
        for e in page["Events"]:
            ce = json.loads(e["CloudTrailEvent"])
            td = (ce.get("requestParameters") or {}).get("taskDefinition", "")
            t = dt.datetime.strptime(ce["eventTime"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
            events.append((t, td.split(":")[0], ce.get("errorCode", "")))
    events.sort()
    by_rt = {}
    for t, fam, err in events:
        if err or not (BLOCK_START <= t <= BLOCK_END):
            continue
        for rt, f in FAMILY.items():
            if fam == f:
                by_rt.setdefault(rt, []).append(t)
    return by_rt


def fetch(metric, family, start, end):
    resp = CW.get_metric_statistics(
        Namespace="ECS/ContainerInsights", MetricName=metric,
        Dimensions=[{"Name": "ClusterName", "Value": CLUSTER},
                    {"Name": "TaskDefinitionFamily", "Value": family}],
        StartTime=start, EndTime=end, Period=PERIOD,
        Statistics=["Average", "Maximum"])
    return sorted(resp["Datapoints"], key=lambda d: d["Timestamp"])


def buckets_inside(points, w_start, w_end):
    """So buckets de 5 min INTEIRAMENTE dentro de [w_start, w_end].
    Regra conservadora: nenhum segundo de metrica vem de fora do hold."""
    return [p for p in points
            if p["Timestamp"] >= w_start
            and p["Timestamp"] + dt.timedelta(seconds=PERIOD) <= w_end]


def _drop_boot(points, run_task):
    """Remove buckets que se sobrepoem a [RunTask-30, RunTask+180]."""
    g0 = run_task - dt.timedelta(seconds=BOOT_GUARD_BEFORE)
    g1 = run_task + dt.timedelta(seconds=BOOT_GUARD_AFTER)
    return [p for p in points
            if not (p["Timestamp"] < g1 and p["Timestamp"] + dt.timedelta(seconds=PERIOD) > g0)]


def buckets_centered(points, w_start, w_end):
    """Buckets de 5 min cujo CENTRO cai dentro de [w_start, w_end].

    O hold tem 780s = 2.6 buckets de 300s, entao a regra estrita
    (buckets_inside) rende 1 ou 2 datapoints conforme o alinhamento do
    RunTask com a grade de 5 min do CloudWatch -- o n varia por acidente de
    fase, nao por diferenca real entre rodadas. A regra por centro rende 2-3
    datapoints de forma estavel, ao custo de deixar cada bucket de borda
    invadir ate 150s fora do hold.

    Esse vazamento e seguro aqui: o unico transiente que contamina a metrica
    e o pico de arranque da task, e a task seguinte so e lancada ~910s depois
    do RunTask desta rodada (ramp-down + teardown + provisionamento), com o
    pico de CPU de boot ainda ~PRE_K6 segundos depois disso -- bem alem do
    alcance de um bucket centrado antes do fim do hold. Do lado esquerdo, o
    boot DESTA task e anterior a w_start por PRE_K6 + 30s de ramp-up.
    Reportada como variante para conferencia contra a regra estrita."""
    half = dt.timedelta(seconds=PERIOD / 2)
    return [p for p in points if w_start <= p["Timestamp"] + half <= w_end]


def hold_window(run_task, runtime, pre_k6_delta=0):
    k6_start = run_task + dt.timedelta(seconds=PRE_K6[runtime] + pre_k6_delta)
    return (k6_start + dt.timedelta(seconds=RAMP_UP),
            k6_start + dt.timedelta(seconds=RAMP_UP + HOLD))


def main():
    by_rt = fetch_runtasks()
    rows = []
    for runtime, family in FAMILY.items():
        starts = by_rt.get(runtime, [])
        print(f"\n{runtime}: {len(starts)} RunTask no bloco valido")
        if len(starts) != 5:
            print(f"  [AVISO] esperava 5 rodadas, achei {len(starts)}")
        for i, rt_time in enumerate(starts, start=1):
            w_start, w_end = hold_window(rt_time, runtime)
            # busca com folga, recorta depois
            pts_cpu = fetch("CpuUtilized", family,
                            rt_time - dt.timedelta(seconds=600),
                            rt_time + dt.timedelta(seconds=1500))
            pts_mem = fetch("MemoryUtilized", family,
                            rt_time - dt.timedelta(seconds=600),
                            rt_time + dt.timedelta(seconds=1500))
            cpu = _drop_boot(buckets_inside(pts_cpu, w_start, w_end), rt_time)
            mem = _drop_boot(buckets_inside(pts_mem, w_start, w_end), rt_time)

            # robustez a incerteza de PRE_K6
            sel = {p["Timestamp"] for p in cpu}
            estavel = True
            for delta in (-PRE_K6_UNCERTAINTY, +PRE_K6_UNCERTAINTY):
                a, b = hold_window(rt_time, runtime, delta)
                if {p["Timestamp"] for p in _drop_boot(buckets_inside(pts_cpu, a, b), rt_time)} != sel:
                    estavel = False

            if not cpu and not mem:
                print(f"  [AVISO] r{i}: sem datapoints na janela de hold")
                continue
            for label, c, m in (("f2s", cpu, mem),):
                if not c:
                    continue
                ca = [d["Average"] for d in c]; cm = [d["Maximum"] for d in c]
                ma = [d["Average"] for d in m]; mm = [d["Maximum"] for d in m]
                rows.append({
                    "cenario": label, "runtime": runtime, "round": i,
                    "n_datapoints_cpu": len(c),
                    "cpu_units_mean": np.mean(ca), "cpu_units_max": np.max(cm),
                    "cpu_pct_mean": np.mean(ca) / CPU_UNITS * 100,
                    "cpu_pct_max": np.max(cm) / CPU_UNITS * 100,
                    "mem_mb_mean": np.mean(ma), "mem_mb_max": np.max(mm),
                    "mem_pct_mean": np.mean(ma) / MEM_MB * 100,
                    "mem_pct_max": np.max(mm) / MEM_MB * 100,
                    "run_task_utc": rt_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "hold_start_utc": w_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "hold_end_utc": w_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "period_sec": PERIOD,
                    "estavel_pre_k6": estavel if label == "f2s" else "",
                })
            e = rows[-1]
            print(f"  r{i} RunTask={rt_time:%H:%M:%SZ} hold=[{w_start:%H:%M:%S},{w_end:%H:%M:%S}] "
                  f"n={len(cpu)} CPU avg={e['cpu_pct_mean']:.2f}% max={e['cpu_pct_max']:.2f}% "
                  f"MEM avg={e['mem_mb_mean']:.0f}MB max={e['mem_mb_max']:.0f}MB "
                  f"estavel={estavel}")
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\n-> {OUT} ({len(df)} linhas)")
    return df


if __name__ == "__main__":
    main()
