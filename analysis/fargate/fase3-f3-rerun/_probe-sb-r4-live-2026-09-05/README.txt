Sonda informativa — NÃO é a rodada springboot r4 oficial.

A rodada springboot r4 estava rodando ao vivo quando o orquestrador f3_rerun.sh foi
interrompido para diagnóstico (2026-09-05). Deixada terminar por curiosidade, para
confirmar o diagnóstico da saturação de 2026-09-02 (ver ../saturated-sb-r4-r5/).

Resultado: 208.799 iterações, 0 dropped, p95=73ms, p99≈0, 0.05% das reqs em 3-10s,
0 falha HTTP, k6 rc=0.  <-- rodou LIMPA, ao contrário de 2026-09-02 r4 (p95=2108ms,
293 dropped). Confirma: a saturação de 02/09 foi transitória (variância de GC/host),
não falha estrutural de infra.

A r4 oficial da re-coleta está em ../f3-springboot-r4-*.json (rodada por f3_rerun.sh).
