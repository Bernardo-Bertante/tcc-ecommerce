package com.tcc.orderprocessor.integration;

import java.util.Map;

import org.testcontainers.containers.GenericContainer;
import org.testcontainers.utility.DockerImageName;

import io.quarkus.test.common.QuarkusTestResourceLifecycleManager;

public class DynamoDbTestResource implements QuarkusTestResourceLifecycleManager {

	private GenericContainer<?> dynamoDb;

	@Override
	public Map<String, String> start() {
		dynamoDb = new GenericContainer<>(DockerImageName.parse("public.ecr.aws/aws-dynamodb-local/aws-dynamodb-local:latest"))
				.withExposedPorts(8000);
		dynamoDb.start();

		return Map.of(
				"dynamodb.endpoint", "http://" + dynamoDb.getHost() + ":" + dynamoDb.getMappedPort(8000),
				"aws.region", "us-east-1",
				"order.processor.dynamodb.processed-orders-table", "processed_orders_quarkus_it",
				"order.processor.dynamodb.stock-reservations-table", "stock_reservations_quarkus_it"
		);
	}

	@Override
	public void stop() {
		if (dynamoDb != null) {
			dynamoDb.stop();
		}
	}

}