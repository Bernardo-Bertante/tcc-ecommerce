package com.tcc.orderservice.integration;

import io.quarkus.test.common.QuarkusTestResource;
import io.quarkus.test.junit.QuarkusTest;

@QuarkusTest
@QuarkusTestResource(PostgresTestResource.class)
class OrderResourceIT extends OrderResourceScenarios {
}
