# tcc-aws-ecommerce

## Order Service - Spring Boot WebFlux + R2DBC (TCC Benchmark)

## Stack local de benchmark do Order Service

O arquivo `infrastructure/docker-compose.benchmark.yml` sobe as três variantes do Order Service ao mesmo tempo, todas conectadas a um PostgreSQL compartilhado:

| Variante | URL local | Health endpoint | Imagem |
| --- | --- | --- | --- |
| Quarkus Native | `http://localhost:8081` | `/q/health` | `order-service-quarkus:native` |
| Quarkus JVM | `http://localhost:8082` | `/q/health` | `order-service-quarkus:jvm` |
| Spring Boot JVM | `http://localhost:8083` | `/actuator/health` | `order-service-springboot:jvm` |
| PostgreSQL compartilhado | `localhost:55434` | `pg_isready` | `postgres:16-alpine` |

Antes de subir o Compose, gere os artefatos que os Dockerfiles copiam para as imagens:

```bash
cd order-service/springboot
./gradlew clean bootJar --no-daemon

cd ../quarkus
./gradlew clean build --no-daemon
./gradlew build -Dquarkus.native.enabled=true -Dquarkus.package.jar.enabled=false -Dquarkus.native.container-build=true -Dquarkus.native.native-image-xmx=6g --no-daemon
```

Depois, a partir da raiz do repositório:

```bash
docker compose -f infrastructure/docker-compose.benchmark.yml up --build -d
```

Verifique a prontidão das três aplicações:

```bash
curl --fail http://localhost:8081/q/health
curl --fail http://localhost:8082/q/health
curl --fail http://localhost:8083/actuator/health
```

Para encerrar e remover o banco efêmero do benchmark:

```bash
docker compose -f infrastructure/docker-compose.benchmark.yml down -v
```

Os cenários em `benchmark/` ainda devem ser executados apontando para uma URL por vez. Use `http://localhost:8081`, `http://localhost:8082` ou `http://localhost:8083` conforme a variante que será medida.
