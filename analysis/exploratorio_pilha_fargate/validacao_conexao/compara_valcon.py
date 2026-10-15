#!/usr/bin/env python3
"""
Comparacao do perfil de CPU do Spring Boot COM e SEM validation-query, sob 1 vCPU.

Condicoes:
  sbval  : Spring Boot com validacao (reconfirmacao 1 vCPU de 20/09, ../results_1vcpu/sb-r{1,2})
  sbanc  : Spring Boot com validacao, ancora do mesmo dia deste teste (results/sbval-a1)
  sbnv   : Spring Boot SEM validacao (results/sbnv-r{1,2,3})
  qj     : Quarkus JVM, controle reaproveitado (../results_1vcpu/qj-r{1,2})

Categorias self-time: as MESMAS do ../analyze.py (importado, nao copiado).
Subsistemas inclusivos: padroes recalibrados contra os valores publicados na secao de
reconfirmacao do NOTAS (reproduzem exatamente 0,01757 / 0,00814 / 0,00683 / 0,00504 vCPU
nos .collapsed de 20/09; ver secao "Calibracao" na saida).
"""
import gzip
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import analyze as A  # noqa: E402

MS, WIN = 0.010, A.WINDOW_S  # 1 amostra ctimer = 10 ms; janela de 360 s
R1V = PARENT / "results_1vcpu"
R8 = PARENT / "results"
RES = HERE / "results"

COND = {
    "sbval": [R1V / "sb-r1", R1V / "sb-r2"],
    "sbanc": [RES / "sbval-a1"],
    "sbnv": [RES / "sbnv-r1", RES / "sbnv-r2", RES / "sbnv-r3"],
    "qj": [R1V / "qj-r1", R1V / "qj-r2"],
}
LABEL = {"sbval": "SB com val. (20/09)", "sbanc": "SB com val. (âncora 24/09)",
         "sbnv": "SB sem val. (24/09)", "qj": "QJ (20/09)"}

# inclusivos (qualquer frame do stack casa)
SUBSYS = [
    ("render_sql", "Spring Data: renderização de SQL (StatementMapper)", r"StatementMapper"),
    ("excecao", "exceção: fillInStackTrace (total)", r"fillInStackTrace"),
    ("propertypath", "— PropertyPath / PropertyReferenceException", r"PropertyPath"),
    ("reactor_ctx", "Reactor: propagação de Context", r"currentContext|reactor\.util\.context"),
    ("r2dbc_pool_validation", "r2dbc-pool: Validation (lado de envio)", r"io\.r2dbc\.pool\.Validation"),
    ("r2dbc_pool", "r2dbc-pool: qualquer frame", r"io\.r2dbc\.pool\."),
]
SUBSYS_C = [(k, lbl, re.compile(p)) for k, lbl, p in SUBSYS]
SELF_FRAMES = [("itable_stub", "itable stub")]


def load_run(base: Path):
    jfr = base.with_name(base.name + ".cpu.jfr")
    col = A.convert(jfr, "cpu")
    tot, sc, _, st, sf = A.parse(col)
    inc = defaultdict(int)
    with col.open() as fh:
        for line in fh:
            stack, _, n = line.rstrip("\n").rpartition(" ")
            if not stack:
                continue
            n = int(n)
            for k, _, rx in SUBSYS_C:
                if rx.search(stack):
                    inc[k] += n
    for k, fr in SELF_FRAMES:
        inc[k] = sf.get(fr, 0)
    return dict(tot=tot, cat=sc, thr=st, inc=inc)


def cgroup_window(base: Path):
    meta = dict(kv.split("=", 1) for line in base.with_name(base.name + ".meta").read_text().split("\n")
                for kv in line.split(" ") if "=" in kv)
    k0 = float(meta["k6_start_epoch"])
    rows = [tuple(map(float, l.split()[:2])) for l in base.with_name(base.name + ".cpu.tsv").read_text().split("\n")
            if len(l.split()) >= 2]
    a = min(rows, key=lambda r: abs(r[0] - (k0 + 120)))
    b = min(rows, key=lambda r: abs(r[0] - (k0 + 480)))
    return (b[1] - a[1]) / 1e6 / (b[0] - a[0])


def k6_stats(base: Path):
    reqs = fails = 0
    durs = []
    with gzip.open(base.with_name(base.name + ".k6.csv.gz"), "rt") as fh:
        next(fh)
        for line in fh:
            m, _, v = line.split(",", 3)[:3]
            if m == "http_reqs":
                reqs += 1
            elif m == "http_req_failed":
                fails += float(v) > 0
            elif m == "http_req_duration":
                durs.append(float(v))
    durs.sort()
    q = lambda p: durs[min(len(durs) - 1, int(p * len(durs)))]
    return reqs, fails, q(0.50), q(0.95), q(0.99)


def mean(xs):
    return sum(xs) / len(xs)


def main():
    runs = {c: [load_run(b) for b in bases] for c, bases in COND.items()
            if all(b.with_name(b.name + ".cpu.jfr").exists() for b in bases)}
    missing = [c for c in COND if c not in runs]
    if missing:
        print(f"!! condicoes sem dados ainda: {missing}")

    def vcpu_cat(c, cat):
        return mean([r["cat"].get(cat, 0) * MS / WIN for r in runs[c]])

    def vcpu_tot(c):
        return mean([r["tot"] * MS / WIN for r in runs[c]])

    def vcpu_inc(c, k):
        return mean([r["inc"].get(k, 0) * MS / WIN for r in runs[c]])

    def vcpu_thr(c, t):
        return mean([r["thr"].get(t, 0) * MS / WIN for r in runs[c]])

    conds = [c for c in ("sbval", "sbanc", "sbnv", "qj") if c in runs]

    # --- 0. sanidade: carga, amostras, cgroup ---------------------------------
    print("=" * 96 + "\n0. SANIDADE POR REPETICAO (janela de profiling t+120..480 s)\n" + "=" * 96)
    print(f"{'rodada':<22}{'amostras':>9}{'vCPU prof':>11}{'vCPU cgroup':>13}"
          f"{'reqs':>8}{'falhas':>8}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}")
    for c in conds:
        for b, r in zip(COND[c], runs[c]):
            reqs, fails, p50, p95, p99 = k6_stats(b)
            print(f"{c + ':' + b.name:<22}{r['tot']:>9}{r['tot'] * MS / WIN:>11.4f}{cgroup_window(b):>13.4f}"
                  f"{reqs:>8}{fails:>8}{p50:>9.2f}{p95:>9.2f}{p99:>9.2f}")

    # --- 1. totais e gaps ----------------------------------------------------------
    print("\n" + "=" * 96 + "\n1. CPU TOTAL AMOSTRADA E GAP CONTRA QUARKUS JVM\n" + "=" * 96)
    qj = vcpu_tot("qj")
    for c in conds:
        t = vcpu_tot(c)
        extra = "" if c == "qj" else f"   gap vs QJ {t - qj:.4f} vCPU   razao {t / qj:.2f}x"
        print(f"{LABEL[c]:<28}{t:.4f} vCPU (média de {len(runs[c])}){extra}")
    if "sbnv" in runs:
        g0, g1 = vcpu_tot("sbval") - qj, vcpu_tot("sbnv") - qj
        print(f"\ngap com val. (20/09) {g0:.4f} -> sem val. {g1:.4f}: "
              f"variacao {g1 - g0:+.4f} vCPU ({100 * (g1 - g0) / g0:+.1f}% do gap original)")
        if "sbanc" in runs:
            ga = vcpu_tot("sbanc") - qj
            print(f"gap com val. (ancora 24/09) {ga:.4f} -> sem val. {g1:.4f}: "
                  f"variacao {g1 - ga:+.4f} vCPU ({100 * (g1 - ga) / ga:+.1f}%)")

    # --- 2. categorias self-time em vCPU --------------------------------------------
    print("\n" + "=" * 96 + "\n2. CATEGORIAS (self time, analyze.py) EM vCPU E % DO GAP\n" + "=" * 96)
    cats = set()
    for c in conds:
        for r in runs[c]:
            cats |= set(r["cat"])
    hdr = f"{'categoria':<18}" + "".join(f"{c:>10}" for c in conds)
    if "sbnv" in runs:
        hdr += f"{'Δ val→nv':>11}{'%gap val':>10}{'%gap nv':>10}{'Δ/Δtot':>9}"
    print(hdr)
    g0 = vcpu_tot("sbval") - qj
    g1 = vcpu_tot("sbnv") - qj if "sbnv" in runs else None
    dtot = (vcpu_tot("sbnv") - vcpu_tot("sbval")) if "sbnv" in runs else None
    rows = sorted(cats, key=lambda k: -(vcpu_cat("sbval", k) - vcpu_cat("qj", k)))
    for k in rows:
        line = f"{k:<18}" + "".join(f"{vcpu_cat(c, k):10.5f}" for c in conds)
        if "sbnv" in runs:
            d = vcpu_cat("sbnv", k) - vcpu_cat("sbval", k)
            line += (f"{d:+11.5f}{100 * (vcpu_cat('sbval', k) - vcpu_cat('qj', k)) / g0:9.1f}%"
                     f"{100 * (vcpu_cat('sbnv', k) - vcpu_cat('qj', k)) / g1:9.1f}%"
                     f"{100 * d / dtot:8.1f}%")
        print(line)
    print("  (Δ/Δtot = fatia da variacao total do SB com->sem validacao que caiu nesta categoria)")

    # --- 3. threads -------------------------------------------------------------
    print("\n" + "=" * 96 + "\n3. CPU POR GRUPO DE THREADS (vCPU)\n" + "=" * 96)
    thrs = set()
    for c in conds:
        for r in runs[c]:
            thrs |= set(r["thr"])
    print(f"{'thread':<18}" + "".join(f"{c:>10}" for c in conds))
    for t in sorted(thrs, key=lambda t: -vcpu_thr("sbval", t)):
        print(f"{t:<18}" + "".join(f"{vcpu_thr(c, t):10.5f}" for c in conds))

    # --- 4. subsistemas inclusivos ---------------------------------------------
    print("\n" + "=" * 96 + "\n4. SUBSISTEMAS (inclusivo) E FRAMES SELF, vCPU\n" + "=" * 96)
    print(f"{'subsistema':<50}" + "".join(f"{c:>10}" for c in conds) + f"{'var val→nv':>12}")
    for k, lbl, _ in SUBSYS_C:
        a = vcpu_inc("sbval", k)
        v = [vcpu_inc(c, k) for c in conds]
        var = (f"{100 * (vcpu_inc('sbnv', k) - a) / a:+11.1f}%" if "sbnv" in runs and a else "")
        print(f"{lbl:<50}" + "".join(f"{x:10.5f}" for x in v) + var)
    for k, fr in SELF_FRAMES:
        v = [vcpu_inc(c, k) for c in conds]
        p = [mean([r["inc"][k] / r["tot"] * 100 for r in runs[c]]) for c in conds]
        a = vcpu_inc("sbval", k)
        var = f"{100 * (vcpu_inc('sbnv', k) - a) / a:+11.1f}%" if "sbnv" in runs else ""
        print(f"{fr + ' (self, vCPU)':<50}" + "".join(f"{x:10.5f}" for x in v) + var)
        print(f"{fr + ' (self, % do total)':<50}" + "".join(f"{x:9.2f}%" for x in p))

    # --- 5. dispersao entre repeticoes (sbnv) --------------------------------------
    if "sbnv" in runs:
        print("\n" + "=" * 96 + "\n5. DISPERSAO ENTRE REPETICOES, vCPU (mecanismos + categorias sensiveis)\n" + "=" * 96)
        items = [("TOTAL", lambda r: r["tot"])] + \
                [(k, (lambda k: lambda r: r["cat"].get(k, 0))(k)) for k in
                 ("reativo", "despacho_virtual", "syscall_rede", "db_driver", "http_netty", "jdk_outro",
                  "nativo_vm", "orm_mapper")] + \
                [(k, (lambda k: lambda r: r["inc"].get(k, 0))(k)) for k in
                 ("render_sql", "excecao", "propertypath", "reactor_ctx", "itable_stub")]
        for c in conds:
            print(f"-- {LABEL[c]}")
            for nm, f in items:
                vals = [f(r) * MS / WIN for r in runs[c]]
                print(f"   {nm:<18}" + " ".join(f"{x:.5f}" for x in vals)
                      + (f"   (amplitude {max(vals) - min(vals):.5f})" if len(vals) > 1 else ""))

    # --- 6. agregado: 3 rodadas com validacao (20/09 + ancora) vs 3 sem ---------------
    if "sbnv" in runs and "sbanc" in runs:
        import statistics as S
        val3 = runs["sbval"] + runs["sbanc"]
        nv3 = runs["sbnv"]
        nv2 = runs["sbnv"][1:]  # sensibilidade: sem sbnv-r1
        print("\n" + "=" * 96 + "\n6. AGREGADO: COM val. (3 rodadas: 2 de 20/09 + âncora) vs SEM val. (3 rodadas)\n"
              + "=" * 96)
        print("   'share' = fração da CPU total do SB; t = Welch, n=3 vs 3 (df≈4; |t|>2,78 ~ p<0,05)")
        items = [("TOTAL", lambda r: r["tot"])] + \
                [(k, (lambda k: lambda r: r["cat"].get(k, 0))(k)) for k in
                 ("reativo", "despacho_virtual", "jdk_outro", "nativo_vm", "orm_mapper",
                  "syscall_rede", "db_driver", "http_netty", "compilador_jit")] + \
                [(k, (lambda k: lambda r: r["inc"].get(k, 0))(k)) for k in
                 ("render_sql", "excecao", "propertypath", "reactor_ctx", "itable_stub",
                  "r2dbc_pool_validation")] + \
                [("thr:event_loop_db", lambda r: r["thr"].get("event_loop_db", 0)),
                 ("thr:event_loop_http", lambda r: r["thr"].get("event_loop_http", 0))]
        print(f"{'item':<22}{'val3':>9}{'nv3':>9}{'Δ':>10}{'Δ%':>8}{'t':>7}"
              f"{'share val':>11}{'share nv':>10}{'nv2 (s/ r1)':>13}{'Δ% nv2':>8}")
        for nm, f in items:
            a = [f(r) * MS / WIN for r in val3]
            b = [f(r) * MS / WIN for r in nv3]
            c = [f(r) * MS / WIN for r in nv2]
            ma, mb, mc = mean(a), mean(b), mean(c)
            se = (S.variance(a) / len(a) + S.variance(b) / len(b)) ** 0.5
            t = (mb - ma) / se if se else float("nan")
            sa = mean([f(r) / r["tot"] for r in val3]) * 100
            sb = mean([f(r) / r["tot"] for r in nv3]) * 100
            print(f"{nm:<22}{ma:9.5f}{mb:9.5f}{mb - ma:+10.5f}{100 * (mb - ma) / ma if ma else 0:+7.1f}%"
                  f"{t:7.2f}{sa:10.2f}%{sb:9.2f}%{mc:13.5f}{100 * (mc - ma) / ma if ma else 0:+7.1f}%")
        g_a = mean([r["tot"] * MS / WIN for r in val3]) - qj
        g_b = mean([r["tot"] * MS / WIN for r in nv3]) - qj
        g_c = mean([r["tot"] * MS / WIN for r in nv2]) - qj
        print(f"\ngap vs QJ: com val. (3) {g_a:.4f} | sem val. (3) {g_b:.4f} ({100 * (g_b - g_a) / g_a:+.1f}%)"
              f" | sem val. sem r1 (2) {g_c:.4f} ({100 * (g_c - g_a) / g_a:+.1f}%)")

    # --- calibracao -------------------------------------------------------------
    print("\n" + "=" * 96 + "\nCALIBRACAO DOS PADROES INCLUSIVOS CONTRA O NOTAS (SB, 1 vCPU e 8 nucleos)\n" + "=" * 96)
    ref = {"render_sql": (0.01757, 0.01754), "excecao": (0.00814, 0.00741),
           "propertypath": (0.00683, 0.00611), "reactor_ctx": (0.00504, 0.00619)}
    r8 = [load_run(R8 / f"sb-r{i}") for i in (1, 2, 3)]
    for k, (v1, v8) in ref.items():
        m1 = vcpu_inc("sbval", k)
        m8 = mean([r["inc"].get(k, 0) * MS / WIN for r in r8])
        print(f"{k:<14} 1 vCPU: NOTAS {v1:.5f} recalc {m1:.5f}   8 nucleos: NOTAS {v8:.5f} recalc {m8:.5f}")


if __name__ == "__main__":
    main()
