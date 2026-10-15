# RESULTADOS_JIT_FARGATE — PRELIMINAR (gerado automaticamente)

**Exploratório, fora do desenho experimental oficial.** Gerado no exp-jit-runner em 2026-09-30 03:04 UTC, sem validação humana. Não usar como dado oficial.

Diferenças em relação ao oficial: RDS separado (`exp-jit-postgres`), `-XX:+PrintCompilation`, awslogs non-blocking com buffer de 25 MB explícito, senha via Secrets Manager, ECS Exec ligado. Latências deste teste não são comparáveis às oficiais e não são reportadas.

## Rodadas (task, imagem, janela de carga)

| cenário | versão | task | imageDigest | startedAt | início carga (UTC) | carga (min) | requisições |
|---|---|---|---|---|---|---|---|
| f1 | quarkus-jvm | 70d0e801c831413380b129172b0d3493 | sha256:abec3583cd78 | 2026-09-29T23:18:17.188000+00:00 | 23:18:40 | 23.9 | 71027 |
| f1 | springboot | a7695a431fee44b0b1c8e2fffe2def7c | sha256:276548dd7956 | 2026-09-29T22:49:42.218000+00:00 | 22:50:19 | 23.9 | 70996 |
| f2 | quarkus-jvm | 2fe6e041c12e45dfb8f28ac198441e6e | sha256:abec3583cd78 | 2026-09-30T00:37:17.772000+00:00 | 00:38:44 | 44.5 | 242724 |
| f2 | springboot | c598bd825a024bd48b98a927895dab78 | sha256:276548dd7956 | 2026-09-29T23:46:31.629000+00:00 | 23:48:12 | 44.5 | 242724 |
| f2s | quarkus-jvm | d42a68275a604e6b92b5b5b169c31f42 | sha256:abec3583cd78 | 2026-09-30T01:45:37.295000+00:00 | 01:46:00 | 14.0 | 6480 |
| f2s | springboot | 8a6a9cdcf317485bb297f53c3d9bc942 | sha256:276548dd7956 | 2026-09-30T01:27:12.693000+00:00 | 01:27:44 | 13.9 | 6479 |
| f3 | quarkus-jvm | c9b5e215398d4d14a59d050c6a225946 | sha256:abec3583cd78 | 2026-09-30T02:34:39.295000+00:00 | 02:36:06 | 25.0 | 233855 |
| f3 | springboot | cd804844e40c4a0d82136655ece1090a | sha256:276548dd7956 | 2026-09-30T02:03:48.302000+00:00 | 02:05:27 | 25.0 | 233855 |

## P1 — métodos por nível ao fim da carga (log) e no jcmd

| cenário | versão | n1 | n2 | n3 | n4 | jcmd n4 | OSR n4 vivas | distintos que atingiram n4 | n4 antes da carga | 100º n4 (s) | 1000º n4 (s) | último n4 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f1 | quarkus-jvm | 997 | 340 | 3659 | 1929 | 1931 | 24 | 1963 | 549 | -21.5 | 64.4 | 1435.3 |
| f1 | springboot | 1366 | 1244 | 4319 | 3394 | 3392 | 27 | 3452 | 1027 | -35.9 | -1.3 | 1371.5 |
| f2 | quarkus-jvm | 1054 | 600 | 3672 | 2102 | 2104 | 27 | 2130 | 512 | -84.6 | 15.4 | 2606.1 |
| f2 | springboot | 1386 | 1926 | 3568 | 3574 | 3585 | 26 | 3622 | 1124 | -99.4 | -1.8 | 2428.0 |
| f2s | quarkus-jvm | 926 | 377 | 3254 | 1325 | 1315 | 24 | 1341 | 601 | -21.9 | 88.6 | 813.9 |
| f2s | springboot | 1215 | 1089 | 4113 | 2357 | 2357 | 27 | 2400 | 1091 | -30.3 | -3.8 | 818.2 |
| f3 | quarkus-jvm | 1045 | 446 | 3772 | 2142 | 2146 | 31 | 2174 | 566 | -85.7 | 13.6 | 1470.3 |
| f3 | springboot | 1387 | 1828 | 3666 | 3574 | 3581 | 20 | 3617 | 1084 | -97.6 | -1.9 | 1429.8 |

Tempos em segundos desde a 1ª requisição da carga (negativo = antes da carga, no boot/setup).

## P2 — caminho do GET /orders/summary (métodos com certeza = certo)

| cenário | versão | atingiu | atingiu só no fim | atingiu antes da carga | não atingiu | não compilado |
|---|---|---|---|---|---|---|
| f1 | quarkus-jvm | 2 | 1 | 0 | 39 | 0 |
| f1 | springboot | 4 | 0 | 0 | 34 | 0 |
| f2 | quarkus-jvm | 5 | 0 | 0 | 38 | 0 |
| f2 | springboot | 7 | 0 | 0 | 32 | 0 |
| f2s | quarkus-jvm | 4 | 2 | 0 | 37 | 0 |
| f2s | springboot | 6 | 4 | 0 | 29 | 0 |
| f3 | quarkus-jvm | 5 | 0 | 0 | 37 | 0 |
| f3 | springboot | 8 | 0 | 0 | 31 | 0 |

Detalhe por método: `csv/summary_path_nivel.csv`. "Só no fim" = 1º nível 4 depois de 80% da janela de carga.

Métodos do caminho que atingiram nível 4 (t = s desde o início da carga; chamadas = summary até então):

| cenário | versão | método | t 1º n4 (s) | chamadas summary | leitura |
|---|---|---|---|---|---|
| f1 | quarkus-jvm | OrderService::fillMissingStatuses | 1095.4 | 994 | atingiu |
| f1 | quarkus-jvm | OrderService::normalizeMoney | 70.5 | 20 | atingiu |
| f1 | quarkus-jvm | OrderSummaryRepository::validateAndBuildDateRange | 1178.7 | 1074 | atingiu so no fim |
| f1 | springboot | OrderService::fillMissingStatuses | 1095.8 | 995 | atingiu |
| f1 | springboot | OrderService::normalizeMoney | 360.3 | 288 | atingiu |
| f1 | springboot | OrderSummaryRepositoryImpl::toLong | 433.2 | 359 | atingiu |
| f1 | springboot | OrderSummaryRepositoryImpl::toBigDecimal | 527.0 | 448 | atingiu |
| f2 | quarkus-jvm | OrderService::fillMissingStatuses | 841.2 | 995 | atingiu |
| f2 | quarkus-jvm | OrderService::normalizeMoney | 104.1 | 100 | atingiu |
| f2 | quarkus-jvm | OrderSummaryRepository::validateAndBuildDateRange | 896.4 | 1100 | atingiu |
| f2 | quarkus-jvm | OrderSummaryRepository::mapTopCustomers | 1283.0 | 1842 | atingiu |
| f2 | quarkus-jvm | OrderSummaryResponse$TopCustomerSummary::<init> | 1296.5 | 1870 | atingiu |
| f2 | springboot | OrderService::fillMissingStatuses | 841.0 | 994 | atingiu |
| f2 | springboot | OrderSummaryRepositoryImpl::validateAndBuildDateRange | 1109.7 | 1510 | atingiu |
| f2 | springboot | OrderSummaryRepositoryImpl::initializeStatusCounts | 1923.2 | 3072 | atingiu |
| f2 | springboot | OrderSummaryRepositoryImpl::toLong | 499.7 | 478 | atingiu |
| f2 | springboot | OrderSummaryRepositoryImpl::toBigDecimal | 761.8 | 843 | atingiu |
| f2 | springboot | OrderSummaryRepositoryImpl::lambda$countOrdersByStatusInDateRange$4 | 1279.6 | 1836 | atingiu |
| f2 | springboot | OrderSummaryRepositoryImpl::lambda$findTopCustomersByRevenue$6 | 560.1 | 537 | atingiu |
| f2s | quarkus-jvm | OrderResource$quarkusrestinvoker$getSummary_55c945abd81bba952c573e53b366297cfeda8264::invoke | 716.0 | 5631 | atingiu so no fim |
| f2s | quarkus-jvm | OrderService::fillMissingStatuses | 136.6 | 995 | atingiu |
| f2s | quarkus-jvm | OrderSummaryRepository_ClientProxy::sumRevenueByDateRange | 716.2 | 5632 | atingiu so no fim |
| f2s | quarkus-jvm | OrderSummaryRepository::validateAndBuildDateRange | 146.5 | 1075 | atingiu |
| f2s | quarkus-jvm | OrderSummaryRepository::mapStatusCounts | 385.4 | 2986 | atingiu |
| f2s | quarkus-jvm | OrderSummaryRepository::mapTopCustomers | 242.6 | 1843 | atingiu |
| f2s | springboot | OrderService::fillMissingStatuses | 136.7 | 995 | atingiu |
| f2s | springboot | OrderService::calculateAverageOrderValue | 700.2 | 5503 | atingiu so no fim |
| f2s | springboot | OrderSummaryRepositoryImpl::countOrdersByDateRange | 716.1 | 5631 | atingiu so no fim |
| f2s | springboot | OrderSummaryRepositoryImpl::findTopCustomersByRevenue | 716.1 | 5631 | atingiu so no fim |
| f2s | springboot | OrderSummaryRepositoryImpl::validateAndBuildDateRange | 175.3 | 1305 | atingiu |
| f2s | springboot | OrderSummaryRepositoryImpl::initializeStatusCounts | 396.2 | 3072 | atingiu |
| f2s | springboot | OrderSummaryRepositoryImpl::toLong | 48.4 | 289 | atingiu |
| f2s | springboot | OrderSummaryRepositoryImpl::toBigDecimal | 64.7 | 419 | atingiu |
| f2s | springboot | OrderSummaryRepositoryImpl::lambda$countOrdersByStatusInDateRange$4 | 145.5 | 1066 | atingiu |
| f2s | springboot | OrderSummaryResponse::getOrdersByStatus | 716.2 | 5632 | atingiu so no fim |
| f3 | quarkus-jvm | OrderService::fillMissingStatuses | 495.5 | 995 | atingiu |
| f3 | quarkus-jvm | OrderService::normalizeMoney | 104.1 | 98 | atingiu |
| f3 | quarkus-jvm | OrderSummaryRepository::validateAndBuildDateRange | 512.1 | 1074 | atingiu |
| f3 | quarkus-jvm | OrderSummaryRepository::mapTopCustomers | 672.3 | 1844 | atingiu |
| f3 | quarkus-jvm | OrderSummaryResponse$TopCustomerSummary::<init> | 677.7 | 1870 | atingiu |
| f3 | springboot | OrderService::fillMissingStatuses | 495.3 | 995 | atingiu |
| f3 | springboot | OrderService::normalizeMoney | 76.8 | 73 | atingiu |
| f3 | springboot | OrderSummaryRepositoryImpl::validateAndBuildDateRange | 517.2 | 1100 | atingiu |
| f3 | springboot | OrderSummaryRepositoryImpl::initializeStatusCounts | 928.1 | 3072 | atingiu |
| f3 | springboot | OrderSummaryRepositoryImpl::toLong | 346.5 | 366 | atingiu |
| f3 | springboot | OrderSummaryRepositoryImpl::toBigDecimal | 374.1 | 447 | atingiu |
| f3 | springboot | OrderSummaryRepositoryImpl::lambda$countOrdersByStatusInDateRange$4 | 670.3 | 1834 | atingiu |
| f3 | springboot | OrderSummaryRepositoryImpl::lambda$findTopCustomersByRevenue$6 | 398.3 | 536 | atingiu |

## P3 — deoptimização (linhas `made not entrant`)

| cenário | versão | total | durante a carga | de n4 | caminho summary | caminho summary na carga |
|---|---|---|---|---|---|---|
| f1 | quarkus-jvm | 2663 | 1867 | 214 | 6 | 6 |
| f1 | springboot | 5808 | 3426 | 417 | 9 | 8 |
| f2 | quarkus-jvm | 3099 | 2256 | 252 | 10 | 10 |
| f2 | springboot | 7420 | 5018 | 351 | 19 | 18 |
| f2s | quarkus-jvm | 1819 | 962 | 106 | 8 | 8 |
| f2s | springboot | 4052 | 1889 | 274 | 15 | 14 |
| f3 | quarkus-jvm | 2942 | 2161 | 250 | 9 | 9 |
| f3 | springboot | 6845 | 4622 | 365 | 16 | 15 |

## Integridade da captura

| cenário | versão | eventos | compilações | não parseadas | ids sem linha | maior lacuna | codelist | codelist ausentes no log | JVMs no log | spread relógio (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| f1 | quarkus-jvm | 13547 | 10790 | 0 | 22 | 5 | 10409 | 0 | 1 | 1 |
| f1 | springboot | 23540 | 17608 | 0 | 136 | 10 | 16097 | 0 | 1 | 1 |
| f2 | quarkus-jvm | 15005 | 11794 | 0 | 34 | 5 | 11422 | 0 | 1 | 1 |
| f2 | springboot | 26968 | 19426 | 1 | 412 | 29 | 17843 | 0 | 1 | 1 |
| f2s | quarkus-jvm | 10697 | 8796 | 0 | 8 | 2 | 8377 | 0 | 1 | 1 |
| f2s | springboot | 18262 | 14111 | 0 | 48 | 6 | 13145 | 0 | 1 | 1 |
| f3 | quarkus-jvm | 14743 | 11695 | 1 | 28 | 2 | 11288 | 1 | 1 | 1 |
| f3 | springboot | 25813 | 18836 | 0 | 333 | 35 | 17281 | 1 | 1 | 1 |

"ids sem linha" inclui tarefas de compilação descartadas da fila (acontece sem perda de log: no teste local, ~8% no SB e ~3% no QJ). A prova de integridade é "codelist ausentes no log" (esperado 0 ou 1, uma linha corrompida por intercalação com o log da aplicação).
