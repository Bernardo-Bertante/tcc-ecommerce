#!/usr/bin/env python3
"""Item 2: planos reais do auto_explain (amostra de 2 %), por operacao e condicao.
Baixa os logs do RDS (se ainda nao baixados), remonta os JSON, recorta pela janela de cada rodada.
Exploratorio, fora do desenho oficial. Uso: 02_planos.py [dados] [resultados]
"""
import csv, gzip, json, re, sys, collections, statistics as st
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extrai_planos as ep
from compara import classifica

base = Path(sys.argv[1] if len(sys.argv) > 1 else "dados")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "resultados"); out.mkdir(exist_ok=True)
ep.INSTANCE = "pgss-res-postgres"
COND = {"springboot-noval": "SB-noval", "quarkus-jvm": "QJ"}

jan = {}
for d in sorted(base.glob("r*-*")):
    if (d / "meta.json").exists():
        m = json.loads((d / "meta.json").read_text()); jan[d.name] = (m["epoch_inicio"], m["epoch_fim"])
logdir = base / "logs_brutos"
if not list(logdir.glob("*.gz")):
    import boto3
    rds = boto3.Session(profile_name="pessoal", region_name="us-east-1").client("rds")
    ep.baixa_logs(rds, logdir, min(v[0] for v in jan.values()))
arqs = sorted(logdir.glob("*.gz"))

def walk(n, prof, acc):
    acc.append((prof, n))
    for c in n.get("Plans", []) or []: walk(c, prof + 1, acc)
    return acc

def assinatura(plano):
    partes = []
    for prof, n in walk(plano["Plan"], 0, []):
        t = n["Node Type"]
        if n.get("Relation Name"): t += f"[{n['Relation Name']}" + (f"/{n['Index Name']}" if n.get("Index Name") else "") + "]"
        partes.append("  " * prof + t)
    return " > ".join(p.strip() for p in partes)

amostras = []
for epoch, dur, pl in ep.le_planos(arqs):
    rot = next((k for k, (a, b) in jan.items() if a <= epoch <= b), None)
    if not rot or "Plan" not in pl: continue
    q = " ".join((pl.get("Query Text") or "").split())
    nos = walk(pl["Plan"], 0, [])
    raiz = pl["Plan"]
    scans = [n for _, n in nos if "Scan" in n["Node Type"]]
    amostras.append(dict(
        rodada=rot, cond=COND[rot.split("-", 1)[1]], op=classifica(q), q=q, dur=dur,
        sig=assinatura(pl), hit=raiz.get("Shared Hit Blocks", 0), read=raiz.get("Shared Read Blocks", 0),
        rows_real=raiz.get("Actual Rows", 0) * raiz.get("Actual Loops", 1), nos=[n for _, n in nos],
        scans=scans, epoch=epoch))
print(len(amostras), "amostras")

with (out / "planos_amostras.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["rodada", "cond", "op", "dur_ms", "blocos_raiz", "assinatura", "texto"])
    for a in amostras:
        w.writerow([a["rodada"], a["cond"], a["op"], a["dur"], a["hit"] + a["read"], a["sig"], a["q"][:300]])

L = []
# 1) assinaturas de plano por operacao/texto e condicao
L.append("# Planos por operacao e texto de consulta (assinatura = tipos de no + relacao/indice)\n")
por = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for a in amostras:
    por[(a["op"], a["q"][:120])][a["cond"]][a["sig"]] += 1
for (op, q), d in sorted(por.items()):
    if op.startswith("infra_"): continue
    L.append(f"\n## {op}: `{q}`")
    for cond in ("SB-noval", "QJ"):
        n = sum(d[cond].values())
        L.append(f"- {cond}: {n} amostras")
        for s, c in d[cond].most_common(6): L.append(f"    - {c:>4} x {s}")

# 2) estimado x real e blocos por linha nos nos de scan
L.append("\n\n# Nos de scan: estimativa x real e blocos por linha (mediana por amostra; nos com >= 200 linhas reais)\n")
L.append(f"{'op':24} {'cond':9} {'no':22} {'n':>5} {'lin_real_med':>12} {'est/real_med':>12} {'blk/linha_med':>13} {'heapfetch/lin':>13}")
g = collections.defaultdict(list)
for a in amostras:
    for n in a["scans"]:
        real = (n.get("Actual Rows") or 0) * (n.get("Actual Loops") or 1)
        blk = (n.get("Shared Hit Blocks") or 0) + (n.get("Shared Read Blocks") or 0)
        if real < 200: continue
        g[(a["op"], a["cond"], n["Node Type"] + "/" + (n.get("Relation Name") or ""))].append(
            (real, (n.get("Plan Rows") or 0) / real, blk / real, (n.get("Heap Fetches") or 0) / real if "Heap Fetches" in n else None))
for k in sorted(g):
    v = g[k]
    hf = [x[3] for x in v if x[3] is not None]
    L.append(f"{k[0]:24} {k[1]:9} {k[2]:22} {len(v):5d} {st.median(x[0] for x in v):12.0f} {st.median(x[1] for x in v):12.2f} "
             f"{st.median(x[2] for x in v):13.3f} {(st.median(hf) if hf else float('nan')):13.3f}")

# 3) blocos e duracao por chamada, no raiz, por operacao (para as operacoes de 1 statement)
L.append("\n\n# No raiz: blocos e duracao por amostra, por operacao (mediana)\n")
L.append(f"{'op':24} {'cond':9} {'n':>5} {'blocos_med':>10} {'dur_ms_med':>10}")
h = collections.defaultdict(list)
for a in amostras: h[(a["op"], a["cond"])].append(a)
for k in sorted(h):
    if k[0].startswith("infra_"): continue
    v = h[k]; L.append(f"{k[0]:24} {k[1]:9} {len(v):5d} {st.median(a['hit'] + a['read'] for a in v):10.1f} {st.median(a['dur'] for a in v):10.3f}")
(out / "planos_resumo.md").write_text("\n".join(L) + "\n"); print("\n".join(L[-40:]))
