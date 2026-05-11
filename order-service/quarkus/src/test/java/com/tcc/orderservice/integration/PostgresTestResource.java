package com.tcc.orderservice.integration;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Map;

import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import io.quarkus.test.common.QuarkusTestResourceLifecycleManager;

public class PostgresTestResource implements QuarkusTestResourceLifecycleManager {

    private static volatile String jdbcUrl;
    private static volatile String username;
    private static volatile String password;

    private PostgreSQLContainer<?> postgres;

    @Override
    public Map<String, String> start() {
        postgres = new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"));
        postgres.start();

        jdbcUrl = postgres.getJdbcUrl();
        username = postgres.getUsername();
        password = postgres.getPassword();

        String reactiveUrl = "postgresql://" + postgres.getHost() + ":" + postgres.getFirstMappedPort() + "/"
                + postgres.getDatabaseName();

        return Map.of(
                "quarkus.datasource.username", username,
                "quarkus.datasource.password", password,
                "quarkus.datasource.reactive.url", reactiveUrl,
                "quarkus.datasource.jdbc.url", jdbcUrl);
    }

    static void cleanDatabase() {
        if (jdbcUrl == null || username == null || password == null) {
            throw new IllegalStateException("PostgreSQL test resource has not been started");
        }

        try (Connection connection = DriverManager.getConnection(jdbcUrl, username, password);
                Statement statement = connection.createStatement()) {
            statement.execute("TRUNCATE TABLE order_status_history, order_items, orders");
        } catch (SQLException exception) {
            throw new IllegalStateException("Failed to clean PostgreSQL test database", exception);
        }
    }

    @Override
    public void stop() {
        if (postgres != null) {
            postgres.stop();
        }

        jdbcUrl = null;
        username = null;
        password = null;
    }
}
