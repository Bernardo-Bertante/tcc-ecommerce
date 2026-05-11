package com.tcc.orderservice.integration;

import static io.restassured.RestAssured.given;
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

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.request.AddItemRequest;
import com.tcc.orderservice.dto.request.CreateOrderRequest;
import com.tcc.orderservice.dto.request.ShippingAddressRequest;
import com.tcc.orderservice.dto.request.UpdateStatusRequest;
import com.tcc.orderservice.dto.response.OrderItemResponse;
import com.tcc.orderservice.dto.response.OrderResponse;
import com.tcc.orderservice.dto.response.OrderStatusHistoryResponse;

import io.restassured.common.mapper.TypeRef;
import io.restassured.http.ContentType;

abstract class OrderResourceScenarios {

    @BeforeEach
    void cleanDatabase() {
        PostgresTestResource.cleanDatabase();
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

        List<OrderStatusHistoryResponse> historyEntries = given()
                .get("/orders/{id}/history", createdOrder.getId())
                .then()
                .statusCode(200)
                .extract()
                .as(new TypeRef<List<OrderStatusHistoryResponse>>() {
                });

        assertNotNull(historyEntries);
        assertEquals(2, historyEntries.size());
        assertNull(historyEntries.get(0).getPreviousStatus());
        assertEquals(OrderStatus.PENDING, historyEntries.get(0).getNewStatus());
        assertEquals(OrderStatus.PENDING, historyEntries.get(1).getPreviousStatus());
        assertEquals(OrderStatus.CONFIRMED, historyEntries.get(1).getNewStatus());
        assertFalse(historyEntries.get(0).getChangedAt().isAfter(historyEntries.get(1).getChangedAt()));
    }

    @Test
    void shouldMapOrderNotFoundExceptionToNotFound() {
        UUID orderId = UUID.fromString("11111111-1111-1111-1111-111111111111");

        given()
                .get("/orders/{id}", orderId)
                .then()
                .statusCode(404)
                .contentType("application/problem+json")
                .body("status", org.hamcrest.Matchers.equalTo(404))
                .body("title", org.hamcrest.Matchers.equalTo("Order not found"))
                .body("detail", org.hamcrest.Matchers.equalTo("Order not found: " + orderId));
    }

    @Test
    void shouldMapInvalidStatusTransitionExceptionToUnprocessableEntity() {
        OrderResponse createdOrder = createOrder(createOrderRequest(
                UUID.randomUUID(),
                BigDecimal.ZERO,
                new AddItemRequest(UUID.randomUUID(), "Headset", 1, new BigDecimal("25.00"))));

        given()
                .contentType(ContentType.JSON)
                .body(new UpdateStatusRequest(OrderStatus.SHIPPED))
                .put("/orders/{id}/status", createdOrder.getId())
                .then()
                .statusCode(422)
                .contentType("application/problem+json")
                .body("status", org.hamcrest.Matchers.equalTo(422))
                .body("title", org.hamcrest.Matchers.equalTo("Invalid status transition"))
                .body("detail", org.hamcrest.Matchers.equalTo("Invalid status transition: PENDING -> SHIPPED"));
    }

    @Test
    void shouldMapOrderValidationExceptionToBadRequest() {
        given()
                .contentType(ContentType.JSON)
                .body("{}")
                .post("/orders")
                .then()
                .statusCode(400)
                .contentType("application/problem+json")
                .body("status", org.hamcrest.Matchers.equalTo(400))
                .body("title", org.hamcrest.Matchers.equalTo("Validation error"))
                .body("detail", org.hamcrest.Matchers.equalTo("customerId is required"));
    }

    @Test
    void shouldAddAndRemoveItemsAndRecalculateAmounts() {
        OrderResponse createdOrder = createOrder(createOrderRequest(
                UUID.randomUUID(),
                BigDecimal.ZERO,
                new AddItemRequest(UUID.randomUUID(), "Tablet", 1, new BigDecimal("10.00"))));

        OrderResponse orderAfterAdd = given()
                .contentType(ContentType.JSON)
                .body(new AddItemRequest(UUID.randomUUID(), "Mouse", 2, new BigDecimal("5.00")))
                .post("/orders/{id}/items", createdOrder.getId())
                .then()
                .statusCode(200)
                .extract()
                .as(OrderResponse.class);

        assertNotNull(orderAfterAdd);
        assertEquals(2, orderAfterAdd.getItems().size());
        assertMoney("20.00", orderAfterAdd.getTotalAmount());
        assertMoney("20.00", orderAfterAdd.getFinalAmount());

        OrderItemResponse addedItem = orderAfterAdd.getItems().stream()
                .filter(item -> "Mouse".equals(item.getProductName()))
                .findFirst()
                .orElseThrow();

        OrderResponse orderAfterRemove = given()
                .delete("/orders/{id}/items/{itemId}", createdOrder.getId(), addedItem.getId())
                .then()
                .statusCode(200)
                .extract()
                .as(OrderResponse.class);

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

        given()
                .delete("/orders/{id}", createdOrder.getId())
                .then()
                .statusCode(204);

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

        given()
                .queryParam("page", 0)
                .queryParam("pageSize", 1)
                .get("/orders/customer/{customerId}", firstCustomerId)
                .then()
                .statusCode(200)
                .body("content.size()", org.hamcrest.Matchers.equalTo(1))
                .body("totalElements", org.hamcrest.Matchers.equalTo(2))
                .body("totalPages", org.hamcrest.Matchers.equalTo(2))
                .body("currentPage", org.hamcrest.Matchers.equalTo(0))
                .body("pageSize", org.hamcrest.Matchers.equalTo(1));

        LocalDate fromDate = LocalDate.now().minusDays(1);
        LocalDate toDate = LocalDate.now().plusDays(1);

        given()
                .queryParam("status", OrderStatus.PENDING)
                .queryParam("fromDate", fromDate.toString())
                .queryParam("toDate", toDate.toString())
                .queryParam("page", 0)
                .queryParam("pageSize", 10)
                .get("/orders")
                .then()
                .statusCode(200)
                .body("totalElements", org.hamcrest.Matchers.equalTo(3))
                .body("content.size()", org.hamcrest.Matchers.equalTo(3));

        given()
                .queryParam("fromDate", fromDate.toString())
                .queryParam("toDate", toDate.toString())
                .get("/orders/summary")
                .then()
                .statusCode(200)
                .body("totalOrders", org.hamcrest.Matchers.equalTo(3))
                .body("totalRevenue", org.hamcrest.Matchers.equalTo(50.48f))
                .body("averageOrderValue", org.hamcrest.Matchers.equalTo(16.83f))
                .body("ordersByStatus.PENDING", org.hamcrest.Matchers.equalTo(3))
                .body("topCustomers.size()", org.hamcrest.Matchers.equalTo(2))
                .body("revenueByDay.size()", org.hamcrest.Matchers.equalTo(1));
    }

    private OrderResponse createOrder(CreateOrderRequest request) {
        OrderResponse createdOrder = given()
                .contentType(ContentType.JSON)
                .body(request)
                .post("/orders")
                .then()
                .statusCode(201)
                .extract()
                .as(OrderResponse.class);

        assertNotNull(createdOrder);
        assertNotNull(createdOrder.getId());
        return createdOrder;
    }

    private OrderResponse getOrder(UUID orderId) {
        OrderResponse order = given()
                .get("/orders/{id}", orderId)
                .then()
                .statusCode(200)
                .extract()
                .as(OrderResponse.class);

        assertNotNull(order);
        return order;
    }

    private OrderResponse updateStatus(UUID orderId, OrderStatus status) {
        OrderResponse order = given()
                .contentType(ContentType.JSON)
                .body(new UpdateStatusRequest(status))
                .put("/orders/{id}/status", orderId)
                .then()
                .statusCode(200)
                .extract()
                .as(OrderResponse.class);

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