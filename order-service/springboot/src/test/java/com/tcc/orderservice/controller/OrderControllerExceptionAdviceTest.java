package com.tcc.orderservice.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.request.CreateOrderRequest;
import com.tcc.orderservice.dto.request.UpdateStatusRequest;
import com.tcc.orderservice.exception.InvalidStatusTransitionException;
import com.tcc.orderservice.exception.OrderExceptionHandler;
import com.tcc.orderservice.exception.OrderNotFoundException;
import com.tcc.orderservice.exception.OrderValidationException;
import com.tcc.orderservice.service.OrderService;

import reactor.core.publisher.Mono;

@WebFluxTest(controllers = OrderController.class)
@Import(OrderExceptionHandler.class)
class OrderControllerExceptionAdviceTest {

	@Autowired
	private WebTestClient webTestClient;

	@MockitoBean
	private OrderService orderService;

	@Test
	void shouldMapOrderNotFoundExceptionToNotFound() {
		UUID orderId = UUID.fromString("11111111-1111-1111-1111-111111111111");
		when(orderService.getOrderById(orderId))
				.thenReturn(Mono.error(new OrderNotFoundException(orderId)));

		webTestClient.get()
				.uri("/orders/{id}", orderId)
				.exchange()
				.expectStatus().isNotFound()
				.expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
				.expectBody()
				.jsonPath("$.status").isEqualTo(404)
				.jsonPath("$.title").isEqualTo("Order not found")
				.jsonPath("$.detail").isEqualTo("Order not found: " + orderId);
	}

	@Test
	void shouldMapInvalidStatusTransitionExceptionToUnprocessableEntity() {
		UUID orderId = UUID.fromString("22222222-2222-2222-2222-222222222222");
		when(orderService.updateOrderStatus(eq(orderId), any(UpdateStatusRequest.class)))
				.thenReturn(Mono.error(new InvalidStatusTransitionException(OrderStatus.PENDING, OrderStatus.SHIPPED)));

		webTestClient.put()
				.uri("/orders/{id}/status", orderId)
				.contentType(MediaType.APPLICATION_JSON)
				.bodyValue("{\"status\":\"SHIPPED\"}")
				.exchange()
				.expectStatus().isEqualTo(422)
				.expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
				.expectBody()
				.jsonPath("$.status").isEqualTo(422)
				.jsonPath("$.title").isEqualTo("Invalid status transition")
				.jsonPath("$.detail").isEqualTo("Invalid status transition: PENDING -> SHIPPED");
	}

	@Test
	void shouldMapOrderValidationExceptionToBadRequest() {
		when(orderService.createOrder(any(CreateOrderRequest.class)))
				.thenReturn(Mono.error(new OrderValidationException("customerId is required")));

		webTestClient.post()
				.uri("/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.bodyValue("{}")
				.exchange()
				.expectStatus().isBadRequest()
				.expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON)
				.expectBody()
				.jsonPath("$.status").isEqualTo(400)
				.jsonPath("$.title").isEqualTo("Validation error")
				.jsonPath("$.detail").isEqualTo("customerId is required");
	}
}