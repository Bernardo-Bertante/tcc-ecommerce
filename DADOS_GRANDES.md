# Dados grandes fora do Git

Alguns arquivos do experimento são grandes demais para o GitHub (limite de 100 MB por arquivo)
ou são saídas brutas que só servem para regerar os dados derivados. Eles ficam fora do
repositório (ver `.gitignore`) e estão listados aqui.

Os **dados derivados** (CSVs de `analysis/fase5/`, `*-latency.json`, `*-summary.json`) e os
**scripts** que os geram estão versionados. Ver a seção "Reprodutibilidade" do README.

## Onde estão guardados

- **Disco local** do autor: todos os arquivos abaixo.
- **Backup em S3** (privado, versionado, criptografado): `analysis/` e `benchmark/results/`
  sincronizados em 31/08/2026. Arquivos criados depois dessa data só estão no disco local até
  o próximo `aws s3 sync`. Disponíveis sob pedido ao autor.

## Resumo por grupo

| Grupo | Arquivos | Tamanho | Conteúdo | Cenário | Guardado em |
|---|---:|---:|---|---|---|
| `analysis/lambda/fase4/{l2,l3}-*-r{1,2,3}-raw.json` | 18 | 2,6 GB | Saída NDJSON bruta do k6 (`--out json`), um ponto por requisição | L2 e L3 (Lambda), rodadas 1–3, 05–06/07/2026 | local + S3 |
| `benchmark/results/**/*_run*.json`, `_downloads/`, `aws*/` | 426 | 12,4 GB | JSON bruto do k6 e pacotes `.tar.gz` de pilotos e validações | Pilotos F1/F2 e validações de dimensionamento, mai–jun/2026 (fora do desenho final) | local + S3 |
| `analysis/exploratorio_pilha_fargate/**` | 122 | 599 MB | `*.k6.csv(.gz)`, perfis `*.collapsed`, `*.jfr` | Exploratório: custo de CPU da pilha no Fargate (20–24/09) | local |
| `analysis/exploratorio_cpu_lambda/**` | 31 | 465 MB | `*.k6.csv`, `*.collapsed`, capturas | Exploratório: gap QJ×SB no Lambda / cliente HTTP (13/09) | local |
| `analysis/exploratorio_gc_f3/**` | 15 | 385 MB | `*.k6.csv(.gz)`, logs brutos de GC | Exploratório: GC × cauda do SB no F3 (20–21/09) | local |
| `analysis/exploratorio_c2_lambda/**` | 26 | 366 MB | `*.k6.csv`, `*.collapsed` | Exploratório: C1 × C2 no Lambda (16/09) | local |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/**` | 24 | 245 MB | `k6_raw.json.gz`, `codelist*.txt` | Exploratório: nível de JIT no Fargate (29–30/09) | local |
| `analysis/exploratorio_gc_f1/**` | 12 | 121 MB | `*.k6.csv`, `*.jfr` | Exploratório: GC no F1 Native (13/09) | local |

## Lista completa (exceto `benchmark/results/`)

| Arquivo | Tamanho |
|---|---:|
| `analysis/exploratorio_c2_lambda/results/r1-qj-c1.codelist` | 0,9 MB |
| `analysis/exploratorio_c2_lambda/results/r1-qj-c1.k6.csv` | 29,1 MB |
| `analysis/exploratorio_c2_lambda/results/r1-qj-c2.codelist` | 1,1 MB |
| `analysis/exploratorio_c2_lambda/results/r1-qj-c2.k6.csv` | 29,1 MB |
| `analysis/exploratorio_c2_lambda/results/r1-sb-c1.codelist` | 1,2 MB |
| `analysis/exploratorio_c2_lambda/results/r1-sb-c1.k6.csv` | 28,9 MB |
| `analysis/exploratorio_c2_lambda/results/r1-sb-c2.codelist` | 1,4 MB |
| `analysis/exploratorio_c2_lambda/results/r1-sb-c2.k6.csv` | 29,0 MB |
| `analysis/exploratorio_c2_lambda/results/r2-qj-c1.codelist` | 0,9 MB |
| `analysis/exploratorio_c2_lambda/results/r2-qj-c1.k6.csv` | 29,1 MB |
| `analysis/exploratorio_c2_lambda/results/r2-qj-c2.codelist` | 1,1 MB |
| `analysis/exploratorio_c2_lambda/results/r2-qj-c2.k6.csv` | 29,1 MB |
| `analysis/exploratorio_c2_lambda/results/r2-sb-c1.codelist` | 1,2 MB |
| `analysis/exploratorio_c2_lambda/results/r2-sb-c1.k6.csv` | 29,0 MB |
| `analysis/exploratorio_c2_lambda/results/r2-sb-c2.codelist` | 1,5 MB |
| `analysis/exploratorio_c2_lambda/results/r2-sb-c2.k6.csv` | 29,0 MB |
| `analysis/exploratorio_c2_lambda/results/r3-qj-c1.codelist` | 0,9 MB |
| `analysis/exploratorio_c2_lambda/results/r3-qj-c1.k6.csv` | 29,1 MB |
| `analysis/exploratorio_c2_lambda/results/r3-qj-c2.codelist` | 1,1 MB |
| `analysis/exploratorio_c2_lambda/results/r3-qj-c2.k6.csv` | 29,1 MB |
| `analysis/exploratorio_c2_lambda/results/r3-sb-c1.codelist` | 1,2 MB |
| `analysis/exploratorio_c2_lambda/results/r3-sb-c1.k6.csv` | 29,0 MB |
| `analysis/exploratorio_c2_lambda/results/r3-sb-c2.codelist` | 1,5 MB |
| `analysis/exploratorio_c2_lambda/results/r3-sb-c2.k6.csv` | 29,0 MB |
| `analysis/exploratorio_c2_lambda/smoke/smoke-qj-c2.codelist` | 1,0 MB |
| `analysis/exploratorio_c2_lambda/smoke/smoke-qj-c2.k6.csv` | 2,7 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h1-qja-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h1-qj-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h1-sb-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h1-sbu-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h2-qja-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h2-qj-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h2-sb-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h2-sbu-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h3-qja-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h3-qj-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h3-sb-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results_httpclient/h3-sbu-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results/r1-qj-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results/r1-qj-lim.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results/r1-sb-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results/r1-sb-lim.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results/r2-qj-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results/r2-qj-lim.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results/r2-sb-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results/r2-sb-lim.k6.csv` | 18,0 MB |
| `analysis/exploratorio_cpu_lambda/results/r3-qj-free.k6.csv` | 18,2 MB |
| `analysis/exploratorio_cpu_lambda/results/r3-qj-lim.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results/r3-sb-free.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/results/r3-sb-lim.k6.csv` | 18,1 MB |
| `analysis/exploratorio_cpu_lambda/smoke_httpclient/s2-qja.k6.csv` | 2,4 MB |
| `analysis/exploratorio_cpu_lambda/smoke_httpclient/s2-qj.k6.csv` | 2,4 MB |
| `analysis/exploratorio_cpu_lambda/smoke_httpclient/s-qja.k6.csv` | 1,8 MB |
| `analysis/exploratorio_cpu_lambda/smoke_httpclient/s-sbu.k6.csv` | 1,8 MB |
| `analysis/exploratorio_cpu_lambda/tcpdump/cap-qj.k6.csv` | 7,3 MB |
| `analysis/exploratorio_cpu_lambda/tcpdump/cap-sb.k6.csv` | 7,3 MB |
| `analysis/exploratorio_cpu_lambda/tcpdump/cap-sbu.k6.csv` | 7,3 MB |
| `analysis/exploratorio_gc_f1/results/qj-240-r1.k6.csv.gz` | 16,6 MB |
| `analysis/exploratorio_gc_f1/results/qj-240-r2.k6.csv.gz` | 16,8 MB |
| `analysis/exploratorio_gc_f1/results/qj-240-r3.k6.csv.gz` | 16,9 MB |
| `analysis/exploratorio_gc_f1/results/qj-48-r1.k6.csv.gz` | 3,4 MB |
| `analysis/exploratorio_gc_f1/results/qj-48-r2.k6.csv.gz` | 3,4 MB |
| `analysis/exploratorio_gc_f1/results/qj-48-r3.k6.csv.gz` | 3,4 MB |
| `analysis/exploratorio_gc_f1/results/qn-240-r1.k6.csv.gz` | 16,9 MB |
| `analysis/exploratorio_gc_f1/results/qn-240-r2.k6.csv.gz` | 16,9 MB |
| `analysis/exploratorio_gc_f1/results/qn-240-r3.k6.csv.gz` | 16,5 MB |
| `analysis/exploratorio_gc_f1/results/qn-48-r1.k6.csv.gz` | 3,4 MB |
| `analysis/exploratorio_gc_f1/results/qn-48-r2.k6.csv.gz` | 3,4 MB |
| `analysis/exploratorio_gc_f1/results/qn-48-r3.k6.csv.gz` | 3,4 MB |
| `analysis/exploratorio_gc_f3/results/gc_raw/gc.stream.qj.err` | 0,0 MB |
| `analysis/exploratorio_gc_f3/results/gc_raw/gc.stream.sb.err` | 0,0 MB |
| `analysis/exploratorio_gc_f3/results/qj-r1.k6.csv.gz` | 25,7 MB |
| `analysis/exploratorio_gc_f3/results/qj-r2.k6.csv.gz` | 25,8 MB |
| `analysis/exploratorio_gc_f3/results/sb-r1.k6.csv.gz` | 26,0 MB |
| `analysis/exploratorio_gc_f3/results/sb-r2.k6.csv.gz` | 26,0 MB |
| `analysis/exploratorio_gc_f3/results/sb-r3.k6.csv.gz` | 26,0 MB |
| `analysis/exploratorio_gc_f3/results/sb-r4.k6.csv.gz` | 26,0 MB |
| `analysis/exploratorio_gc_f3/results/sb-r5.k6.csv.gz` | 26,0 MB |
| `analysis/exploratorio_gc_f3/results_tentativa1_db_saturado/gc_raw/gc.log.0` | 20,0 MB |
| `analysis/exploratorio_gc_f3/results_tentativa1_db_saturado/gc_raw/gc.stream.sb.err` | 0,0 MB |
| `analysis/exploratorio_gc_f3/results_tentativa1_db_saturado/sb-r1.k6.csv.gz` | 26,1 MB |
| `analysis/exploratorio_gc_f3/results_tentativa1_db_saturado/sb-r2.k6.csv.gz` | 26,1 MB |
| `analysis/exploratorio_gc_f3/results_tentativa1_db_saturado/sb-r3.k6.csv.gz` | 24,6 MB |
| `analysis/exploratorio_gc_f3/results_tentativa1_db_saturado/sb-r4.k6.csv` | 106,7 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f1-quarkus-jvm/codelist_bruto.txt` | 1,6 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f1-quarkus-jvm/codelist.txt` | 1,6 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f1-quarkus-jvm/k6_raw.json.gz` | 13,5 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f1-springboot/codelist_bruto.txt` | 2,7 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f1-springboot/codelist.txt` | 2,7 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f1-springboot/k6_raw.json.gz` | 13,4 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2-quarkus-jvm/codelist_bruto.txt` | 1,8 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2-quarkus-jvm/codelist.txt` | 1,8 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2-quarkus-jvm/k6_raw.json.gz` | 46,2 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2-springboot/codelist_bruto.txt` | 3,1 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2-springboot/codelist.txt` | 3,0 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2-springboot/k6_raw.json.gz` | 46,1 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2s-quarkus-jvm/codelist_bruto.txt` | 1,3 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2s-quarkus-jvm/codelist.txt` | 1,3 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2s-quarkus-jvm/k6_raw.json.gz` | 1,1 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2s-springboot/codelist_bruto.txt` | 2,1 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2s-springboot/codelist.txt` | 2,1 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f2s-springboot/k6_raw.json.gz` | 1,1 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f3-quarkus-jvm/codelist_bruto.txt` | 1,8 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f3-quarkus-jvm/codelist.txt` | 1,7 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f3-quarkus-jvm/k6_raw.json.gz` | 44,2 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f3-springboot/codelist_bruto.txt` | 3,0 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f3-springboot/codelist.txt` | 2,9 MB |
| `analysis/exploratorio/jit-fargate/fase_b/rodadas/f3-springboot/k6_raw.json.gz` | 44,7 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.cpu.collapsed` | 3,3 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.cpu.jfr` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.cpu.norm.collapsed` | 3,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.k6.csv.gz` | 5,9 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.smoke.collapsed` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.smoke.jfr` | 0,1 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.wall.collapsed` | 0,3 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.wall.jfr` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r1.wall.norm.collapsed` | 0,4 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.cpu.collapsed` | 3,3 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.cpu.jfr` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.cpu.norm.collapsed` | 3,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.k6.csv.gz` | 5,9 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.smoke.collapsed` | 0,1 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.smoke.jfr` | 0,1 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.wall.collapsed` | 1,4 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.wall.jfr` | 0,7 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/qj-r2.wall.norm.collapsed` | 1,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.cpu.collapsed` | 19,5 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.cpu.jfr` | 2,3 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.cpu.norm.collapsed` | 22,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.smoke.collapsed` | 0,8 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.wall.collapsed` | 4,0 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.wall.jfr` | 1,3 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r1.wall.norm.collapsed` | 4,5 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.cpu.collapsed` | 17,5 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.cpu.jfr` | 2,1 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.cpu.norm.collapsed` | 20,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.wall.collapsed` | 2,4 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.wall.jfr` | 1,2 MB |
| `analysis/exploratorio_pilha_fargate/results_1vcpu/sb-r2.wall.norm.collapsed` | 2,6 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.cpu.collapsed` | 3,8 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.cpu.jfr` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.cpu.norm.collapsed` | 4,8 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.k6.csv.gz` | 5,9 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.smoke.collapsed` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.smoke.jfr` | 0,1 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.wall.collapsed` | 1,4 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.wall.jfr` | 1,2 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r1.wall.norm.collapsed` | 1,7 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.cpu.collapsed` | 3,6 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.cpu.jfr` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.cpu.norm.collapsed` | 4,5 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.k6.csv.gz` | 5,9 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.smoke.collapsed` | 0,3 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.smoke.jfr` | 0,1 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.wall.collapsed` | 0,4 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.wall.jfr` | 1,0 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r2.wall.norm.collapsed` | 0,5 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.cpu.collapsed` | 3,6 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.cpu.jfr` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.cpu.norm.collapsed` | 4,5 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.k6.csv.gz` | 5,9 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.smoke.collapsed` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.smoke.jfr` | 0,1 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.wall.collapsed` | 0,4 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.wall.jfr` | 1,0 MB |
| `analysis/exploratorio_pilha_fargate/results/qj-r3.wall.norm.collapsed` | 0,5 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.cpu.collapsed` | 19,0 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.cpu.jfr` | 2,4 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.cpu.norm.collapsed` | 24,1 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.smoke.collapsed` | 0,7 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.wall.collapsed` | 3,3 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.wall.jfr` | 1,5 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r1.wall.norm.collapsed` | 3,9 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.cpu.collapsed` | 18,9 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.cpu.jfr` | 2,4 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.cpu.norm.collapsed` | 23,6 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.wall.collapsed` | 5,8 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.wall.jfr` | 1,9 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r2.wall.norm.collapsed` | 6,7 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.cpu.collapsed` | 18,5 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.cpu.jfr` | 2,2 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.cpu.norm.collapsed` | 22,5 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.wall.collapsed` | 4,0 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.wall.jfr` | 1,5 MB |
| `analysis/exploratorio_pilha_fargate/results/sb-r3.wall.norm.collapsed` | 4,6 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.cpu.collapsed` | 15,7 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.cpu.jfr` | 1,9 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.cpu.norm.collapsed` | 18,3 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.k6.csv.gz` | 5,9 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.wall.collapsed` | 4,3 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r1.wall.jfr` | 1,4 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.cpu.collapsed` | 17,5 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.cpu.jfr` | 2,1 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.cpu.norm.collapsed` | 20,8 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.wall.collapsed` | 3,7 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r2.wall.jfr` | 1,3 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.cpu.collapsed` | 17,7 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.cpu.jfr` | 2,2 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.cpu.norm.collapsed` | 21,0 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.wall.collapsed` | 4,9 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbnv-r3.wall.jfr` | 1,4 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.cpu.collapsed` | 19,1 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.cpu.jfr` | 2,3 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.cpu.norm.collapsed` | 22,6 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.k6.csv.gz` | 6,0 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.smoke.collapsed` | 0,6 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.smoke.jfr` | 0,2 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.wall.collapsed` | 5,3 MB |
| `analysis/exploratorio_pilha_fargate/validacao_conexao/results/sbval-a1.wall.jfr` | 1,5 MB |
| `analysis/lambda/fase4/l2-quarkus-jvm-r1-raw.json` | 124,7 MB |
| `analysis/lambda/fase4/l2-quarkus-jvm-r2-raw.json` | 124,7 MB |
| `analysis/lambda/fase4/l2-quarkus-jvm-r3-raw.json` | 124,7 MB |
| `analysis/lambda/fase4/l2-quarkus-native-r1-raw.json` | 125,0 MB |
| `analysis/lambda/fase4/l2-quarkus-native-r2-raw.json` | 125,0 MB |
| `analysis/lambda/fase4/l2-quarkus-native-r3-raw.json` | 125,0 MB |
| `analysis/lambda/fase4/l2-springboot-r1-raw.json` | 124,8 MB |
| `analysis/lambda/fase4/l2-springboot-r2-raw.json` | 124,8 MB |
| `analysis/lambda/fase4/l2-springboot-r3-raw.json` | 124,8 MB |
| `analysis/lambda/fase4/l3-quarkus-jvm-r1-raw.json` | 170,6 MB |
| `analysis/lambda/fase4/l3-quarkus-jvm-r2-raw.json` | 170,5 MB |
| `analysis/lambda/fase4/l3-quarkus-jvm-r3-raw.json` | 170,6 MB |
| `analysis/lambda/fase4/l3-quarkus-native-r1-raw.json` | 170,6 MB |
| `analysis/lambda/fase4/l3-quarkus-native-r2-raw.json` | 170,6 MB |
| `analysis/lambda/fase4/l3-quarkus-native-r3-raw.json` | 170,6 MB |
| `analysis/lambda/fase4/l3-springboot-r1-raw.json` | 170,9 MB |
| `analysis/lambda/fase4/l3-springboot-r2-raw.json` | 170,4 MB |
| `analysis/lambda/fase4/l3-springboot-r3-raw.json` | 170,7 MB |
