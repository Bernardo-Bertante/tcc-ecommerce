# Reinicialização de estado do DynamoDB entre repetições: L1, L2, L3 (Lambda)

22/09/2026. Verifica se existia algum procedimento de limpeza/reinicialização da(s)
tabela(s) DynamoDB entre repetições dos cenários Lambda — análogo ao `TRUNCATE` do
Fargate — e se o volume acumulado poderia ter afetado a latência medida em L2/L3.
Motivado pela investigação `analysis/reproducao_f3_instabilidade/`, que mostrou que no
Fargate o crescimento da tabela `orders` durante a carga é a causa da instabilidade de
p95 do Spring Boot em F3. Não altera nenhum `.tex`/`.md` do texto.

Reproduzir (nesta pasta): `python3 espaco_de_chaves.py` e `python3 tendencia_por_rodada.py`.

## Resposta curta

**Não havia nenhuma limpeza, e não há efeito de acúmulo.** Nem entre repetições, nem
entre versões, nem entre cenários: as tabelas `processed_orders` e `stock_reservations`
foram criadas em 21/06/2026 e nunca foram truncadas, recriadas nem tiveram itens
removidos ao longo de toda a campanha. Elas ainda existem na conta `pessoal`
(776648109551, us-east-1).

Isso não teve efeito sobre a medição por **duas** razões independentes, ambas verificadas:

1. **O `order-processor` só faz `PutItem` por chave primária.** Não há `Scan`,
   `Query`, agregação nem sequer uma leitura — e a IAM role da stack concede
   literalmente só `dynamodb:PutItem`. O custo de um `PutItem` por chave no DynamoDB
   não depende do número de itens da tabela. Não existe o análogo do
   `GET /orders/summary` do Fargate.
2. **A tabela não crescia.** O `orderId` vem de um pool determinístico de 4.096 UUIDs
   (seed fixa), idêntico em toda rodada, versão e cenário. Como `orderId` é a chave de
   partição e a operação é `PutItem`, as rodadas seguintes **sobrescrevem** as mesmas
   chaves. O teto simulado (4.096 e 12.288 chaves) bate com o `ItemCount` real
   (4.101 e 12.293) e é atingido **dentro da primeira rodada**.

A latência mediana de L2/L3 **tem** uma deriva crescente de r1→r5 (+1,8 a +3,4 ms,
+6% a +13%, monótona nas 6 séries), mas ela **não** é acúmulo — as duas tabelas já
estavam saturadas nos primeiros ~7 min da primeira rodada e ficaram constantes daí em
diante, e dentro de uma rodada (18.601 escritas) não há deriva nenhuma. Ver §4.

## 1. Nenhum script de coleta tem limpeza de DynamoDB

**Protocolo documentado.** `03-methodology.md` l.23-27 ("Protocolo experimental
obrigatório (Lambda, L1/L2/L3)") tem 4 passos: confirmar Function URL + permissões,
rodar k6 apontando `BASE_URL`, extrair `init_duration` do CloudWatch (L1), e
`--out json` + `--summary-export` (L2/L3). Não há passo de reset de banco — em
contraste explícito com o protocolo do Fargate na mesma página, cujo passo 3 é
`TRUNCATE order_status_history, order_items, orders` (l.11) e cujo F2-S tem a regra de
truncar+repopular (l.20).

**Script mestre de L2/L3.** `09-scripts.md` l.144-190 documenta `l2l3_completo.sh`
(efêmero, rodava de `/tmp`, nunca commitado — mesmo padrão do `bloco_fargate.sh` de
julho). Os 6 passos são: subir runner EC2 → checar SSH → copiar scripts e capturar
Function URLs → `run_scenario()` com checkpointing → loop rodada×runtime×cenário →
parar o runner. `run_scenario()` faz apenas `ssh ... k6 run`, extrai o `latency.json`
e baixa por `scp`. Nenhuma chamada `aws dynamodb` aparece em lugar nenhum do script:

```bash
# 5. Loop: para cada rodada faltante × cada runtime → L2 depois L3
for R in "${ROUNDS[@]}"; do
  for RUNTIME in "${RUNTIMES[@]}"; do
    run_scenario "$RUNTIME" "${URLS[$RUNTIME]}" "l2" "$R" "l2_warm_burst.js" \
      "L2_WARMUP_RATE=15 L2_RATE=31 L2_WARMUP_DURATION=2m L2_DURATION=10m"
    run_scenario "$RUNTIME" "${URLS[$RUNTIME]}" "l3" "$R" "l3_concurrency_burst.js" \
      "L3_WARMUP_RATE=15 L3_RATE=77 L3_BURST_CONCURRENCY=8 L3_WARMUP_DURATION=2m L3_SUSTAIN_DURATION=5m"
  done
done
```

**Orquestrador versionado.** `benchmark/run/run-lambda.sh` (commit `ed54be1`,
"snapshot: pipeline de benchmark Lambda + recoleta L2 (nunca commitado)") é o
equivalente versionado e também não tem nada: o loop `for repetition / for version /
for scenario` (l.100-176) vai direto de um `k6 run` ao próximo, com no máximo um
`sleep "$REST_SECONDS"`. As únicas variáveis com "reset" no nome são `RESET_URL` /
`REQUIRE_COLD_RESET` (l.106-107, l.138-139), que são **reset de cold start** do
ambiente Lambda, não de banco — `benchmark/lib/lambda-invoker.js:51-53` faz um
`http.post(resetUrl)` e o `order-processor` não expõe nenhum endpoint desse tipo
(o único bean é `processOrder`, `SpringOrderProcessorFunction.java:16-18`).

**Recoleta de L2 (agosto/setembro).** Foi abortada sem gerar nenhum dado
(`analysis/l2_recoleta_resumo_final.md` l.3-21: "Nenhum dado oficial foi substituído"),
mas o script deixou registrado por escrito o estado das tabelas
(`scripts/l2_recoleta/provision_infra.sh:57-67`):

> As tabelas DynamoDB default (processed_orders, stock_reservations) já existem no
> ambiente desde 21/jun/2026, criadas fora de qualquer stack CloudFormation, com dados
> reais acumulados (4101 e 12293 itens -- **provavelmente resíduo acumulado da própria
> coleta original de L1/L2/L3, que nunca teve protocolo de reset para o Lambda**).

Ou seja: os dados oficiais de L2/L3 são os originais de julho/2026, rodados contra as
tabelas `processed_orders`/`stock_reservations` originais, sem reset.

## 2. As tabelas ainda existem e o `ItemCount` é o teto do espaço de chaves

`aws dynamodb describe-table --profile pessoal --region us-east-1`, 22/09/2026:

| Tabela | Criada | ItemCount | Bytes | Chave | GSI |
|---|---|---|---|---|---|
| `processed_orders` | 21/06/2026 11:42 | **4.101** | 904.706 | HASH `orderId` | nenhum |
| `stock_reservations` | 21/06/2026 11:42 | **12.293** | 1.682.829 | HASH `orderId` + RANGE `productId` | nenhum |
| `processing-results` | 21/06/2026 11:05 | 0 | 0 | HASH `orderId` | nenhum |

(`processing-results` é órfã de um teste anterior; as tabelas
`*_l2_recoleta` da recoleta abortada não existem mais.)

**Por que 4.101 e não ~500 mil.** `benchmark/lib/workload.js:132` chama
`makeProcessingRequestPayload(iteration + 20000)`, e
`benchmark/lib/data-generator.js:157` monta `orderId: uuidAt(pool, 3000 + index)`, onde
`uuidAt` é `pool[|index| % pool.length]` (l.90-92) sobre um pool de **4.096** UUIDs
gerados por PRNG de seed fixa `20260512` (l.2-3, l.94). Os três cenários (L1, L2, L3) e
as três versões usam o mesmo gerador. Logo o espaço de chaves é fechado: 4.096
`orderId` possíveis e 12.288 pares `(orderId, productId)` possíveis.

`espaco_de_chaves.py` reimplementa o gerador em Python e confirma:

```
  n=  4096 invocacoes -> processed_orders:  4096 chaves | stock_reservations:   8193 chaves
  n= 20354 invocacoes -> processed_orders:  4096 chaves | stock_reservations:  12288 chaves
  n=100000 invocacoes -> processed_orders:  4096 chaves | stock_reservations:  12288 chaves
```

Teto simulado 4.096/12.288 vs. `ItemCount` real 4.101/12.293 — exatamente +5 em ambas,
quase certamente itens de smoke test local com payload diferente. Saturação exata:
`processed_orders` em **4.096** invocações, `stock_reservations` em **12.286**. Uma
rodada de L2 tem 20.354 invocações e uma de L3 tem 27.759 — as duas tabelas atingiam o
teto **dentro da primeira rodada da primeira versão** (~2 min e ~7 min de fase `load` a
31 req/s) e ficaram constantes pelas outras 29 rodadas oficiais.

Então a resposta literal a "a tabela acumulava os pedidos de todas as rodadas?" é:
**não** — ela acumulou até 4.096/12.288 e parou. A partir daí toda rodada só
sobrescreveu as mesmas chaves.

## 3. Todas as operações são acesso por chave — não há análogo do `GET /orders/summary`

O caminho de execução é único (`OrderProcessingService.process`, idêntico nas 3
versões): valida → calcula → `processedOrderRepository.save` →
`stockReservationRepository.saveAll`. Os dois repositórios fazem exclusivamente
`PutItem`:

- `DynamoDbProcessedOrderRepository.java:42-45` (SB) / `:44-47` (Quarkus) — 1 `PutItem`
  em `processed_orders`, chave = `orderId`.
- `DynamoDbStockReservationRepository.java:32-36` (SB) / `:34-38` (Quarkus) — 1 `PutItem`
  por item do pedido (1 a 3 por invocação) em `stock_reservations`, chave =
  `(orderId, productId)`.

`grep` por `scan|Scan|query|Query|getItem|batchWrite|transactWrite|KeyCondition` em
`order-processor/*/src/main/java` retorna **zero** ocorrências fora desses quatro
`putItem`. Não há leitura de nenhum tipo.

Confirmação independente pela IAM role da stack
(`infrastructure/aws/order-processor-stack.yaml:118-126`):

```yaml
              - Sid: WriteOrderProcessorResults
                Effect: Allow
                Action:
                  - dynamodb:PutItem
                Resource:
                  - !GetAtt ProcessedOrdersTable.Arn
                  - !GetAtt StockReservationsTable.Arn
```

A função **não tinha permissão** para `Scan`, `Query`, `GetItem`, `DeleteItem` nem
`BatchWriteItem`. Qualquer tentativa teria falhado com `AccessDeniedException` — e as
rodadas oficiais não têm erro (checks do k6 passaram). As tabelas também não têm GSI
(l.78-103) e são `PAY_PER_REQUEST`, sem capacidade provisionada compartilhada.

Um `PutItem` por chave primária no DynamoDB tem custo O(1) em WCU e latência
independente do tamanho da tabela — é exatamente a propriedade que o RDS do F3 não
tinha, onde o `GET /orders/summary` agregava a tabela `orders` inteira e crescia com ela.
**O mecanismo do F3 não tem análogo aqui.**

## 4. Checagem empírica: a deriva r1→r5 existe, mas não é acúmulo

`tendencia_por_rodada.py` (fonte: os 30 `summary.json` oficiais de
`analysis/lambda/fase4/`). Mediana de `http_req_duration` em ms:

| Cenário | Versão | r1 | r2 | r3 | r4 | r5 | Δ | ρ Spearman | p |
|---|---|---|---|---|---|---|---|---|---|
| L2 | springboot | 26,30 | 26,95 | 27,60 | 28,37 | 29,69 | +3,39 (+12,9%) | +1,00 | 0,000 |
| L2 | quarkus-jvm | 30,47 | 30,81 | 30,97 | 31,43 | 32,52 | +2,05 (+6,7%) | +1,00 | 0,000 |
| L2 | quarkus-native | 28,53 | 28,40 | 29,47 | 29,79 | 30,98 | +2,45 (+8,6%) | +0,90 | 0,037 |
| L3 | springboot | 26,04 | 26,45 | 27,22 | 27,99 | 28,87 | +2,83 (+10,9%) | +1,00 | 0,000 |
| L3 | quarkus-jvm | 29,93 | 30,99 | 30,65 | 32,10 | 32,86 | +2,93 (+9,8%) | +0,90 | 0,037 |
| L3 | quarkus-native | 28,40 | 28,64 | 29,71 | 30,40 | 30,22 | +1,82 (+6,4%) | +0,90 | 0,037 |

A deriva é real e monótona nas 6 séries (~+0,5 a +0,8 ms por rodada). **Mas ela não pode
ser acúmulo de itens**, por três motivos:

1. **A quantidade supostamente causadora era constante.** As tabelas saturaram em
   4.096/12.288 itens dentro da r1 (§2). De r1 a r5 o `ItemCount` não mudou. Uma
   variável constante não explica uma tendência monótona.
2. **Dentro de uma rodada não há deriva.** Mediana por bloco de 2.048 iterações da fase
   `load` (fonte: `l2-springboot-r1-raw.json`, 18.601 escritas):
   `[27,34 · 25,73 · 25,70 · 26,47 · 25,98 · 25,81 · 26,12 · 26,32 · 25,83]` — plana
   (o 1º bloco é mais alto por JIT residual, depois estabiliza). É exatamente aí, se em
   algum lugar, que o efeito de tamanho apareceria mais forte. A r5 tem a mesma forma
   num patamar mais alto: `[33,01 · 29,32 · 28,82 · 28,61 · 28,46 · 28,56 · 29,16 · 30,15 · 29,59]`.
3. **O mecanismo não existe** (§3): `PutItem` por chave, sem leitura, sem GSI, sem
   permissão para varredura.

**O que a deriva é, então: em aberto.** Ela é *common-mode* — afeta as 3 versões e os 2
cenários com magnitude parecida — e não é um degrau na fronteira de sessão (r1-r3 na
madrugada de 05-06/jul, r4-r5 na manhã de 16/jul; o salto r3→r4 (+0,77 ms) é igual aos
saltos dentro de cada sessão). Candidatos plausíveis não investigados aqui: carga
regional da AWS por horário, estado do runner EC2, população de ambientes de execução
Lambda. O que importa para o TCC é que ela **não inverte nenhuma comparação**: o gap
entre versões permanece estável e com o mesmo sinal em todas as rodadas —

| Gap (ms) | r1 | r2 | r3 | r4 | r5 |
|---|---|---|---|---|---|
| L2 quarkus-jvm − springboot | 4,17 | 3,86 | 3,38 | 3,06 | 2,83 |
| L2 quarkus-native − springboot | 2,23 | 1,45 | 1,87 | 1,42 | 1,30 |
| L3 quarkus-jvm − springboot | 3,89 | 4,54 | 3,43 | 4,11 | 3,99 |
| L3 quarkus-native − springboot | 2,36 | 2,19 | 2,49 | 2,41 | 1,35 |

— e as 3 versões de uma mesma rodada rodavam no mesmo bloco de ~1 h, então a deriva é
ortogonal à variável de interesse.

## 5. L1 especificamente

L1 escreve nas mesmas tabelas pelo mesmo caminho (`l1_sparse_coldstart.js:47` chama o
mesmo `runProcessOrderOperation`), mas com ~11 invocações por versão espaçadas de 15 min
— 33 escritas no total, sobre chaves já existentes. Não há limpeza, e o objeto de medida
de L1 é o `init_duration` extraído do CloudWatch (`03-methodology.md` l.27), que é o
tempo de inicialização do ambiente, anterior a qualquer chamada ao DynamoDB. Efeito
nulo por construção.

## Para o texto da metodologia

Descrição fiel do que aconteceu, se for útil:

> Nos cenários do Lambda (L1, L2 e L3) não houve reinicialização de estado das tabelas
> do DynamoDB entre repetições. Diferentemente dos cenários do Fargate — em que a
> agregação do `GET /orders/summary` sobre a tabela `orders` torna o custo dependente do
> volume armazenado —, o `order-processor` executa exclusivamente operações de escrita
> por chave primária (`PutItem`), cujo custo e latência no DynamoDB independem do número
> de itens da tabela; a própria política IAM da função concede apenas `dynamodb:PutItem`.
> Além disso, os identificadores de pedido são gerados a partir de um conjunto fechado e
> determinístico de 4.096 UUIDs, de modo que repetições sucessivas sobrescrevem as mesmas
> chaves em vez de acrescentar novas: as tabelas atingiram seu tamanho máximo
> (4.096 e 12.288 itens) ainda durante a primeira repetição e permaneceram constantes ao
> longo de toda a campanha. A ausência de reinicialização, portanto, não constitui
> confundidor para as medições de L1, L2 e L3.

## Arquivos gerados

- `espaco_de_chaves.py` — reimplementa o gerador de UUIDs do k6 e calcula o teto de
  chaves distintas por tabela.
- `tendencia_por_rodada.py` — teste de tendência r1→r5 e perfil intra-rodada.
- `tendencia_por_rodada.csv` — medianas/p95/n por rodada, Δ, ρ de Spearman e slope.
