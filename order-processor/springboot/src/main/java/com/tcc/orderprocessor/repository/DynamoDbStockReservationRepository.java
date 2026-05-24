package com.tcc.orderprocessor.repository;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Repository;

import com.tcc.orderprocessor.config.DynamoDbProperties;
import com.tcc.orderprocessor.domain.StockReservation;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;

@Repository
public class DynamoDbStockReservationRepository implements StockReservationRepository {

	private final DynamoDbClient dynamoDbClient;
	private final DynamoDbProperties properties;

	public DynamoDbStockReservationRepository(DynamoDbClient dynamoDbClient, DynamoDbProperties properties) {
		this.dynamoDbClient = dynamoDbClient;
		this.properties = properties;
	}

	@Override
	public void saveAll(List<StockReservation> reservations) {
		for (StockReservation reservation : reservations) {
			dynamoDbClient.putItem(PutItemRequest.builder()
					.tableName(properties.stockReservationsTable())
					.item(toItem(reservation))
					.build());
		}
	}

	private static Map<String, AttributeValue> toItem(StockReservation reservation) {
		Map<String, AttributeValue> item = new HashMap<>();
		item.put("orderId", AttributeValue.builder().s(reservation.orderId().toString()).build());
		item.put("productId", AttributeValue.builder().s(reservation.productId().toString()).build());
		item.put("quantity", AttributeValue.builder().n(Integer.toString(reservation.quantity())).build());
		item.put("reservedAt", timestamp(reservation.reservedAt()));
		return item;
	}

	private static AttributeValue timestamp(LocalDateTime value) {
		return AttributeValue.builder().s(value.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)).build();
	}

}