# Investigação exploratória: gap Quarkus JVM vs Spring Boot no Lambda (L2/L3)

Exploratório, 13/09/2026. **Não é resultado formal do TCC** (N pequeno, ambiente local).

## Setup comum

- Código: `order-processor` (é o que roda no Lambda L2/L3). Zips idênticos aos publicados (sha256 conferido)
  para as versões originais; variantes buildadas no worktree `../ecommerce-tcc-httpclient-probe`
  (branch `exp/httpclient-probe`, não mesclado).
- Runtime: imagem `public.ecr.aws/lambda/java:21` + RIE, `AWS_LAMBDA_FUNCTION_MEMORY_SIZE=512`.
  A JVM sobe com as mesmas flags do Lambda (`-XX:+UseSerialGC -XX:TieredStopAtLevel=1`, heap ~445 MB).
- DynamoDB Local (container pinado nos núcleos 8,10); função pinada em 2,4; k6 em 6,7; dockerd nativo.
- Carga: `processOrder` com o payload do L2, 20 rps, 1 VU (serial), 300 s (~6000 invocações);
  1 ambiente novo por rodada; métricas sobre invocações seq > 1000.

## Teste 1 — CPU restrita (`results/`, `run_all.sh`)

3 rodadas × {SB, QJ} × {livre, `--cpus=0.29`}, ordem contrabalanceada.

| Condição | Mediana SB | Mediana QJ | QJ vs SB | CPU/invocação SB / QJ |
|---|---|---|---|---|
| Livre | 8,12 ms | 11,63 ms | +43% | 5,4 / 5,7 ms |
| 0,29 vCPU | 8,27 ms | 11,80 ms | +43% | 5,9 / 5,8 ms |

Conclusão: a restrição de CPU não altera o gap; hipótese de CPU escassa descartada.
Ressalva: a 20 rps a cota só foi atingida em ~2% dos períodos (ambiente saturado não testado).

## Teste 2 — cliente HTTP do SDK DynamoDB (`results_httpclient/`, `run_httpclient.sh`)

3 rodadas × 4 configurações, CPU livre, controles re-rodados na mesma sessão.

| Configuração | Cliente | Mediana | p90 | CPU/invocação | vs SB (mediana) |
|---|---|---|---|---|---|
| SB original | apache | 6,64 | 8,72 | 4,76 | — |
| QJ + apache | apache | 6,14 | 8,28 | 4,42 | −7,5% |
| QJ original | UrlConnection | 9,79 | 13,30 | 5,02 | +47% |
| SB + UrlConnection | UrlConnection | 10,66 | 13,55 | 5,65 | +61% |

Por rodada (mediana, ms): SB 6,24 / 6,68 / 7,00 · QJA 6,79 / 6,05 / 5,59 · QJ 10,49 / 8,72 / 10,17 ·
SBU 10,61 / 10,58 / 10,80.

Conclusão: a latência segue o cliente, não o framework, nos dois sentidos. A troca para apache não aumenta
a CPU por invocação (diminui).

Alterações das variantes:
- Quarkus: `apache-client` + `io.quarkus:quarkus-apache-httpclient` (sem ele: `NoClassDefFoundError`
  de `commons-logging`), `httpClientBuilder(ApacheHttpClient.builder())`.
- Spring Boot: `url-connection-client` + `httpClientBuilder(UrlConnectionHttpClient.builder())`.

## Diagnóstico de rede

- Os dois clientes fazem keep-alive: 0 `ActiveOpens` durante a carga, 1 socket ESTABLISHED para :8000,
  0 TIME_WAIT.
- UrlConnection: +2,3 segmentos TCP por invocação em cada direção (15,2 vs 12,95 enviados), 0 retransmissões,
  independentemente do framework. Cada invocação faz 2 chamadas ao DynamoDB.
- Mecanismo (captura tcpdump na porta 8000 a partir do namespace de rede da função, ~10-19 invocações
  aquecidas por variante, 120 s de carga com captura aos 90 s; `tcpdump/cap-{sb,sbu,qj}.txt`):

  | Variante | Segmentos/inv | Rede: requisição→resposta | Cliente: resposta→próxima requisição | Span das chamadas DynamoDB/inv |
  |---|---|---|---|---|
  | SB (apache) | 8,0 | 0,36 ms | 0,37 ms | 1,97 ms |
  | SB + UrlConnection | 13,2 | 0,67 ms | 1,79 ms | 5,73 ms |
  | QJ original (UrlConnection) | 14,2 | 0,65 ms | 1,91 ms | 6,24 ms |

  (medianas; ~3 chamadas DynamoDB por invocação: 1 `putItem` do pedido + 1 por item)

  - Apache escreve cada requisição HTTP num único segmento (cabeçalho+corpo). UrlConnection escreve em dois
    (cabeçalho ~927 B, corpo ~230-360 B); o servidor devolve um ACK puro entre eles. Isso explica os segmentos
    extras e ~+0,3 ms por chamada (≈ +0,9 ms/inv). Não há travamento de Nagle/delayed ACK dentro da requisição
    (os gaps de ~40 ms são o intervalo entre invocações e aparecem igual nas duas variantes).
  - A maior parte do gap (~+1,5 ms por intervalo entre chamadas ≈ +2,9 ms/inv) está no próprio cliente, dentro da
    JVM, entre receber a resposta e enviar a próxima requisição. O comportamento é idêntico no SB e no QJ quando
    ambos usam UrlConnection → é do cliente, não do framework.
  - Soma (+0,9 + +2,9 ≈ +3,8 ms) ≈ span +3,8-4,3 ms ≈ gap de latência k6 medido.
  - Causa interna exata desse tempo no cliente **não identificada**. Parte é CPU (UrlConnection gasta
    ~0,6-0,9 ms a mais de CPU por invocação: SBU 5,65 vs SB 4,76; QJ 5,02 vs QJA 4,42), o resto não é
    atribuível com estes dados (precisaria de profiler).

## Correção em relação ao Teste 1

No Teste 1, SB e QJ gastaram CPU parecida por invocação, mas no Teste 2 (mesmo framework, cliente trocado) o
UrlConnection custa ~14-19% mais CPU. Isso não reabre a hipótese de CPU: a troca para apache reduz latência
**e** CPU, e a restrição a 0,29 vCPU não mudou o gap.

## Limitações

DynamoDB Local ≠ DynamoDB real (latência de rede e servidor diferentes; o gap absoluto local ~3-4 ms é
parecido com os ~3,2 ms do Lambda, mas isso pode ser coincidência). RIE ≠ serviço Lambda.
