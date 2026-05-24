package com.tcc.orderprocessor.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "order.processor.dynamodb")
public record DynamoDbProperties(
		String processedOrdersTable,
		String stockReservationsTable
) {

	public DynamoDbProperties {
		processedOrdersTable = defaultIfBlank(processedOrdersTable, "processed_orders");
		stockReservationsTable = defaultIfBlank(stockReservationsTable, "stock_reservations");
	}

	private static String defaultIfBlank(String value, String fallback) {
		return value == null || value.isBlank() ? fallback : value;
	}

}