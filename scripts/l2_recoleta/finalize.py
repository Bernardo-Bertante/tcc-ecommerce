#!/usr/bin/env python3
"""Passo final da recoleta de L2: troca os arquivos antigos de L2 em
analysis/lambda/fase4/ pelos novos (com backup dos antigos), roda
analysis/fase5_analise_estatistica.py para regenerar os 3 CSVs oficiais, e
confirma (por comparacao byte-a-byte) que as linhas de F1/F2/F2-S/F3/L1/L3
nao mudaram -- so L2. Escreve o resumo final em
analysis/l2_recoleta_resumo_final.md.

Uso: python3 finalize.py --staging-dir DIR --repo-root DIR
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging-dir", required=True)
    ap.add_argument("--repo-root", required=True)
    args = ap.parse_args()

    repo_root = args.repo_root
    fase4_dir = os.path.join(repo_root, "analysis", "lambda", "fase4")
    fase5_dir = os.path.join(repo_root, "analysis", "fase5")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    l2_backup_dir = os.path.join(repo_root, "analysis", f"lambda_fase4_l2_backup_{ts}")
    csv_backup_dir = os.path.join(repo_root, "analysis", f"fase5_csv_backup_{ts}")

    os.makedirs(l2_backup_dir, exist_ok=True)
    os.makedirs(csv_backup_dir, exist_ok=True)

    print(f"[finalize] Backup dos arquivos antigos de L2 em {l2_backup_dir}")
    for fname in os.listdir(fase4_dir):
        if fname.startswith("l2-"):
            shutil.copy2(os.path.join(fase4_dir, fname), os.path.join(l2_backup_dir, fname))
            os.remove(os.path.join(fase4_dir, fname))

    print(f"[finalize] Copiando os novos dados de L2 ({args.staging_dir}) para {fase4_dir}")
    for fname in sorted(os.listdir(args.staging_dir)):
        if fname == "_round_windows.json":
            continue
        shutil.copy2(os.path.join(args.staging_dir, fname), os.path.join(fase4_dir, fname))

    _update_timestamps(fase4_dir, args.staging_dir)
    _ensure_l2_not_raw(repo_root)

    backup_csvs = {}
    for csv_name in ["fase5_estatistica_descritiva.csv", "fase5_testes_significancia.csv", "fase5_teste_global.csv"]:
        src = os.path.join(fase5_dir, csv_name)
        if os.path.exists(src):
            dst = os.path.join(csv_backup_dir, csv_name)
            shutil.copy2(src, dst)
            backup_csvs[csv_name] = dst

    print("[finalize] Rodando analysis/fase5_analise_estatistica.py para regenerar os 3 CSVs oficiais...")
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "analysis", "fase5_analise_estatistica.py")],
        cwd=repo_root, capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print(
            f"[finalize] ERRO: fase5_analise_estatistica.py falhou (codigo {result.returncode}). "
            f"Os arquivos antigos de L2 estao preservados em {l2_backup_dir} e os CSVs anteriores em "
            f"{csv_backup_dir}. Nada foi perdido, mas a finalizacao nao completou -- corrija o erro acima "
            f"e rode este script de novo manualmente:\n"
            f"  python3 {os.path.abspath(__file__)} --staging-dir {args.staging_dir} --repo-root {repo_root}",
            file=sys.stderr,
        )
        sys.exit(1)

    problems = _check_non_l2_rows_unchanged(fase5_dir, backup_csvs)
    if problems:
        print("[finalize] ALERTA: cenarios que deveriam permanecer identicos mudaram nos CSVs finais:")
        for p in problems:
            print(f"  - {p}")
        print(f"[finalize] CSVs anteriores preservados em {csv_backup_dir} para comparacao manual.")
    else:
        print("[finalize] Checagem de integridade OK -- F1/F2/F2-S/F3/L1/L3 permaneceram byte-a-byte "
              "identicos nos 3 CSVs oficiais. Somente as linhas de L2 mudaram.")

    _write_final_summary(repo_root, fase5_dir, l2_backup_dir, csv_backup_dir, problems)


def _update_timestamps(fase4_dir, staging_dir):
    """Substitui so as entradas l2-* de timestamps.json, preservando as
    entradas l3-* como estavam (L3 nao faz parte desta recoleta)."""
    timestamps_path = os.path.join(fase4_dir, "timestamps.json")
    timestamps = {}
    if os.path.exists(timestamps_path):
        with open(timestamps_path) as fp:
            timestamps = json.load(fp)

    windows_path = os.path.join(staging_dir, "_round_windows.json")
    if not os.path.exists(windows_path):
        print("[finalize][aviso] _round_windows.json nao encontrado no staging -- "
              "timestamps.json NAO foi atualizado com as novas janelas de L2.")
        return

    with open(windows_path) as fp:
        new_windows = json.load(fp)
    timestamps.update(new_windows)
    with open(timestamps_path, "w") as fp:
        json.dump(timestamps, fp, indent=2, sort_keys=True)
    print(f"[finalize] timestamps.json atualizado com as janelas das {len(new_windows)} novas rodadas de L2.")


def _ensure_l2_not_raw(repo_root):
    """A recoleta sempre extrai latencia no runner e grava *-latency.json
    para as 5 rodadas (nunca guarda o raw.json NDJSON) -- diferente do dado
    de julho, que tinha r1-r3 em raw.json e r4-r5 em latency.json (mudanca
    de convencao no meio da coleta original). fase5_analise_estatistica.py
    ainda espera raw.json para l2 r1-r3 (SCENARIOS["l2"]["raw_rounds"] =
    {1,2,3}); sem esse ajuste, load_latency() pularia silenciosamente 3 das
    5 rodadas novas de L2 (so imprime "[aviso] arquivo nao encontrado,
    pulando", nao falha). Ajusta o config para refletir o formato real dos
    arquivos que estao de fato em disco apos a recoleta -- nao e mudanca de
    metodologia, e so o loader reconhecer o formato (mais simples) que
    persistimos desta vez para todas as 5 rodadas."""
    stats_script = os.path.join(repo_root, "analysis", "fase5_analise_estatistica.py")
    with open(stats_script) as fp:
        content = fp.read()

    old_line = '"l2":  {"dir": "lambda/fase4",   "file_prefix": "l2",  "raw_rounds": {1, 2, 3}},'
    new_line = '"l2":  {"dir": "lambda/fase4",   "file_prefix": "l2",  "raw_rounds": set()},'
    if new_line in content:
        print("[finalize] fase5_analise_estatistica.py ja esta ajustado para l2 sem raw_rounds -- ok.")
        return
    if old_line not in content:
        print(
            "[finalize] ERRO: nao encontrei a linha esperada de SCENARIOS['l2'] em "
            f"{stats_script} para ajustar raw_rounds (o arquivo pode ter mudado desde que este script foi "
            "escrito). Ajuste manualmente antes de prosseguir: SCENARIOS['l2']['raw_rounds'] deve virar "
            "set(), ja que a recoleta grava *-latency.json para as 5 rodadas.",
            file=sys.stderr,
        )
        sys.exit(1)
    content = content.replace(old_line, new_line)
    with open(stats_script, "w") as fp:
        fp.write(content)
    print("[finalize] fase5_analise_estatistica.py ajustado: l2 raw_rounds -> set() (todas as 5 rodadas agora latency.json).")


def _check_non_l2_rows_unchanged(fase5_dir, backup_csvs):
    problems = []
    for csv_name, backup_path in backup_csvs.items():
        new_path = os.path.join(fase5_dir, csv_name)

        old_by_scenario = {}
        with open(backup_path) as fp:
            for row in csv.DictReader(fp):
                cenario = row.get("cenario")
                if cenario != "l2":
                    old_by_scenario.setdefault(cenario, []).append(row)

        new_by_scenario = {}
        with open(new_path) as fp:
            for row in csv.DictReader(fp):
                cenario = row.get("cenario")
                if cenario != "l2":
                    new_by_scenario.setdefault(cenario, []).append(row)

        for cenario, rows in old_by_scenario.items():
            if new_by_scenario.get(cenario) != rows:
                problems.append(f"{csv_name}: linhas do cenario '{cenario}' mudaram (deveriam ser identicas)")
    return problems


def _write_final_summary(repo_root, fase5_dir, l2_backup_dir, csv_backup_dir, problems):
    env_csv_path = os.path.join(fase5_dir, "fase5_l2_ambientes_execucao.csv")
    env_csv_content = ""
    rows = []
    if os.path.exists(env_csv_path):
        with open(env_csv_path) as fp:
            env_csv_content = fp.read()
        with open(env_csv_path) as fp:
            rows = list(csv.DictReader(fp))

    max_values = [int(r["max_invocacoes_ambiente"]) for r in rows if r.get("max_invocacoes_ambiente")]
    crossed_tier1 = [r for r in rows if r.get("ts_cruzou_tier1_1000inv")]
    crossed_tier2 = [r for r in rows if r.get("ts_cruzou_tier2_10000inv")]
    jit_tracked_rows = [r for r in rows if r.get("versao") in ("springboot", "quarkus-jvm")]
    highest_single_env = max(max_values) if max_values else 0

    conclusion = (
        f"O ambiente de execucao mais ativo observado em qualquer rodada/versao acumulou no maximo "
        f"{highest_single_env} invocacoes dentro da janela do cenario (~12min). "
        f"Entre as {len(jit_tracked_rows)} combinacoes rodada/versao com JIT rastreavel (springboot + "
        f"quarkus-jvm), {len(crossed_tier1)} cruzaram o limiar Tier 1 (1.000 invocacoes acumuladas) e "
        f"{len(crossed_tier2)} cruzaram o limiar Tier 2 (10.000) dentro da janela."
    )
    if highest_single_env < 1000:
        conclusion += (
            " NENHUM ambiente individual, em nenhuma rodada, cruzou sequer o limiar Tier 1 -- a fragmentacao "
            "de carga entre ambientes de execucao concorrentes IMPEDE, na pratica, que a JVM demonstre "
            "desempenho pos-aquecimento dentro da janela do cenario L2 como desenhado hoje. Isso deveria ser "
            "declarado como limitacao/achado explicito no texto, nao assumido implicitamente."
        )
    elif highest_single_env < 10000:
        conclusion += (
            " Ambientes individuais conseguem cruzar o Tier 1 em pelo menos algumas combinacoes, mas nenhum "
            "chega ao Tier 2 dentro da janela -- o cenario oferece aquecimento parcial, nao o estado JIT "
            "totalmente otimizado que o desenho original pretendia demonstrar."
        )
    else:
        conclusion += (
            " Pelo menos um ambiente por rodada/versao consegue cruzar o Tier 2 dentro da janela -- a premissa "
            "do cenario L2 (JVM com chance real de aquecimento completo) se sustenta empiricamente."
        )

    integrity_section = (
        "NENHUM PROBLEMA -- todas as linhas de cenarios != l2 permaneceram byte-a-byte identicas nos 3 CSVs."
        if not problems else "\n".join(f"- {p}" for p in problems)
    )

    md = f"""# Recoleta L2 -- Resumo Final

Gerado em {datetime.now(timezone.utc).isoformat()}

## CSVs oficiais atualizados

- `analysis/fase5/fase5_estatistica_descritiva.csv`
- `analysis/fase5/fase5_testes_significancia.csv`
- `analysis/fase5/fase5_teste_global.csv`

Backup dos CSVs anteriores a recoleta: `{os.path.relpath(csv_backup_dir, repo_root)}`
Backup dos arquivos antigos de L2 (`fase4/l2-*.json`): `{os.path.relpath(l2_backup_dir, repo_root)}`

## Checagem de integridade (F1/F2/F2-S/F3/L1/L3 devem ser identicos ao dado anterior)

{integrity_section}

## fase5_l2_ambientes_execucao.csv (dado bruto por rodada/versao)

```
{env_csv_content}
```

## Conclusao

{conclusion}
"""
    out_path = os.path.join(repo_root, "analysis", "l2_recoleta_resumo_final.md")
    with open(out_path, "w") as fp:
        fp.write(md)
    print(f"[finalize] Resumo final escrito em {out_path}")


if __name__ == "__main__":
    main()
