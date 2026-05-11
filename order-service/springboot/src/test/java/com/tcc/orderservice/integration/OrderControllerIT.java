package com.tcc.orderservice.integration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.web.reactive.server.WebTestClient;

import com.tcc.orderservice.TestcontainersConfiguration;
import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.request.AddItemRequest;
import com.tcc.orderservice.dto.request.CreateOrderRequest;
import com.tcc.orderservice.dto.request.ShippingAddressRequest;
import com.tcc.orderservice.dto.request.UpdateStatusRequest;
import com.tcc.orderservice.dto.response.OrderItemResponse;
import com.tcc.orderservice.dto.response.OrderResponse;
import com.tcc.orderservice.dto.response.OrderStatusHistoryResponse;

@Import(TestcontainersConfiguration.class)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
class OrderControllerIT {

	@Autowired
	private WebTestClient webTestClient;

	@Autowired
	private DatabaseClient databaseClient;

	@BeforeEach
	void cleanDatabase() {
		databaseClient.sql("TRUNCATE TABLE order_status_history, order_items, orders")
				.fetch()
				.rowsUpdated()
				.block();
	}

	@Test
	void shouldCreateOrderAndGetById() {
		UUID customerId = UUID.randomUUID();
		CreateOrderRequest request = createOrderRequest(
				customerId,
				new BigDecimal("1.00"),
				new AddItemRequest(UUID.randomUUID(), "Keyboard", 2, new BigDecimal("9.99")));

		OrderResponse createdOrder = createOrder(request);
		assertNotNull(createdOrder);
		assertNotNull(createdOrder.getId());
		assertEquals(customerId, createdOrder.getCustomerId());
		assertEquals(OrderStatus.PENDING, createdOrder.getStatus());
		assertMoney("19.98", createdOrder.getTotalAmount());
		assertMoney("1.00", createdOrder.getDiscountAmount());
		assertMoney("18.98", createdOrder.getFinalAmount());
		assertEquals(1, createdOrder.getItems().size());
		assertEquals("MG", createdOrder.getShippingAddress().getState());
		assertNotNull(createdOrder.getCreatedAt());
		assertNotNull(createdOrder.getUpdatedAt());

		OrderResponse fetchedOrder = getOrder(createdOrder.getId());
		assertNotNull(fetchedOrder);
		assertEquals(createdOrder.getId(), fetchedOrder.getId());
		assertEquals(OrderStatus.PENDING, fetchedOrder.getStatus());
		assertMoney("19.98", fetchedOrder.getTotalAmount());
		assertMoney("18.98", fetchedOrder.getFinalAmount());
		assertEquals(1, fetchedOrder.getItems().size());
	}

	@Test
	void shouldStoreStatusHistoryInOrder() {
		OrderResponse createdOrder = createOrder(createOrderRequest(
				UUID.randomUUID(),
				BigDecimal.ZERO,
				new AddItemRequest(UUID.randomUUID(), "Notebook", 1, new BigDecimal("100.00"))));

		OrderResponse updatedOrder = updateStatus(createdOrder.getId(), OrderStatus.CONFIRMED);
		assertEquals(OrderStatus.CONFIRMED, updatedOrder.getStatus());

		List<OrderStatusHistoryResponse> historyEntries = webTestClient.get()
				.uri("/orders/{id}/history", createdOrder.getId())
				.exchange()
				.expectStatus().isOk()
				.expectBodyList(OrderStatusHistoryResponse.class)
				.returnResult()
				.getResponseBody();

		assertNotNull(historyEntries);
		assertEquals(2, historyEntries.size());
		assertNull(historyEntries.get(0).getPreviousStatus());
		assertEquals(OrderStatus.PENDING, historyEntries.get(0).getNewStatus());
		assertEquals(OrderStatus.PENDING, historyEntries.get(1).getPreviousStatus());
		assertEquals(OrderStatus.CONFIRMED, historyEntries.get(1).getNewStatus());
		assertFalse(historyEntries.get(0).getChangedAt().isAfter(historyEntries.get(1).getChangedAt()));
	}

	@Test
	void shouldReturnUnprocessableEntityForInvalidStatusTransition() {
		OrderResponse createdOrder = createOrder(createOrderRequest(
				UUID.randomUUID(),
				BigDecimal.ZERO,
				new AddItemRequest(UUID.randomUUID(), "Headset", 1, new BigDecimal("25.00"))));

		webTestClient.put()
				.uri("/orders/{id}/status", createdOrder.getId())
				.contentType(MediaType.APPLICATION_JSON)
				.bodyValue(new UpdateStatusRequest(OrderStatus.SHIPPED))
				.exchange()
				.expectStatus().isEqualTo(422)
				.expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
				.expectBody()
				.jsonPath("$.title").isEqualTo("Invalid status transition")
				.jsonPath("$.detail").isEqualTo("Invalid status transition: PENDING -> SHIPPED");
	}

	@Test
	void shouldAddAndRemoveItemsAndRecalculateAmounts() {
		OrderResponse createdOrder = createOrder(createOrderRequest(
				UUID.randomUUID(),
				BigDecimal.ZERO,
				new AddItemRequest(UUID.randomUUID(), "Tablet", 1, new BigDecimal("10.00"))));

		OrderResponse orderAfterAdd = webTestClient.post()
				.uri("/orders/{id}/items", createdOrder.getId())
				.contentType(MediaType.APPLICATION_JSON)
				.bodyValue(new AddItemRequest(UUID.randomUUID(), "Mouse", 2, new BigDecimal("5.00")))
				.exchange()
				.expectStatus().isOk()
				.expectBody(OrderResponse.class)
				.returnResult()
				.getResponseBody();

		assertNotNull(orderAfterAdd);
		assertEquals(2, orderAfterAdd.getItems().size());
		assertMoney("20.00", orderAfterAdd.getTotalAmount());
		assertMoney("20.00", orderAfterAdd.getFinalAmount());

		OrderItemResponse addedItem = orderAfterAdd.getItems().stream()
				.filter(item -> "Mouse".equals(item.getProductName()))
				.findFirst()
				.orElseThrow();

		OrderResponse orderAfterRemove = webTestClient.delete()
				.uri("/orders/{id}/items/{itemId}", createdOrder.getId(), addedItem.getId())
				.exchange()
				.expectStatus().isOk()
				.expectBody(OrderResponse.class)
				.returnResult()
				.getResponseBody();

		assertNotNull(orderAfterRemove);
		assertEquals(1, orderAfterRemove.getItems().size());
		assertMoney("10.00", orderAfterRemove.getTotalAmount());
		assertMoney("10.00", orderAfterRemove.getFinalAmount());
	}

	@Test
	void shouldCancelOrderAndExposeCancelledStatus() {
		OrderResponse createdOrder = createOrder(createOrderRequest(
				UUID.randomUUID(),
				BigDecimal.ZERO,
				new AddItemRequest(UUID.randomUUID(), "Monitor", 1, new BigDecimal("200.00"))));

		webTestClient.delete()
				.uri("/orders/{id}", createdOrder.getId())
				.exchange()
				.expectStatus().isNoContent();

		OrderResponse cancelledOrder = getOrder(createdOrder.getId());
		assertEquals(OrderStatus.CANCELLED, cancelledOrder.getStatus());
	}

	@Test
	void shouldReturnPagedCustomerOrdersAndSummaryForDateRange() {
		UUID firstCustomerId = UUID.randomUUID();
		UUID secondCustomerId = UUID.randomUUID();

		createOrder(createOrderRequest(
				firstCustomerId,
				new BigDecimal("1.00"),
				new AddItemRequest(UUID.randomUUID(), "Keyboard", 2, new BigDecimal("9.99"))));
		createOrder(createOrderRequest(
				firstCustomerId,
				BigDecimal.ZERO,
				new AddItemRequest(UUID.randomUUID(), "Desk", 1, new BigDecimal("20.00"))));
		createOrder(createOrderRequest(
				secondCustomerId,
				new BigDecimal("0.50"),
				new AddItemRequest(UUID.randomUUID(), "Cable", 3, new BigDecimal("4.00"))));

		webTestClient.get()
				.uri(uriBuilder -> uriBuilder.path("/orders/customer/{customerId}")
						.queryParam("page", 0)
						.queryParam("pageSize", 1)
						.build(firstCustomerId))
				.exchange()
				.expectStatus().isOk()
				.expectBody()
				.jsonPath("$.content.length()").isEqualTo(1)
				.jsonPath("$.totalElements").isEqualTo(2)
				.jsonPath("$.totalPages").isEqualTo(2)
				.jsonPath("$.currentPage").isEqualTo(0)
				.jsonPath("$.pageSize").isEqualTo(1);

		LocalDate fromDate = LocalDate.now().minusDays(1);
		LocalDate toDate = LocalDate.now().plusDays(1);

		webTestClient.get()
				.uri(uriBuilder -> uriBuilder.path("/orders")
						.queryParam("status", OrderStatus.PENDING)
						.queryParam("fromDate", fromDate)
						.queryParam("toDate", toDate)
						.queryParam("page", 0)
						.queryParam("pageSize", 10)
						.build())
				.exchange()
				.expectStatus().isOk()
				.expectBody()
				.jsonPath("$.totalElements").isEqualTo(3)
				.jsonPath("$.content.length()").isEqualTo(3);

		webTestClient.get()
				.uri(uriBuilder -> uriBuilder.path("/orders/summary")
						.queryParam("fromDate", fromDate)
						.queryParam("toDate", toDate)
						.build())
				.exchange()
				.expectStatus().isOk()
				.expectBody()
				.jsonPath("$.totalOrders").isEqualTo(3)
				.jsonPath("$.totalRevenue").isEqualTo(50.48)
				.jsonPath("$.averageOrderValue").isEqualTo(16.83)
				.jsonPath("$.ordersByStatus.PENDING").isEqualTo(3)
				.jsonPath("$.topCustomers.length()").isEqualTo(2)
				.jsonPath("$.revenueByDay.length()").isEqualTo(1);
	}

	private OrderResponse createOrder(CreateOrderRequest request) {
		OrderResponse createdOrder = webTestClient.post()
				.uri("/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.bodyValue(request)
				.exchange()
				.expectStatus().isCreated()
				.expectBody(OrderResponse.class)
				.returnResult()
				.getResponseBody();

		assertNotNull(createdOrder);
		assertNotNull(createdOrder.getId());
		return createdOrder;
	}

	private OrderResponse getOrder(UUID orderId) {
		OrderResponse order = webTestClient.get()
				.uri("/orders/{id}", orderId)
				.exchange()
				.expectStatus().isOk()
				.expectBody(OrderResponse.class)
				.returnResult()
				.getResponseBody();

		assertNotNull(order);
		return order;
	}

	private OrderResponse updateStatus(UUID orderId, OrderStatus status) {
		OrderResponse order = webTestClient.put()
				.uri("/orders/{id}/status", orderId)
				.contentType(MediaType.APPLICATION_JSON)
				.bodyValue(new UpdateStatusRequest(status))
				.exchange()
				.expectStatus().isOk()
				.expectBody(OrderResponse.class)
				.returnResult()
				.getResponseBody();

		assertNotNull(order);
		return order;
	}

	private CreateOrderRequest createOrderRequest(UUID customerId,
			BigDecimal discountAmount,
			AddItemRequest... items) {
		return new CreateOrderRequest(
				customerId,
				discountAmount,
				List.of(items),
				new ShippingAddressRequest(
						"37200-000",
						"Main Street",
						"123",
						null,
						"Lavras",
						"MG"));
	}

	private void assertMoney(String expectedValue, BigDecimal actualValue) {
		assertNotNull(actualValue);
		assertTrue(new BigDecimal(expectedValue).compareTo(actualValue) == 0,
				() -> "Expected money value " + expectedValue + " but got " + actualValue);
	}
}
