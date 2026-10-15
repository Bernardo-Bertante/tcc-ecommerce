# De onde vem o custo da primeira chamada do Quarkus JVM na Lambda (teste "lazy")

**EXPLORATÓRIO — fora do desenho experimental oficial. Não substitui nem altera os dados oficiais do L1.**

- Execução: 29/09/2026, 22:17:55–22:48:23 UTC (RUN_ID `full-20260929T221755Z`); fumaça no mesmo dia
  (`smoke-20260929T221245Z`, 9 amostras, não usadas aqui). Registro completo: `NOTAS_execucao.md`.
- Conta `776648109551`, us-east-1. Recursos criados e já apagados (todos `exp-lazy-*`, tag `Projeto=tcc-exp-lazy`):
  - 3 funções: `exp-lazy-qj-v0`, `exp-lazy-qj-v1` e `exp-lazy-qj-v2`;
  - 2 tabelas DynamoDB;
  - roles `exp-lazy-role` e `exp-lazy-driver-role`, mais o *instance profile* do driver;
  - EC2 `exp-lazy-driver`;
  - bucket `exp-lazy-results-776648109551`;
  - 3 *log groups*.

  Verificação final em 30/09 05:47 -03:00: nenhum recurso `exp-lazy-*` restante.
- Dados: `resultados_full-20260929T221755Z/`.
  - `samples.jsonl` / `samples_final.csv`: 1 linha por invocação.
  - `invocations.csv`: linhas `REPORT`/`INIT_START` do CloudWatch.
  - `points.csv`: linhas `EXP_LAZY`.
  - `intervals.csv`, `phases.csv`, `summary.json`: agregados gerados por `analyze.py`.
  - `raw/logs_*.jsonl.gz`: todos os eventos brutos do CloudWatch.

  Referência oficial: `l1_duration_postinit.csv` (cópia de `analysis/lambda/l1/`, só lida).
- Todo número deste arquivo sai desses arquivos. Salvo quando indicado, são **medianas, n = 30 por variante**.

## Diferenças em relação ao L1 oficial

| Aspecto | L1 oficial (03/07/2026) | Este teste |
|---|---|---|
| Função e tabelas | `order-processor-quarkus-jvm`; `processed_orders`/`stock_reservations` | Cópias `exp-lazy-qj-*`; tabelas `exp-lazy-*` (mesmo esquema); role própria |
| Variáveis de ambiente | nenhuma | `PROCESSED_ORDERS_TABLE`, `STOCK_RESERVATIONS_TABLE`, `COLD_TOKEN` (V2: + `EXP_LAZY_PREP=1`) |
| Runtime | java:21.v68 (Auto) | java:21.v68 fixado (Manual), conferido no `INIT_START` das 90 amostras |
| Cold start | Expiração natural, 1 chamada a cada 15 min | **Forçado:** troca de `COLD_TOKEN`, espera `Successful` (mediana 2,27 s), invoca |
| Invocação | Function URL (k6) | `Invoke` direto da API com evento no formato Function URL (mesmo caminho no mapper) |
| Payload | `makeProcessingRequestPayload(20000+k)`, k = 0..10 | O mesmo, gerado pelo próprio `data-generator.js`; bloco b usa k = b mod 11 |
| Amostragem | n = 10 válidas | 30 blocos com V0/V1/V2 embaralhados (seed 20260929), concorrência 1, + 1 chamada quente por amostra |
| Código | zip oficial | V0 = zip oficial (mesmo sha256); V1/V2 = mesmo bytecode + instrumentação (zip próprio) |

## 1. Variantes

- **V0 (controle):** o pacote publicado, sem mudanças. `CodeSha256 qqGaGUSyL1rtWwcwOeIMNhFYfsW+HvIh8QiUTPe+WME=`, igual ao da função oficial.
- **V1 (instrumentada):** um build local cujo conteúdo é idêntico ao oficial (303/303 entradas), mais o seguinte:
  - um *wrapper* fino do `FunqyStreamHandler` (`LazyProbeHandler`);
  - marcas `System.nanoTime()` nos construtores, no handler, no service e no produtor do `DynamoDbClient`;
  - um `ExecutionInterceptor` do SDK, que separa a transmissão HTTP do resto da chamada.

  Cada marca registra classes carregadas, tempo de JIT, tempo de GC, CPU do processo, CPU da thread e `/proc/stat`. `CodeSha256 RTtmKw35s7nPa1IzWSFMtzk8lznzf9Dy72LqBZdfSn4=`. Nenhuma flag de JVM foi adicionada. As 60 amostras V1/V2 registram os mesmos argumentos da JVM que a Lambda impõe (`-XX:+TieredCompilation -XX:TieredStopAtLevel=1 -XX:+UseSerialGC …`), com `JAVA_TOOL_OPTIONS` vazio.
- **V2 (preparação antecipada):** o **mesmo zip da V1**, com `EXP_LAZY_PREP=1`. Um `@Observes StartupEvent` roda no init. O boot do Quarkus já acontece no init, porque o build ativa por padrão o *full warm-up* do SnapStart do Quarkus. A preparação faz, em ordem:
  1. instancia os beans da aplicação;
  2. faz `readTree` + `toProcessingRequest` de um evento de marcação;
  3. faz 1 `GetItem` de uma chave inexistente;
  4. faz `service.process()` de um pedido de marcação com `orderId 00000000-0000-0000-0000-000000000000`, ou seja, 1 `PutItem` em cada tabela no mesmo caminho da primeira chamada (os itens de marcação não entram em nenhuma métrica);
  5. serializa o resultado.

  Código-fonte: `variante_v1v2_src/` e `variante_v1v2.patch`.

## 2. Resultados por variante (ms)

Mediana [Q1–Q3], mín.–máx.; n = 30 (L1: n = 10).

| Variante | Init Duration | Duration | Init + Duration (= Billed) | Duration da 2ª chamada |
|---|---|---|---|---|
| V0 | 1.454,8 [1.393,9–1.804,0] 1.196,1–1.990,2 | 5.500,8 [5.359,4–5.715,7] 3.610,7–6.004,7 | 6.968,3 [6.772,2–7.420,6] | 73,3 [54,8–91,5] |
| V1 | 1.459,6 [1.403,3–1.841,9] 1.146,8–1.972,7 | 5.432,5 [5.326,1–5.544,5] 4.685,5–5.871,3 | 6.904,3 [6.729,1–7.350,6] | 96,4 [58,0–119,7] |
| V2 | 2.927,2 [2.863,8–3.184,2] 2.766,2–3.678,1 | 347,1 [328,4–394,5] 306,0–447,1 | 3.298,0 [3.202,1–3.616,5] | 94,7 [71,1–122,5] |
| L1 oficial QJ | 1.382,6 [1.366,5–1.406,4] 1.314,9–1.470,1 | 5.620,4 [5.468,8–5.729,8] 5.315,1–5.842,5 | 6.999,7 [6.896,7–7.141,4] | — |

Outros dados:
- `Billed Duration` ficou igual a `Init + Duration` arredondado em todas as amostras (V0 6.969; V1 6.905; V2 3.298,5).
- `Max Memory Used`: V0 185, V1 186, V2 187 MB; L1 184–185 MB.
- O intervalo entre o fim do init e o `START` teve mediana de 3,8–3,9 ms nas três variantes. Não houve pré-inicialização do ambiente.

## 3. Validação

**Integridade:**
- 90/90 cold starts válidos na 1ª tentativa, e as 90 chamadas quentes também. As 180 invocações retornaram 200, sem `FunctionError`.
- As 180 linhas `REPORT` foram encontradas no CloudWatch.
- Zero ocorrências de `AccessDenied`, `sdk_fail` e `prep_fail`.
- A ordem executada é igual ao sorteio, e cada bloco tem V0, V1 e V2 uma vez.
- A posição no bloco ficou desbalanceada por acaso: a primeira posição saiu 13× para V0, 11× para V2 e 6× para V1.

**Fumaça (`infra/smoke_verificacao.txt`):**
- gravações só nas tabelas `exp-lazy-*`;
- ConsumedWriteCapacityUnits = 0 nas tabelas oficiais durante a janela;
- funções oficiais com sha, RevisionId e LastModified iguais ao snapshot de antes.

**Controle, V0 × L1 oficial.** A regra pré-definida era |diferença das medianas| ≤ 10%. **Resultado: OK.**
- Duration: 5.500,8 × 5.620,4 ms, ou −2,1%. O intervalo bootstrap 95% da diferença, [−280,6; +92,1], inclui zero.
- Init Duration: 1.454,8 × 1.382,6 ms, ou +5,2%. O intervalo bootstrap [+9,9; +355,0] **não** inclui zero. A V0 tem cauda superior mais pesada: o Q3 de 1.804 ms passa do máximo do L1 (1.470 ms).
- Causa provável dessa diferença no Init: o cold start forçado logo após a atualização de configuração, contra a expiração natural do L1. Não foi investigada. A diferença não afeta o objeto do teste (o Duration), que o método reproduz.

**Instrumentação, V1 × V0.** Não distorce.
- Duration: −68,3 ms (−1,2%), bootstrap [−220,3; +53,5].
- Init: +4,8 ms (+0,3%).
- Soma: −63,9 ms (−0,9%).
- Na chamada quente, V1 fica +23,1 ms acima (bootstrap [−13,0; +49,2]), compatível com o custo de imprimir cerca de 20 linhas `EXP_LAZY`.

## 4. Decomposição da primeira chamada (V1)

O intervalo entre a entrada do *wrapper* (`w_in`) e a saída (`w_out`) cobre 99% do `Duration`. Antes dele (`START`→`w_in`) passam 3,0 ms, e depois (`w_out`→fim) 39,4 ms. Medianas por intervalo (fonte: `intervals.csv`, fase `inv1`):

| Trecho da 1ª chamada | Tempo (ms) | Classes carregadas | JIT (ms) | CPU da thread (ms) |
|---|---|---|---|---|
| Criação do `DynamoDbClient` (`client_build_in → out`), disparada pelo 1º uso do repositório | **2.759,7** | 1.524 | 740 | 575,5 |
| 1º `PutItem`: repositório → `beforeExecution` | 325,3 | 282 | 104 | 76,8 |
| 1º `PutItem`: `beforeExecution → beforeTransmission` (serialização, credenciais, assinatura) | 420,4 | 392 | 26 | 107,1 |
| 1º `PutItem`: **transmissão HTTP** (`beforeTransmission → afterTransmission`) | **1.255,7** | 831 | 476 | 246,2 |
| 1º `PutItem`: `afterTransmission → afterExecution` | 100,5 | 72 | 16 | 22,9 |
| Jackson (`treeToValue` do pedido) | 201,0 | 110 | 28 | 43,4 |
| Saída do Funqy (`h_out → w_out`) | 122,1 | 45 | 43 | 25,8 |
| Funqy + criação do bean da função (`w_in → ctor_function`) | 47,4 | 36 | 1 | 15,9 |
| 2º `PutItem` (só a transmissão) | 25,3 | 2 | 1 | 2,8 |

Sobre esses números:
- **Participação na primeira chamada (soma das medianas, que não é exatamente a mediana da soma):**
  - build do cliente do SDK: ~51%;
  - primeiro `PutItem` completo: 2.101,9 ms, ~39%;
  - Jackson: ~4%;
  - saída do Funqy: ~2%.
- **Os beans da aplicação custam pouco:** a criação de cada um leva de décimos de ms a ~15 ms.
- **Totais da fase `inv1`:** tempo de parede 5.401,3 ms; 3.331 classes carregadas; 1.427,5 ms de JIT acumulado; 252,5 ms de GC; CPU da thread principal 1.137,7 ms; CPU do processo 1.540 ms.

## 5. Deslocamento para o init (V2 × V1)

| | V1 | V2 | Diferença (bootstrap 95%) |
|---|---|---|---|
| Init Duration | 1.459,6 | 2.927,2 | **+1.467,6** (+100,6%) [+1.236,8; +1.629,6] |
| Duration | 5.432,5 | 347,1 | **−5.085,4** (−93,6%) [−5.164,3; −4.996,6] |
| Init + Duration | 6.904,3 | 3.298,0 | **−3.606,3** (−52,2%) [−3.866,4; −3.391,6] |
| Duration da 2ª chamada | 96,4 | 94,7 | −1,7 [−26,0; +36,6] |

**O custo migrou para o init, e a soma caiu pela metade.** O trabalho em si não diminuiu: a CPU consumida é praticamente a mesma. O que muda é o tempo de parede, porque as duas fases recebem CPU diferente (seção 6, H-CPU):

- **CPU do processo:**
  - V1 na 1ª chamada: 1.540 ms;
  - V2: +1.420 ms a mais no init (init da V2 2.490 ms − init da V1 1.070 ms) + 90 ms na 1ª chamada = 1.510 ms.
- **As mesmas operações nas duas fases** (V1 no invoke × V2 no init):

  | Operação | Invoke V1 (ms) | Init V2 (ms) | Razão | CPU da thread (invoke × init, ms) |
  |---|---|---|---|---|
  | Build do cliente | 2.759,7 | 730,7 | 3,78× | 575,5 × 514,6 |
  | Serialização, credenciais e assinatura | 420,4 | 108,7 | 3,87× | — |
  | 1ª transmissão HTTP | 1.255,7 | 351,0 | 3,58× | 246,2 × 227,0 |

  A 1ª transmissão compara o `PutItem` da V1 com o `GetItem` da V2; as duas carregam as mesmas ~830 classes. O Jackson segue o mesmo padrão: 201,0 × 58,7 ms, razão 3,43×.

**O que sobra na V2 (347,1 ms):**
- saída do Funqy: 153,2 ms. Não foi exercitada pela preparação, que serializou pelo `ObjectMapper`, não pelo caminho do Funqy;
- GC: 104 ms. O heap já vinha ocupado pela preparação;
- entrada até o handler: 21,7 ms;
- `w_out` → fim: ~43 ms;
- cada `PutItem`: ~18–24 ms, que é o tempo de regime (na V1, a 2ª chamada leva 11–22 ms por `PutItem`).

**Custo da preparação no init:** 1.444 ms de tempo de parede, na diferença entre as fases de init das duas variantes (2.546,0 × 1.101,6 ms). Nisso, o build do cliente leva 730,7 ms e o primeiro `GetItem`, 351,0 ms. O init ficou longe do limite de 10 s: máximo de 3.678,1 ms.

## 6. Resposta às hipóteses

| Hipótese | Veredito | Certeza | Números |
|---|---|---|---|
| **H-lazy**: componentes criados só no 1º uso | **Sustentada** | Alta (dentro do escopo exploratório) | A cadeia de proxies `@ApplicationScoped` adia o produtor `@Singleton` do `DynamoDbClient` até o 1º uso do repositório: 2.759,7 ms dentro da chamada. Com a preparação no init, o Duration cai 93,6% (5.432,5 → 347,1) e o custo aparece no Init (+1.467,6). O pesado não é a injeção de dependências dos beans da aplicação (ms), e sim o **cliente do SDK e a primeira requisição** que eles criam por último. |
| **H-classes**: carregamento de classes na 1ª chamada | **Sustentada como componente, não separável de H-lazy** | Média | 3.331 classes carregadas na 1ª chamada da V1 contra 37 na V2; 1.524 no build do cliente e ~1.577 no 1º `PutItem`. As classes são carregadas porque os objetos são criados na hora. Sem JFR ou log de classes (fora do escopo: nenhuma flag nova de JVM), não há como separar o tempo de carregar do tempo de executar a inicialização. |
| **H-interpretado**: código ainda interpretado/C1 | **Não sustentada como causa principal; contribuição residual não separável** | Média | Na V2, os caminhos executados uma única vez na preparação já rodam em regime na 1ª chamada real (`PutItem` 18–24 ms contra 11–22 ms na 2ª chamada da V1; Duration da 2ª chamada V1 × V2 = 96,4 × 94,7). Se a execução interpretada dominasse, a 1ª chamada da V2 continuaria lenta. O JIT acumula 1.427,5 ms de compilação na 1ª chamada da V1 e disputa a CPU com a thread principal, então faz parte do custo, sem quantificação isolada. |
| **H-rede**: DNS/TCP/TLS na 1ª conexão | **Não sustentada como causa principal; resíduo não separável** | Média | A 1ª transmissão leva 1.255,7 ms no invoke e 351,0 ms no init: escala 3,58×, como os trechos puros de CPU (3,43–3,87×), e carrega 831 classes (pilha TLS/HTTP). As transmissões seguintes levam ~11–25 ms (medianas por chamada). A latência de rede em si deve ser da ordem de dezenas de ms, mas medir isso exigiria captura de pacotes na Lambda. |
| **H-CPU**: init com mais CPU que o invoke | **Sustentada empiricamente; mecanismo não documentado pela AWS** | Alta para o fenômeno, baixa para a causa | CPU do processo por tempo de parede: init 0,98 (V1, IQR 0,91–0,98; V2 0,97) contra 1ª chamada 0,29 (IQR 0,28–0,29), próximo de 512/1769 = 0,29 vCPU. `/proc/stat` fração ocupada: 0,47 de 2 vCPUs no init contra 0,11–0,12 no invoke. `steal` ≈ 0: o teto não aparece como *steal* dentro da VM, só na razão CPU/tempo. Mesmas operações 3,4–4,6× mais rápidas no init com a mesma CPU da thread (seção 5). **Fontes oficiais consultadas não confirmam nem negam:** a página do ciclo de vida da execução (lambda-runtime-environment.html) não menciona CPU por fase; o blog da AWS de 07/08/2025 (Bhattacharya e Wen) só diz que mais memória dá mais CPU "para inicializar e executar". É um confundidor direto de V2 × V1: a queda da soma (−52%) vem da mudança de fase, não de menos trabalho. |

**O que continua sem explicação:**
- quanto das ~2,1 s do primeiro `PutItem` é carregamento de classes, quanto é JIT disputando a CPU e quanto é execução interpretada;
- a latência de rede exata do primeiro handshake TLS;
- o Init da V0 um pouco maior que o do L1 (+5,2%);
- os 153 ms da saída do Funqy e os 104 ms de GC que sobram na V2.

## 7. Limitações

- Amostra exploratória (n = 30 por variante, uma sessão, um dia). Os intervalos bootstrap são descritivos, não confirmatórios.
- As cópias usam outras tabelas (mesmo esquema), outra role (com `GetItem` a mais), variáveis de ambiente que a oficial não tem e invocação direta em vez de Function URL. O cold start é forçado, não por expiração natural. V0 × L1 mostra que isso preserva o Duration, mas o Init ficou +5,2%.
- V1/V2 trocam o Handler por um *wrapper* e acrescentam instrumentação. V1 × V0 mostra efeito ≤ 1,2% no Duration.
- A conclusão sobre CPU por fase é medida de dentro da VM (razão CPU/tempo e `/proc/stat`). A política de alocação da AWS não é documentada e pode mudar.
- O teste é só sobre o Quarkus JVM. **Nada aqui permite concluir sobre Spring Boot ou Native.**
- Nada disso substitui os dados oficiais do L1, que não foram tocados.

## 8. Implicação para o texto (sem editar; arquivos mais recentes em `~/Downloads`)

1. **`lambda(8).tex`, linha 49** ("cuja causa não foi investigada neste trabalho. Uma hipótese compatível com os dados é…"). Pode deixar de ser hipótese e virar achado de **investigação exploratória complementar, fora do desenho oficial**. Conteúdo possível:
   - o Duration da 1ª chamada vem sobretudo da criação tardia do cliente do SDK do DynamoDB (~2,8 s) e da primeira requisição (~2,1 s), com ~3.300 classes carregadas;
   - antecipar esse trabalho para o init reduz o Duration em ~94% e a soma em ~52%.

   A redação atual ("carregamento de classes e inicialização adiada para o primeiro uso") está correta na direção, mas é vaga quanto ao componente.
2. **`lambda(8).tex`, linha 67.** Nenhum número muda; os dados oficiais seguem os mesmos. Se o texto quiser explicar por que a inversão do Billed Duration acontece, a H-CPU é a peça que faltava: o mesmo trabalho custa ~3,5× mais tempo no invoke do que no init. Deve entrar com a ressalva de que é medida exploratória e de que a AWS não documenta a diferença.
3. **`discussao(30).tex`, linha 95** (descarte da *lazy initialization* para a inversão no **regime aquecido**). A conclusão continua de pé e agora tem evidência direta: a preparação não muda a 2ª chamada (96,4 × 94,7 ms). Mas a **justificativa** ("se fosse lazy, deveria se manifestar também no Native") fica em tensão com este teste, que mostra *lazy* como mecanismo da 1ª chamada no JVM. Sugestão: trocar o argumento pelo dado da 2ª chamada e deixar claro que o descarte vale para o regime aquecido, não para o cold start. (Este teste não diz nada sobre o Native.)
4. **`discussao(30).tex`, linha 15** (ressalva de escopo sobre H1a). Pode citar o achado ao remeter à Seção de inversão. Não precisa mudar a conclusão.
5. **Sugestão para `08-known-problems`:** registrar como entrada nova, com ressalva de escopo no mesmo padrão das #28 e #33.
