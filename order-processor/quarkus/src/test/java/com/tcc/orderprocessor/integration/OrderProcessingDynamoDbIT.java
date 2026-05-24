package com.tcc.orderprocessor.integration;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.config.DynamoDbProperties;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.service.OrderProcessingService;

import io.quarkus.test.common.QuarkusTestResource;
import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeDefinition;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.BillingMode;
import software.amazon.awssdk.services.dynamodb.model.CreateTableRequest;
import software.amazon.awssdk.services.dynamodb.model.DescribeTableRequest;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.KeySchemaElement;
import software.amazon.awssdk.services.dynamodb.model.KeyType;
import software.amazon.awssdk.services.dynamodb.model.ScalarAttributeType;

@QuarkusTest
@QuarkusTestResource(DynamoDbTestResource.class)
class OrderProcessingDynamoDbIT {

	@Inject
	OrderProcessingService service;

	@Inject
	DynamoDbClient dynamoDbClient;

	@Inject
	DynamoDbProperties properties;

	@BeforeEach
	void createTables() {
		createTableIfMissing(properties.processedOrdersTable(), "orderId", null);
		createTableIfMissing(properties.stockReservationsTable(), "orderId", "productId");
	}

	@Test
	void writesProcessingResultAndStockReservationAttributes() {
		ProcessingResult result = service.process(ProcessingFixtures.validRequest());

		Map<String, AttributeValue> orderItem = dynamoDbClient.getItem(GetItemRequest.builder()
				.tableName(properties.processedOrdersTable())
				.key(Map.of("orderId", string(result.orderId().toString())))
				.build()).item();

		assertThat(orderItem.get("orderId").s()).isEqualTo(result.orderId().toString());
		assertThat(orderItem.get("customerId").s()).isEqualTo(ProcessingFixtures.CUSTOMER_ID.toString());
		assertThat(orderItem.get("fiscalNumber").s()).isEqualTo("NF-3F2504E04F89");
		assertThat(decimal(orderItem, "shippingCost")).isEqualByComparingTo("19.90");
		assertThat(decimal(orderItem, "taxAmount")).isEqualByComparingTo("31.98");
		assertThat(decimal(orderItem, "finalAmount")).isEqualByComparingTo("451.68");
		assertThat(orderItem.get("estimatedDeliveryDays").n()).isEqualTo("2");
		assertThat(orderItem.get("processedAt").s()).isEqualTo(format(result));

		Map<String, AttributeValue> reservationItem = dynamoDbClient.getItem(GetItemRequest.builder()
				.tableName(properties.stockReservationsTable())
				.key(Map.of(
						"orderId", string(result.orderId().toString()),
						"productId", string(ProcessingFixtures.KEYBOARD_ID.toString())
				))
				.build()).item();

		assertThat(reservationItem.get("orderId").s()).isEqualTo(result.orderId().toString());
		assertThat(reservationItem.get("productId").s()).isEqualTo(ProcessingFixtures.KEYBOARD_ID.toString());
		assertThat(reservationItem.get("quantity").n()).isEqualTo("2");
		assertThat(reservationItem.get("reservedAt").s()).isEqualTo(format(result));
	}

	@Test
	void writesOneStockReservationPerItem() {
		ProcessingResult result = service.process(ProcessingFixtures.validRequestWithTwoItems());

		Map<String, AttributeValue> keyboardReservation = dynamoDbClient.getItem(GetItemRequest.builder()
				.tableName(properties.stockReservationsTable())
				.key(Map.of(
						"orderId", string(result.orderId().toString()),
						"productId", string(ProcessingFixtures.KEYBOARD_ID.toString())
				))
				.build()).item();

		Map<String, AttributeValue> mouseReservation = dynamoDbClient.getItem(GetItemRequest.builder()
				.tableName(properties.stockReservationsTable())
				.key(Map.of(
						"orderId", string(result.orderId().toString()),
						"productId", string(ProcessingFixtures.MOUSE_ID.toString())
				))
				.build()).item();

		assertThat(keyboardReservation.get("orderId").s()).isEqualTo(result.orderId().toString());
		assertThat(keyboardReservation.get("productId").s()).isEqualTo(ProcessingFixtures.KEYBOARD_ID.toString());
		assertThat(keyboardReservation.get("quantity").n()).isEqualTo("2");
		assertThat(keyboardReservation.get("reservedAt").s()).isEqualTo(format(result));

		assertThat(mouseReservation.get("orderId").s()).isEqualTo(result.orderId().toString());
		assertThat(mouseReservation.get("productId").s()).isEqualTo(ProcessingFixtures.MOUSE_ID.toString());
		assertThat(mouseReservation.get("quantity").n()).isEqualTo("1");
		assertThat(mouseReservation.get("reservedAt").s()).isEqualTo(format(result));
	}

	private void createTableIfMissing(String tableName, String partitionKey, String sortKey) {
		if (dynamoDbClient.listTables().tableNames().contains(tableName)) {
			return;
		}

		CreateTableRequest.Builder request = CreateTableRequest.builder()
				.tableName(tableName)
				.billingMode(BillingMode.PAY_PER_REQUEST)
				.keySchema(keySchema(partitionKey, sortKey))
				.attributeDefinitions(attributeDefinitions(partitionKey, sortKey));

		dynamoDbClient.createTable(request.build());
		dynamoDbClient.waiter().waitUntilTableExists(DescribeTableRequest.builder().tableName(tableName).build());
	}

	private List<KeySchemaElement> keySchema(String partitionKey, String sortKey) {
		KeySchemaElement partition = KeySchemaElement.builder()
				.attributeName(partitionKey)
				.keyType(KeyType.HASH)
				.build();
		if (sortKey == null) {
			return List.of(partition);
		}
		return List.of(partition, KeySchemaElement.builder()
				.attributeName(sortKey)
				.keyType(KeyType.RANGE)
				.build());
	}

	private List<AttributeDefinition> attributeDefinitions(String partitionKey, String sortKey) {
		AttributeDefinition partition = AttributeDefinition.builder()
				.attributeName(partitionKey)
				.attributeType(ScalarAttributeType.S)
				.build();
		if (sortKey == null) {
			return List.of(partition);
		}
		return List.of(partition, AttributeDefinition.builder()
				.attributeName(sortKey)
				.attributeType(ScalarAttributeType.S)
				.build());
	}

	private static AttributeValue string(String value) {
		return AttributeValue.builder().s(value).build();
	}

	private static BigDecimal decimal(Map<String, AttributeValue> item, String attributeName) {
		return new BigDecimal(item.get(attributeName).n());
	}

	private static String format(ProcessingResult result) {
		return result.processedAt().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
	}

}