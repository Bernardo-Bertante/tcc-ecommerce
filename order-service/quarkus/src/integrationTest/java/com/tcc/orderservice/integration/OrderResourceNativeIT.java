package com.tcc.orderservice.integration;

import io.quarkus.test.common.QuarkusTestResource;
import io.quarkus.test.junit.QuarkusIntegrationTest;

@QuarkusIntegrationTest
@QuarkusTestResource(PostgresTestResource.class)
class OrderResourceNativeIT extends OrderResourceScenarios {
}