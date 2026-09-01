"""
Extrai CPU/memória de container (Fargate) para as 15 execuções do F1 re-executado
(analysis/fargate/fase3-f1-rerun/), usando EXATAMENTE a mesma lógica do modo
`recursos` de fase5_analise_estatistica.py:

  - Namespace CloudWatch: ECS/ContainerInsights
  - Métricas: CpuUtilized, MemoryUtilized
  - Dimensões: ClusterName=order-service-cluster + TaskDefinitionFamily=<runtime>
  - Janela por rodada: mtime do summary.json +/- padding (estimate_round_window_from_mtime,
    padding_sec=600), period=300s (SCENARIO_METRIC_PERIOD_SEC["f1"])

Só troca SCENARIOS["f1"]["dir"] para a pasta da re-coleta. Saída separada, não toca
em fase5_fargate_recursos*.csv.
"""
import os
import pandas as pd
import fase5_analise_estatistica as f5

f5.SCENARIOS["f1"]["dir"] = "fargate/fase3-f1-rerun"

OUT = os.path.join(f5.OUTPUT_DIR, "fase5_f1_corrigido_fargate_recursos.csv")


def main():
    os.makedirs(f5.OUTPUT_DIR, exist_ok=True)
    df = f5.analyze_fargate_resources("f1")
    if df.empty:
        print("\n[!] NENHUM datapoint retornado — sem dado de CPU/mem para a janela do F1-rerun.")
        return
    df.to_csv(OUT, index=False)
    print(f"\n[ok] {OUT}")

    # pico por runtime (mesma leitura que a monografia faz: max entre as 5 rodadas)
    print("\n=== PICO de CPU/mem por runtime (F1 re-executado, 48 iter/s) ===")
    for rt, g in df.groupby("runtime"):
        print(f"  {rt:15} cpu_units_max={g['cpu_units_max'].max():7.1f}  "
              f"cpu_pct_max={g['cpu_pct_max'].max():5.1f}%  "
              f"mem_mb_max={g['mem_mb_max'].max():6.1f}  mem_pct_max={g['mem_pct_max'].max():5.1f}%  "
              f"(cpu_units_mean médio={g['cpu_units_mean'].mean():.1f})")

    old_path = os.path.join(f5.OUTPUT_DIR, "fase5_fargate_recursos_novo.csv")
    if os.path.exists(old_path):
        old = pd.read_csv(old_path)
        old = old[old["cenario"] == "f1"]
        print("\n=== PICO F1 ANTIGO (30 iter/s, com bug) — fase5_fargate_recursos_novo.csv ===")
        for rt, g in old.groupby("runtime"):
            print(f"  {rt:15} cpu_units_max={g['cpu_units_max'].max():7.1f}  "
                  f"cpu_pct_max={g['cpu_pct_max'].max():5.1f}%  "
                  f"mem_mb_max={g['mem_mb_max'].max():6.1f}  mem_pct_max={g['mem_pct_max'].max():5.1f}%  "
                  f"(cpu_units_mean médio={g['cpu_units_mean'].mean():.1f})")


if __name__ == "__main__":
    main()
