#!/usr/bin/env python3
"""Relatório PRELIMINAR automático (gerado no runner, sem interpretação). O relatório final
RESULTADOS_JIT_FARGATE.md é escrito na Fase C, depois da validação dos dados.
Uso: relatorio_preliminar.py <dir_csv> <dir_rodadas>  > RESULTADOS_JIT_FARGATE_preliminar.md"""
import csv, json, os, sys
from collections import defaultdict
from datetime import datetime, timezone

dcsv, drod = sys.argv[1], sys.argv[2]
ler = lambda n: list(csv.DictReader(open(os.path.join(dcsv, n)))) if os.path.exists(os.path.join(dcsv, n)) else []
ORDEM = {"f1": 0, "f2": 1, "f2s": 2, "f3": 3}
chave = lambda r: (ORDEM.get(r["cenario"], 9), r["runtime"])


def tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in l) + " |" for l in linhas]
    return "\n".join(out)


print("# RESULTADOS_JIT_FARGATE — PRELIMINAR (gerado automaticamente)\n")
print("**Exploratório, fora do desenho experimental oficial.** Gerado no exp-jit-runner em "
      f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, sem validação humana. Não usar como dado oficial.\n")
print("Diferenças em relação ao oficial: RDS separado (`exp-jit-postgres`), `-XX:+PrintCompilation`, "
      "awslogs non-blocking com buffer de 25 MB explícito, senha via Secrets Manager, ECS Exec ligado. "
      "Latências deste teste não são comparáveis às oficiais e não são reportadas.\n")

print("## Rodadas (task, imagem, janela de carga)\n")
lin = []
for d in sorted(os.listdir(drod)) if os.path.isdir(drod) else []:
    p = os.path.join(drod, d, "meta.json")
    if "_tentativa_falha_" in d or not os.path.exists(p):
        continue
    m = json.load(open(p))
    dur = (m["carga_fim_ms"] - m["carga_inicio_ms"]) / 60000
    lin.append([m["cenario"], m["runtime"], m["task_arn"].split("/")[-1], (m.get("image_digest") or "")[:19],
                m.get("task_started_at"), datetime.fromtimestamp(m["carga_inicio_ms"] / 1000, timezone.utc).strftime("%H:%M:%S"),
                f"{dur:.1f}", m.get("requisicoes_carga")])
lin.sort(key=lambda l: (ORDEM.get(l[0], 9), l[1]))
print(tabela(["cenário", "versão", "task", "imageDigest", "startedAt", "início carga (UTC)", "carga (min)", "requisições"], lin))

print("\n## P1 — métodos por nível ao fim da carga (log) e no jcmd\n")
rows = sorted(ler("nivel_por_rodada.csv"), key=chave)
print(tabela(["cenário", "versão", "n1", "n2", "n3", "n4", "jcmd n4", "OSR n4 vivas", "distintos que atingiram n4",
              "n4 antes da carga", "100º n4 (s)", "1000º n4 (s)", "último n4 (s)"],
             [[r["cenario"], r["runtime"], r["metodos_fim_nivel1"], r["metodos_fim_nivel2"], r["metodos_fim_nivel3"],
               r["metodos_fim_nivel4"], r["jcmd_metodos_nivel4"], r["osr_vivas_fim_nivel4"],
               r["metodos_distintos_que_atingiram_n4"], r["n4_antes_da_carga"], r["t_100o_n4_s"], r["t_1000o_n4_s"],
               r["t_ultimo_n4_s"]] for r in rows]))
print("\nTempos em segundos desde a 1ª requisição da carga (negativo = antes da carga, no boot/setup).")

print("\n## P2 — caminho do GET /orders/summary (métodos com certeza = certo)\n")
sp = [r for r in ler("summary_path_nivel.csv") if r["certeza"] == "certo"]
agg = defaultdict(lambda: defaultdict(int))
for r in sp:
    agg[(r["cenario"], r["runtime"])][r["leitura"]] += 1
print(tabela(["cenário", "versão", "atingiu", "atingiu só no fim", "atingiu antes da carga", "não atingiu", "não compilado"],
             [[c, rt, a["atingiu"], a["atingiu so no fim"], a["atingiu antes da carga"], a["nao atingiu"],
               a["nao compilado (so interpretado ou nao executado)"]]
              for (c, rt), a in sorted(agg.items(), key=lambda kv: (ORDEM.get(kv[0][0], 9), kv[0][1]))]))
print("\nDetalhe por método: `csv/summary_path_nivel.csv`. \"Só no fim\" = 1º nível 4 depois de 80% da janela de carga.\n")
print("Métodos do caminho que atingiram nível 4 (t = s desde o início da carga; chamadas = summary até então):\n")
print(tabela(["cenário", "versão", "método", "t 1º n4 (s)", "chamadas summary", "leitura"],
             [[r["cenario"], r["runtime"], r["metodo"].split(".")[-1], r["t_primeiro_n4_s"], r["chamadas_summary_ate_n4"], r["leitura"]]
              for r in sorted(sp, key=chave) if r["nivel_max"] == "4"]))

print("\n## P3 — deoptimização (linhas `made not entrant`)\n")
print(tabela(["cenário", "versão", "total", "durante a carga", "de n4", "caminho summary", "caminho summary na carga"],
             [[r["cenario"], r["runtime"], r["made_not_entrant_total"], r["durante_carga"], r["de_nivel4"],
               r["caminho_summary_total"], r["caminho_summary_durante_carga"]] for r in sorted(ler("deopt.csv"), key=chave)]))

print("\n## Integridade da captura\n")
print(tabela(["cenário", "versão", "eventos", "compilações", "não parseadas", "ids sem linha", "maior lacuna",
              "codelist", "codelist ausentes no log", "JVMs no log", "spread relógio (ms)"],
             [[r["cenario"], r["runtime"], r["eventos_log"], r["compilacoes"], r["linhas_nao_parseadas"], r["ids_faltando"],
               r["maior_lacuna"], r["codelist_entradas"], r["codelist_ids_ausentes_no_log"], r["jvms_no_log"],
               r["relogio_spread_p05_p95_ms"]] for r in sorted(ler("integridade.csv"), key=chave)]))
print("\n\"ids sem linha\" inclui tarefas de compilação descartadas da fila (acontece sem perda de log: no teste local, "
      "~8% no SB e ~3% no QJ). A prova de integridade é \"codelist ausentes no log\" (esperado 0 ou 1, uma linha "
      "corrompida por intercalação com o log da aplicação).")
