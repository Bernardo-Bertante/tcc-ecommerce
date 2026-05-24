package com.tcc.orderprocessor.config;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "order.processor.dynamodb")
public interface DynamoDbProperties {

	@WithDefault("processed_orders")
	String processedOrdersTable();

	@WithDefault("stock_reservations")
	String stockReservationsTable();

}