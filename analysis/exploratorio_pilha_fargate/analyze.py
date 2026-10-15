#!/usr/bin/env python3
"""
Quantificação dos flame graphs (tarefas 2, 3 e 4).

Atribuição por SELF TIME (frame folha): cada amostra conta para uma única
categoria, então as categorias particionam 100% do CPU amostrado. É isso que
responde "quanto de CPU é gasto DENTRO de X" — atribuição inclusiva (qualquer
frame do stack casa) conta a mesma amostra em várias categorias e é reportada
à parte, marcada como sobreposta.

Uso: analyze.py [results_dir]
"""
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
JFRCONV = HERE / "build" / "async-profiler-4.5-linux-x64" / "bin" / "jfrconv"
RESULTS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
WINDOW_S = 360  # duracao da janela de profiling de CPU, em segundos

# Ordem importa: a primeira regra que casar vence.
RULES = [
    # --- categorias da hipótese -------------------------------------------
    ("proxy", [
        r"^jdk\.proxy\d*\.", r"\$Proxy\d*", r"^java\.lang\.reflect\.Proxy",
        r"^org\.springframework\.aop\.framework\.",
        r"^org\.springframework\.cglib\.", r"^net\.bytebuddy\.",
        r"^org\.springframework\.data\.repository\.core\.support\.",
        r"^org\.springframework\.data\.projection\.",
        r"_ClientProxy", r"^io\.quarkus\.arc\.impl\.ClientProxy",
    ]),
    ("aop_tx", [
        r"^org\.springframework\.transaction\.",
        r"^org\.springframework\.aop\.interceptor\.",
        r"^org\.springframework\.aop\.aspectj\.",
        r"TransactionAspectSupport",
        r"^io\.quarkus\.arc\.impl\.(Interceptor|InvocationContext|AroundInvoke|Subclass)",
        r"_Subclass", r"WithTransactionInterceptor",
        r"^io\.quarkus\.hibernate\.reactive\.panache\.common\.runtime\.",
        r"^io\.quarkus\.narayana", r"^com\.arjuna\.",
    ]),
    ("reflexao", [
        r"^java\.lang\.reflect\.", r"^jdk\.internal\.reflect\.",
        r"^java\.lang\.Class\.(getMethod|getDeclaredMethod|forName|getAnnotation|getConstructor)",
        r"^java\.lang\.invoke\.", r"LambdaForm",
    ]),
    # --- o "resto", quebrado para responder a tarefa 4 --------------------
    ("app_negocio", [r"^com\.tcc\.orderservice\."]),
    ("orm_mapper", [
        r"^org\.hibernate\.", r"^io\.quarkus\.hibernate\.",
        r"^org\.springframework\.data\.r2dbc\.", r"^org\.springframework\.r2dbc\.",
        r"^org\.springframework\.data\.relational\.", r"^org\.springframework\.data\.mapping\.",
        r"^org\.springframework\.data\.convert\.", r"^org\.springframework\.data\.",
        r"^io\.quarkus\.panache", r"Panache",
    ]),
    ("db_driver", [
        r"^io\.r2dbc\.", r"^io\.vertx\.pgclient\.", r"^io\.vertx\.sqlclient\.",
        r"^org\.postgresql\.", r"^com\.ongres\.",
    ]),
    ("json", [r"^com\.fasterxml\.jackson\.", r"^io\.vertx\.core\.json", r"^io\.quarkus\.jackson"]),
    ("http_netty", [
        r"^io\.netty\.", r"^reactor\.netty\.",
        r"^io\.vertx\.core\.(net|http|impl)", r"^io\.vertx\.core\.buffer",
        r"^org\.jboss\.resteasy\.", r"^io\.quarkus\.resteasy", r"^io\.quarkus\.vertx",
        r"^org\.springframework\.http\.", r"^org\.springframework\.web\.",
        r"^org\.springframework\.core\.io\.buffer\.",
    ]),
    ("reativo", [
        r"^reactor\.core\.", r"^io\.smallrye\.mutiny\.", r"^org\.reactivestreams\.",
        r"^reactor\.util\.",
    ]),
    ("framework_outro", [
        r"^org\.springframework\.", r"^io\.quarkus\.", r"^io\.smallrye\.",
        r"^io\.vertx\.", r"^org\.jboss\.", r"^jakarta\.", r"^org\.slf4j\.",
        r"^ch\.qos\.logback\.", r"^org\.apache\.",
    ]),
    ("jdk_outro", [r"^java\.", r"^jdk\.", r"^sun\.", r"^javax\."]),
    # --- frames nativas: separadas porque "outro" escondia coisa relevante ---
    # Despacho virtual/interface do JIT. itable stub = chamada de método de
    # INTERFACE megamórfica; é o custo de despacho que interessa à hipótese.
    ("despacho_virtual", [
        r"^itable stub$", r"^vtable stub$", r"^I2C/C2I adapters$",
        r"^Interpreter$", r"^StubRoutines", r"^nmethod entry",
    ]),
    ("syscall_rede", [
        r"^send(to|msg)?$", r"^recv(from|msg)?$", r"^__GI___(recv|send|writev|readv|read|write|libc_write|libc_read)",
        r"^(epoll_wait|epoll_ctl|epoll_pwait)$", r"^writev$", r"^readv$",
        r"^__libc_(send|recv|write|read)", r"^sock_", r"^tcp_", r"^ip_",
        r"^__x64_sys_", r"^do_syscall", r"^entry_SYSCALL",
    ]),
    ("sincronizacao", [
        r"futex", r"^SpinPause$", r"pthread_(mutex|cond)", r"^__lll_",
        r"pthread_(en|dis)able_asynccancel",
    ]),
    ("nativo_libc", [
        r"^__mem(set|cpy|move|chr|cmp)", r"arraycopy", r"^clock_gettime",
        r"^__tls_get_addr$", r"^vectorizedMismatch$", r"^__vfprintf",
        r"^_int_(malloc|free)$", r"^malloc$", r"^free$", r"^\[unknown\]$",
        r"\.so( \(deleted\))?$",
    ]),
]
RULES_C = [(name, [re.compile(p) for p in pats]) for name, pats in RULES]

INCLUSIVE_CATS = ("proxy", "aop_tx", "reflexao")

THREAD_BUCKETS = [
    ("compilador_jit", [r"C1 Compiler", r"C2 Compiler", r"CompilerThre"]),
    ("gc", [r"GC Thread", r"G1 ", r"Parallel GC", r"GC Worker", r"Concurrent"]),
    ("vm_outras", [r"VM Thread", r"VM Periodic", r"Service Thread", r"Notification",
                   r"Signal Dispatch", r"Common-Cleaner", r"Reference Handl",
                   r"Finalizer", r"process reaper", r"Attach Listener", r"Sweeper",
                   r"Monitor Ctrl", r"AsyncProf"]),
    ("event_loop_http", [r"reactor-http", r"vert\.x-eventloop"]),
    ("event_loop_db", [r"reactor-tcp", r"vert\.x-.*acceptor"]),
    ("worker_app", [r"parallel-", r"boundedElastic", r"vert\.x-worker",
                    r"executor-thread", r"Hibernate", r"pool-"]),
]
THREAD_BUCKETS_C = [(n, [re.compile(p) for p in ps]) for n, ps in THREAD_BUCKETS]

FRAME_SUFFIX = re.compile(r"_\[[a-zA-Z0-9]+\]$")


def clean(frame: str) -> str:
    return FRAME_SUFFIX.sub("", frame).strip()


def categorize(frame: str) -> str:
    for name, pats in RULES_C:
        for p in pats:
            if p.search(frame):
                return name
    # frames nativas da VM (Klass::method) que escaparam do bucket de thread
    if "::" in frame or frame.endswith("]"):
        return "nativo_vm"
    return "outro"


def bucket_thread(tname: str) -> str:
    for name, pats in THREAD_BUCKETS_C:
        for p in pats:
            if p.search(tname):
                return name
    return "outras_threads"


def convert(jfr: Path, kind: str) -> Path:
    """jfr -> collapsed com nomes normalizados e split por thread."""
    out = jfr.with_suffix(".norm.collapsed")
    flag = "--cpu" if kind == "cpu" else "--wall"
    subprocess.run([str(JFRCONV), flag, "-t", "--norm", "--dot", "-o", "collapsed",
                    str(jfr), str(out)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def parse(collapsed: Path):
    """-> (total, self_por_categoria, incl_por_categoria, self_por_thread, self_por_frame)"""
    total = 0
    self_cat, incl_cat = defaultdict(int), defaultdict(int)
    self_thr, self_frame = defaultdict(int), defaultdict(int)
    with collapsed.open() as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            stack, _, n = line.rpartition(" ")
            try:
                n = int(n)
            except ValueError:
                continue
            frames = [clean(f) for f in stack.split(";")]
            if not frames:
                continue
            total += n
            tname = frames[0]
            tbucket = bucket_thread(tname)
            self_thr[tbucket] += n
            body = frames[1:] or frames
            leaf = body[-1]
            # threads de VM/JIT/GC não entram na taxonomia de aplicação
            if tbucket in ("compilador_jit", "gc", "vm_outras"):
                self_cat[tbucket] += n
            else:
                self_cat[categorize(leaf)] += n
                self_frame[leaf] += n
                seen = {categorize(f) for f in body}
                for c in INCLUSIVE_CATS:
                    if c in seen:
                        incl_cat[c] += n
    return total, self_cat, incl_cat, self_thr, self_frame


def pct(x, tot):
    return 100.0 * x / tot if tot else 0.0


def main():
    runs = defaultdict(dict)  # (ver, kind) -> {rep: parsed}
    for jfr in sorted(RESULTS.glob("*.jfr")):
        m = re.match(r"(sb|qj)-r(\d+)\.(cpu|wall)\.jfr$", jfr.name)
        if not m:
            continue
        ver, rep, kind = m.group(1), int(m.group(2)), m.group(3)
        try:
            col = convert(jfr, kind)
        except subprocess.CalledProcessError:
            print(f"!! falha convertendo {jfr.name}")
            continue
        runs[(ver, kind)][rep] = parse(col)

    for kind in ("cpu", "wall"):
        print(f"\n{'='*78}\nPERFIL {kind.upper()}\n{'='*78}")
        for ver in ("sb", "qj"):
            data = runs.get((ver, kind), {})
            if not data:
                continue
            label = "Spring Boot" if ver == "sb" else "Quarkus JVM"
            print(f"\n--- {label} ({len(data)} repeticoes) ---")
            print(f"{'categoria':<20}" + "".join(f"  rep{r:<7}" for r in sorted(data))
                  + "   media   desvio_max")
            cats = set()
            for _, sc, _, _, _ in data.values():
                cats |= set(sc)
            rows = []
            for c in cats:
                vals = [pct(data[r][1].get(c, 0), data[r][0]) for r in sorted(data)]
                mean = sum(vals) / len(vals)
                dev = max(abs(v - mean) for v in vals) if len(vals) > 1 else 0.0
                rows.append((mean, c, vals, dev))
            for mean, c, vals, dev in sorted(rows, reverse=True):
                if mean < 0.05:
                    continue
                print(f"{c:<20}" + "".join(f"  {v:6.2f}% " for v in vals)
                      + f"  {mean:6.2f}%   +/-{dev:.2f}pp")
            tot = [data[r][0] for r in sorted(data)]
            print(f"{'(amostras)':<20}" + "".join(f"  {t:<7} " for t in tot))
            # inclusivo (sobreposto)
            print("  inclusivo (sobreposto, qualquer frame do stack):", end=" ")
            for c in INCLUSIVE_CATS:
                vals = [pct(data[r][2].get(c, 0), data[r][0]) for r in sorted(data)]
                print(f"{c}={sum(vals)/len(vals):.2f}%", end="  ")
            print()
            # threads
            thr = defaultdict(list)
            for r in sorted(data):
                for t, v in data[r][3].items():
                    thr[t].append(pct(v, data[r][0]))
            print("  por thread:", "  ".join(
                f"{t}={sum(v)/len(v):.1f}%" for t, v in
                sorted(thr.items(), key=lambda kv: -sum(kv[1]))))

    # --- TAREFA 4: decomposição ABSOLUTA do gap de CPU -----------------------
    # 1 amostra de ctimer = 10 ms de CPU. Validado contra o cgroup: o total
    # amostrado bate com a CPU medida do contêiner (ver NOTAS.md).
    MS = 0.010
    print(f"\n{'='*78}\nDECOMPOSICAO ABSOLUTA DO GAP DE CPU (perfil cpu/ctimer)\n{'='*78}")
    absv = {}
    for ver in ("sb", "qj"):
        data = runs.get((ver, "cpu"), {})
        if not data:
            continue
        acc = defaultdict(list)
        for r in data:
            tot, sc, _, _, _ = data[r]
            for c, n in sc.items():
                acc[c].append(n * MS / WINDOW_S)
        absv[ver] = {c: sum(v) / len(v) for c, v in acc.items()}
    if "sb" in absv and "qj" in absv:
        tot_sb = sum(absv["sb"].values())
        tot_qj = sum(absv["qj"].values())
        gap = tot_sb - tot_qj
        print(f"CPU total amostrada: Spring Boot {tot_sb:.4f} vCPU | "
              f"Quarkus JVM {tot_qj:.4f} vCPU | razao {tot_sb/tot_qj:.2f}x | gap {gap:.4f} vCPU\n")
        print(f"{'categoria':<20}{'SB (vCPU)':>12}{'QJ (vCPU)':>12}"
              f"{'delta':>12}{'% do gap':>11}")
        rows = []
        for c in set(absv["sb"]) | set(absv["qj"]):
            a, b = absv["sb"].get(c, 0.0), absv["qj"].get(c, 0.0)
            rows.append((a - b, c, a, b))
        for d, c, a, b in sorted(rows, reverse=True):
            print(f"{c:<20}{a:12.5f}{b:12.5f}{d:12.5f}{100*d/gap:10.1f}%")
        hip = ["proxy", "reflexao", "aop_tx"]
        ha = sum(absv["sb"].get(c, 0) for c in hip)
        hb = sum(absv["qj"].get(c, 0) for c in hip)
        print(f"\n{'>> HIPOTESE (proxy+reflexao+aop_tx)':<20}"
              f"{ha:12.5f}{hb:12.5f}{ha-hb:12.5f}{100*(ha-hb)/gap:10.1f}%")

    # top frames self-time, CPU, agregado por versão
    print(f"\n{'='*78}\nTOP FRAMES POR SELF TIME (CPU, agregado das repeticoes)\n{'='*78}")
    for ver in ("sb", "qj"):
        data = runs.get((ver, "cpu"), {})
        if not data:
            continue
        agg, tot = defaultdict(int), 0
        for r in data:
            tot += data[r][0]
            for f, n in data[r][4].items():
                agg[f] += n
        label = "Spring Boot" if ver == "sb" else "Quarkus JVM"
        print(f"\n--- {label} ---")
        for f, n in sorted(agg.items(), key=lambda kv: -kv[1])[:25]:
            print(f"  {pct(n, tot):5.2f}%  [{categorize(f):<16}] {f}")


if __name__ == "__main__":
    main()
