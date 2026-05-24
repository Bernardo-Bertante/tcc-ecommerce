package com.tcc.orderprocessor.repository;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;

import org.springframework.stereotype.Repository;

import com.tcc.orderprocessor.config.DynamoDbProperties;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;

@Repository
public class DynamoDbProcessedOrderRepository implements ProcessedOrderRepository {

	private final DynamoDbClient dynamoDbClient;
	private final DynamoDbProperties properties;

	public DynamoDbProcessedOrderRepository(DynamoDbClient dynamoDbClient, DynamoDbProperties properties) {
		this.dynamoDbClient = dynamoDbClient;
		this.properties = properties;
	}

	@Override
	public void save(ProcessingRequest request, ProcessingResult result) {
		Map<String, AttributeValue> item = new HashMap<>();
		item.put("orderId", string(result.orderId()));
		item.put("customerId", string(request.customerId()));
		item.put("fiscalNumber", string(result.fiscalNumber()));
		item.put("shippingCost", number(result.shippingCost()));
		item.put("taxAmount", number(result.taxAmount()));
		item.put("finalAmount", number(result.finalAmount()));
		item.put("estimatedDeliveryDays", number(result.estimatedDeliveryDays()));
		item.put("processedAt", timestamp(result.processedAt()));

		dynamoDbClient.putItem(PutItemRequest.builder()
				.tableName(properties.processedOrdersTable())
				.item(item)
				.build());
	}

	private static AttributeValue string(Object value) {
		return AttributeValue.builder().s(String.valueOf(value)).build();
	}

	private static AttributeValue number(BigDecimal value) {
		return AttributeValue.builder().n(value.toPlainString()).build();
	}

	private static AttributeValue number(int value) {
		return AttributeValue.builder().n(Integer.toString(value)).build();
	}

	private static AttributeValue timestamp(LocalDateTime value) {
		return AttributeValue.builder().s(value.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)).build();
	}

}