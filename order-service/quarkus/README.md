# order-service-quarkus

This project uses Quarkus, the Supersonic Subatomic Java Framework.

If you want to learn more about Quarkus, please visit its website: <https://quarkus.io/>.

## Running the application in dev mode

You can run your application in dev mode that enables live coding using:

```shell script
./gradlew quarkusDev
```

> **_NOTE:_**  Quarkus now ships with a Dev UI, which is available in dev mode only at <http://localhost:8080/q/dev/>.

## Packaging and running the application

The application can be packaged using:

```shell script
./gradlew build
```

It produces the `quarkus-run.jar` file in the `build/quarkus-app/` directory.
Be aware that it’s not an _über-jar_ as the dependencies are copied into the `build/quarkus-app/lib/` directory.

The application is now runnable using `java -jar build/quarkus-app/quarkus-run.jar`.

If you want to build an _über-jar_, execute the following command:

```shell script
./gradlew build -Dquarkus.package.jar.type=uber-jar
```

The application, packaged as an _über-jar_, is now runnable using `java -jar build/*-runner.jar`.

## Container images

This repository keeps the canonical container files at the module root for consistency with the Spring Boot variant:

```shell script
docker build -f Dockerfile.jvm -t order-service-quarkus:jvm .
docker build -f Dockerfile.native -t order-service-quarkus:native .
```

The default HTTP port is `8081`, matching the Spring Boot module.

## Creating a native executable

You can create a native executable using:

```shell script
./gradlew build -Dquarkus.native.enabled=true -Dquarkus.package.jar.enabled=false --no-daemon
```

Or, if you don't have GraalVM installed, you can run the native executable build in a container using:

```shell script
./gradlew build -Dquarkus.native.enabled=true -Dquarkus.package.jar.enabled=false -Dquarkus.native.container-build=true -Dquarkus.native.native-image-xmx=6g --no-daemon
```

You can then execute your native executable with: `./build/order-service-quarkus-0.0.1-SNAPSHOT-runner`

## Runtime validation

The JVM baseline uses Quarkus tests plus Testcontainers PostgreSQL:

```shell script
./gradlew clean test
```

The native runtime gate runs the same HTTP scenarios against the built Quarkus artifact with `@QuarkusIntegrationTest`:

```shell script
./gradlew quarkusIntTest -Dquarkus.native.enabled=true -Dquarkus.package.jar.enabled=false -Dquarkus.native.container-build=true -Dquarkus.native.native-image-xmx=6g --no-daemon
```

To validate the native container wrapper as well, build the native executable first, then build and run the compose smoke stack from the repository root:

```shell script
cd /path/to/ecommerce-tcc/order-service/quarkus
./gradlew build -Dquarkus.native.enabled=true -Dquarkus.package.jar.enabled=false -Dquarkus.native.container-build=true -Dquarkus.native.native-image-xmx=6g --no-daemon
docker build -f Dockerfile.native -t order-service-quarkus:native .

cd /path/to/ecommerce-tcc
docker compose -f infrastructure/docker-compose.test.yml up -d
order-service/quarkus/scripts/smoke-native-container.sh
docker compose -f infrastructure/docker-compose.test.yml down -v
```

The compose smoke uses PostgreSQL inside the same Docker network, so the application container receives datasource URLs with the `postgres` service hostname instead of the local `localhost:55432` default.

The container-based native path above is the one validated locally in this repository; the explicit `-Dquarkus.native.native-image-xmx=6g` keeps the Mandrel build stable during native image generation.

If you want to learn more about building native executables, please consult <https://quarkus.io/guides/gradle-tooling>.

## Related Guides

- REST ([guide](https://quarkus.io/guides/rest)): Build RESTful web services and APIs using Jakarta REST (formerly JAX-RS)
- Flyway ([guide](https://quarkus.io/guides/flyway)): Handle your database schema migrations
- Micrometer Registry Prometheus ([guide](https://quarkus.io/guides/micrometer)): Enable Prometheus support for Micrometer
- REST Jackson ([guide](https://quarkus.io/guides/rest#json-serialisation)): Jackson serialization support for Quarkus REST. This extension is not compatible with the quarkus-resteasy extension, or any of the extensions that depend on it
- SmallRye Health ([guide](https://quarkus.io/guides/smallrye-health)): Monitor service health
- Reactive PostgreSQL client ([guide](https://quarkus.io/guides/reactive-sql-clients)): Connect to the PostgreSQL database using the reactive pattern
- JDBC Driver - PostgreSQL ([guide](https://quarkus.io/guides/datasource)): Connect to the PostgreSQL database via JDBC
