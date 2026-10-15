#!/usr/bin/env python3
"""Análise do -XX:+PrintCompilation de uma rodada (EXPLORATÓRIO, fora do desenho oficial do TCC).

Uso: analisa_jit.py <dir_rodada> <arquivo_summary_path> <dir_saida_csv>

<dir_rodada> precisa ter:
  logs.jsonl.gz     uma linha JSON por evento do CloudWatch: {"t": epoch_ms, "m": "mensagem"}
  meta.json         runtime, cenario, carga_inicio_ms, carga_fim_ms (1ª e última requisição do k6)
  requests.csv.gz   (opcional) uma linha por requisição do k6: epoch_ms, duracao_ms, phase, operation, ...
  codelist.txt      (opcional) saída bruta de `jcmd 1 Compiler.codelist`

Acrescenta (append) uma rodada a nivel_por_rodada.csv, curva_nivel4.csv, summary_path_nivel.csv,
deopt.csv e integridade.csv em <dir_saida_csv>. Só usa a biblioteca padrão (roda no runner).

Formato da linha do PrintCompilation no JDK 21 (CompileTask::print):
  <uptime_ms> <compile_id> <5 flags: % s ! b n> <nível> <Classe::método> [@ bci] (<N> bytes|native) [mensagem]
Mensagens tratadas: "made not entrant" (deoptimização da nmethod daquele id) e "COMPILE SKIPPED"
(compilação abortada: o id não gera nmethod viva).
"""
import csv, fnmatch, gzip, json, os, re, statistics, sys
from collections import Counter, defaultdict

LINHA = re.compile(
    r"^\s*(?P<up>\d+)\s+(?P<id>\d+)\s(?P<flags>[ %][ s][ !][ b][ n])\s+(?P<nivel>[0-4])\s+"
    r"(?P<metodo>\S+::\S+)(?:\s+@\s+(?P<bci>\d+))?\s+\((?:(?P<bytes>\d+) bytes|native)\)(?P<resto>.*)$")
# linha "órfã": o log da app foi escrito entre o uptime e o resto da linha (PrintCompilation faz vários write());
# id/flags/nível/método íntegros, uptime perdido -> estimado pelo timestamp do evento no CloudWatch.
ORFA = re.compile(
    r"^\s*(?P<id>\d+)\s(?P<flags>[ %][ s][ !][ b][ n])\s+(?P<nivel>[0-4])\s+"
    r"(?P<metodo>\S+::\S+)(?:\s+@\s+(?P<bci>\d+))?\s+\((?:(?P<bytes>\d+) bytes|native)\)(?P<resto>.*)$")
LOG_APP = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")   # início de uma linha de log da app (SB e Quarkus)
CANDIDATA = re.compile(r"^\s*\d+\s+\d+\s")          # começa como linha de compilação
CODELIST = re.compile(r"^(?P<id>\d+) (?P<nivel>-?\d+) (?P<estado>\d+) (?P<metodo>\S+)")
FIM_SO_NO_FIM = 0.80   # 1º nível 4 depois de 80% da janela de carga => "atingiu só no fim"


def ler_eventos(caminho):
    with gzip.open(caminho, "rt") as f:
        for linha in f:
            o = json.loads(linha)
            yield int(o["t"]), o["m"]


def carregar_padroes(caminho):
    padroes = []
    with open(caminho) as f:
        for linha in f:
            if not linha.strip() or linha.startswith("#"):
                continue
            c = linha.rstrip("\n").split("\t")
            c += [""] * (5 - len(c))
            padroes.append({"padrao": c[0], "camada": c[1], "certeza": c[2], "exclusivo": c[3], "nota": c[4]})
    return padroes


def anexar(caminho, cabecalho, linhas):
    novo = not os.path.exists(caminho)
    with open(caminho, "a", newline="") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(cabecalho)
        w.writerows(linhas)


def seg(ms):
    return None if ms is None else round(ms / 1000.0, 1)


def main(dir_rodada, arq_padroes, dir_saida):
    meta = json.load(open(os.path.join(dir_rodada, "meta.json")))
    rt, cen = meta["runtime"], meta["cenario"]
    c0, c1 = int(meta["carga_inicio_ms"]), int(meta["carga_fim_ms"])
    padroes = carregar_padroes(arq_padroes)

    comp = []            # (uptime, id, flags, nivel, metodo, osr, evento_ms)
    deopt = []           # (uptime, id, nivel, metodo, osr)
    skipped = set()
    n_eventos = n_candidatas = n_nao_parseadas = 0
    exemplos_nao_parseadas = []
    n_orfas = n_recombinadas = 0
    n_jvm = 0   # linhas "INFO exec -a" do run-java.sh: mais de uma = a JVM reiniciou no mesmo log
    pendente = None   # prefixo de linha de compilação cortada por uma linha do log da app
    for t, m in ler_eventos(os.path.join(dir_rodada, "logs.jsonl.gz")):
        n_eventos += 1
        if m.startswith("INFO exec -a"):
            n_jvm += 1
        r = None
        if pendente is not None:
            # o resto da linha cortada chega no evento seguinte ao log da app: prefixo + evento
            r = LINHA.match(pendente + m)
            if r:
                n_recombinadas += 1
            else:
                n_nao_parseadas += 1
                if len(exemplos_nao_parseadas) < 5:
                    exemplos_nao_parseadas.append(pendente[:160])
            pendente = None
        if r is None:
            if not CANDIDATA.match(m):
                continue
            n_candidatas += 1
            r = LINHA.match(m)
        if r:
            up = int(r["up"])
        else:
            r = ORFA.match(m)
            if not r:
                corte = LOG_APP.search(m)
                if corte and corte.start() > 0:
                    pendente = m[:corte.start()]
                    continue
                n_nao_parseadas += 1
                if len(exemplos_nao_parseadas) < 5:
                    exemplos_nao_parseadas.append(m[:160])
                continue
            up = None
            n_orfas += 1
        cid, fl, nv, met = int(r["id"]), r["flags"], int(r["nivel"]), r["metodo"]
        osr = fl[0] == "%"
        resto = r["resto"]
        if "made not entrant" in resto:
            deopt.append((up, cid, nv, met, osr, t))
        elif "COMPILE SKIPPED" in resto:
            skipped.add(cid)
        elif "made zombie" in resto:
            pass
        else:
            comp.append((up, cid, fl, nv, met, osr, t))

    if not comp:
        print(f"{rt}/{cen}: nenhuma linha de compilação", file=sys.stderr)
        sys.exit(2)

    # relógio: início da JVM (epoch) = mediana de (timestamp do evento no CloudWatch - uptime)
    difs = sorted(t - up for up, _, _, _, _, _, t in comp if up is not None)
    jvm0 = statistics.median(difs)
    p05, p95 = difs[int(0.05 * (len(difs) - 1))], difs[int(0.95 * (len(difs) - 1))]
    comp = [(c[0] if c[0] is not None else int(c[6] - jvm0),) + c[1:] for c in comp]
    deopt = [(d[0] if d[0] is not None else int(d[5] - jvm0),) + d[1:5] for d in deopt]
    ep = lambda up: jvm0 + up             # uptime -> epoch ms
    rel = lambda up: ep(up) - c0          # uptime -> ms desde o início da carga

    # chamadas ao summary no tempo (para "quantas chamadas até o 1º nível 4")
    summary_ts = []
    req = os.path.join(dir_rodada, "requests.csv.gz")
    if os.path.exists(req):
        with gzip.open(req, "rt") as f:
            for row in csv.DictReader(f):
                if row["operation"] == "get_summary" and row["phase"] != "setup":
                    summary_ts.append(int(row["epoch_ms"]))
        summary_ts.sort()
    import bisect
    n_summary_ate = lambda ms_epoch: bisect.bisect_right(summary_ts, ms_epoch) if summary_ts else None

    # integridade: lacunas de id
    ids = sorted({c[1] for c in comp} | skipped | {d[1] for d in deopt})
    lacunas = [(a, b) for a, b in zip(ids, ids[1:]) if b - a > 1]
    ids_faltando = sum(b - a - 1 for a, b in lacunas)
    maior_lacuna = max((b - a - 1 for a, b in lacunas), default=0)

    # estado ao fim da carga: réplica dos eventos até carga_fim (por uptime)
    up_fim = c1 - jvm0
    vivos = {}   # id -> (metodo, nivel, osr, native)
    eventos = [(c[0], 0, c) for c in comp] + [(d[0], 1, d) for d in deopt]
    eventos.sort(key=lambda e: (e[0], e[1]))
    for up, tipo, e in eventos:
        if up > up_fim:
            break
        if tipo == 0:
            _, cid, fl, nv, met, osr, _ = e
            if cid not in skipped:
                vivos[cid] = (met, nv, osr, fl[4] == "n")
        else:
            vivos.pop(e[1], None)
    final_metodo = {}   # método (não-OSR, não-native) -> maior nível vivo
    osr_vivos = Counter()
    for met, nv, osr, nat in vivos.values():
        if nat:
            continue
        if osr:
            osr_vivos[nv] += 1
        else:
            final_metodo[met] = max(final_metodo.get(met, 0), nv)
    por_nivel_final = Counter(final_metodo.values())

    # compilações por nível (toda a vida da JVM até o fim da carga), separando OSR e native
    cnt = Counter()
    for up, cid, fl, nv, met, osr, _ in comp:
        if up <= up_fim and fl[4] != "n":
            cnt[(nv, osr)] += 1
    l4 = sorted(up for up, cid, fl, nv, met, osr, _ in comp if nv == 4 and not osr and fl[4] != "n" and cid not in skipped)
    l4_ate_fim = [u for u in l4 if u <= up_fim]
    l4_antes_carga = sum(1 for u in l4 if rel(u) < 0)
    metodos_l4 = {met for up, cid, fl, nv, met, osr, _ in comp if nv == 4 and not osr and up <= up_fim and cid not in skipped}
    kth = lambda k: seg(rel(l4_ate_fim[k - 1])) if len(l4_ate_fim) >= k else None

    # codelist (jcmd) — conferência cruzada
    cl_total = cl_vivos = cl_faltando_no_log = None
    cl_por_nivel = Counter()
    cl_path = os.path.join(dir_rodada, "codelist.txt")
    ids_log = {c[1] for c in comp}
    log_vivos_fim = {}
    for up, tipo, e in eventos:   # vivos ao fim de TODO o log (o jcmd roda depois do fim da carga)
        if tipo == 0:
            if e[1] not in skipped:
                log_vivos_fim[e[1]] = e
        else:
            log_vivos_fim.pop(e[1], None)
    if os.path.exists(cl_path) and os.path.getsize(cl_path) > 0:
        cl_total = cl_vivos = cl_faltando_no_log = 0
        cl_metodo = {}
        faltando_ex = []
        for linha in open(cl_path, errors="replace"):
            r = CODELIST.match(linha.strip())
            if not r:
                continue
            cid, nv, est = int(r["id"]), int(r["nivel"]), int(r["estado"])
            cl_total += 1
            if cid not in ids_log:
                cl_faltando_no_log += 1
                if len(faltando_ex) < 5:
                    faltando_ex.append(linha.strip()[:120])
            if est == 0:
                cl_vivos += 1
                nome = r["metodo"].split("(")[0]
                if nv > 0:   # nível 0 = wrapper nativo
                    cl_metodo[nome] = max(cl_metodo.get(nome, 0), nv)
        cl_por_nivel = Counter(cl_metodo.values())
        if faltando_ex:
            print(f"  codelist: ids ausentes no log, ex.: {faltando_ex}", file=sys.stderr)

    # --- nivel_por_rodada.csv
    anexar(os.path.join(dir_saida, "nivel_por_rodada.csv"),
           ["runtime", "cenario", "carga_s", "metodos_fim_nivel1", "metodos_fim_nivel2", "metodos_fim_nivel3",
            "metodos_fim_nivel4", "osr_vivas_fim_nivel3", "osr_vivas_fim_nivel4",
            "compilacoes_n1", "compilacoes_n2", "compilacoes_n3", "compilacoes_n4",
            "compilacoes_osr_n3", "compilacoes_osr_n4", "metodos_distintos_que_atingiram_n4",
            "n4_antes_da_carga", "t_100o_n4_s", "t_1000o_n4_s", "t_ultimo_n4_s",
            "jcmd_metodos_nivel1", "jcmd_metodos_nivel2", "jcmd_metodos_nivel3", "jcmd_metodos_nivel4"],
           [[rt, cen, seg(c1 - c0), por_nivel_final[1], por_nivel_final[2], por_nivel_final[3], por_nivel_final[4],
             osr_vivos[3], osr_vivos[4], cnt[(1, False)], cnt[(2, False)], cnt[(3, False)], cnt[(4, False)],
             cnt[(3, True)], cnt[(4, True)], len(metodos_l4), l4_antes_carga, kth(100), kth(1000),
             seg(rel(l4_ate_fim[-1])) if l4_ate_fim else None,
             *( [cl_por_nivel[k] for k in (1, 2, 3, 4)] if cl_total is not None else [None] * 4 )]])

    # --- curva_nivel4.csv: acumulado de compilações n4 (não-OSR) por minuto desde o início da carga
    dur_min = int((c1 - c0) // 60000) + 1
    linhas = []
    for mnt in range(0, dur_min + 1):
        lim = mnt * 60000
        acum = sum(1 for u in l4 if rel(u) <= lim)
        acum_osr = sum(1 for up, cid, fl, nv, met, osr, _ in comp if nv == 4 and osr and rel(up) <= lim)
        met_ac = len({met for up, cid, fl, nv, met, osr, _ in comp if nv == 4 and not osr and rel(up) <= lim and cid not in skipped})
        linhas.append([rt, cen, mnt, acum, acum_osr, met_ac, n_summary_ate(c0 + lim)])
    anexar(os.path.join(dir_saida, "curva_nivel4.csv"),
           ["runtime", "cenario", "minuto_desde_inicio_carga", "compilacoes_n4_acum", "compilacoes_osr_n4_acum",
            "metodos_distintos_n4_acum", "chamadas_summary_acum"], linhas)

    # --- summary_path_nivel.csv
    todos_metodos = sorted({c[4] for c in comp})
    por_metodo = defaultdict(list)
    for c in comp:
        por_metodo[c[4]].append(c)
    deopt_metodo = Counter(d[3] for d in deopt if d[0] <= up_fim)
    linhas = []
    janela = c1 - c0
    for p in padroes:
        casados = [m for m in todos_metodos if fnmatch.fnmatchcase(m, p["padrao"])]
        if not casados:
            linhas.append([rt, cen, p["padrao"], "", p["camada"], p["certeza"], p["exclusivo"], "", 0, "", "", "",
                           0, "nao compilado (so interpretado ou nao executado)"])
            continue
        for met in casados:
            cs = [c for c in por_metodo[met] if c[0] <= up_fim and c[1] not in skipped]
            nmax = max((c[3] for c in cs if not c[5]), default=0)
            p4 = min((c[0] for c in cs if c[3] == 4 and not c[5]), default=None)
            t4 = rel(p4) if p4 is not None else None
            if t4 is None:
                leitura = "nao atingiu"
            elif t4 > FIM_SO_NO_FIM * janela:
                leitura = "atingiu so no fim"
            elif t4 < 0:
                leitura = "atingiu antes da carga"
            else:
                leitura = "atingiu"
            linhas.append([rt, cen, p["padrao"], met, p["camada"], p["certeza"], p["exclusivo"], nmax, len(cs),
                           seg(t4), n_summary_ate(ep(p4)) if p4 is not None else "",
                           final_metodo.get(met, 0), deopt_metodo[met], leitura])
    anexar(os.path.join(dir_saida, "summary_path_nivel.csv"),
           ["runtime", "cenario", "padrao", "metodo", "camada", "certeza", "exclusivo", "nivel_max",
            "n_compilacoes", "t_primeiro_n4_s", "chamadas_summary_ate_n4", "nivel_vivo_fim_carga", "deopt",
            "leitura"], linhas)

    # --- deopt.csv
    casa_path = lambda met: any(fnmatch.fnmatchcase(met, p["padrao"]) for p in padroes)
    d_fim = [d for d in deopt if d[0] <= up_fim]
    d_carga = [d for d in d_fim if rel(d[0]) >= 0]
    nv_d = Counter(d[2] for d in d_fim)
    anexar(os.path.join(dir_saida, "deopt.csv"),
           ["runtime", "cenario", "made_not_entrant_total", "durante_carga", "de_nivel4", "de_nivel3",
            "de_nivel2", "de_nivel1", "caminho_summary_total", "caminho_summary_durante_carga"],
           [[rt, cen, len(d_fim), len(d_carga), nv_d[4], nv_d[3], nv_d[2], nv_d[1],
             sum(1 for d in d_fim if casa_path(d[3])), sum(1 for d in d_carga if casa_path(d[3]))]])

    # --- integridade.csv
    anexar(os.path.join(dir_saida, "integridade.csv"),
           ["runtime", "cenario", "eventos_log", "linhas_candidatas", "linhas_nao_parseadas", "compilacoes",
            "deopt_linhas", "skipped", "id_min", "id_max", "ids_faltando", "maior_lacuna",
            "jvm_inicio_epoch_ms", "relogio_spread_p05_p95_ms", "carga_inicio_ms", "carga_fim_ms",
            "codelist_entradas", "codelist_vivas", "codelist_ids_ausentes_no_log", "chamadas_summary", "jvms_no_log",
            "linhas_orfas_recuperadas", "linhas_recombinadas"],
           [[rt, cen, n_eventos, n_candidatas, n_nao_parseadas, len(comp), len(deopt), len(skipped),
             ids[0], ids[-1], ids_faltando, maior_lacuna, int(jvm0), int(p95 - p05), c0, c1,
             cl_total, cl_vivos, cl_faltando_no_log, len(summary_ts) if summary_ts else None, n_jvm, n_orfas, n_recombinadas]])

    print(f"{rt}/{cen}: {len(comp)} compilações, n4 ao fim={por_nivel_final[4]} métodos "
          f"(jcmd={cl_por_nivel[4] if cl_total is not None else '-'}), deopt={len(d_fim)}, "
          f"ids faltando={ids_faltando} (maior lacuna {maior_lacuna}), não parseadas={n_nao_parseadas}, órfãs recuperadas={n_orfas}, recombinadas={n_recombinadas}, "
          f"codelist ausentes no log={cl_faltando_no_log}, JVMs no log={n_jvm}")
    if exemplos_nao_parseadas:
        print("  exemplos não parseados:", exemplos_nao_parseadas, file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
