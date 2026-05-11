package com.tcc.orderservice.controller;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.request.AddItemRequest;
import com.tcc.orderservice.dto.request.CreateOrderRequest;
import com.tcc.orderservice.dto.request.UpdateStatusRequest;
import com.tcc.orderservice.dto.response.OrderResponse;
import com.tcc.orderservice.dto.response.OrderStatusHistoryResponse;
import com.tcc.orderservice.dto.response.OrderSummaryResponse;
import com.tcc.orderservice.dto.response.PageResponse;
import com.tcc.orderservice.service.OrderService;

import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/orders")
public class OrderController {

	private final OrderService orderService;

	public OrderController(OrderService orderService) {
		this.orderService = orderService;
	}

	@PostMapping
	public Mono<ResponseEntity<OrderResponse>> createOrder(@RequestBody CreateOrderRequest request) {
		return orderService.createOrder(request)
				.map(orderResponse -> ResponseEntity.status(HttpStatus.CREATED).body(orderResponse));
	}

	@GetMapping("/{id}")
	public Mono<OrderResponse> getOrderById(@PathVariable("id") UUID orderId) {
		return orderService.getOrderById(orderId);
	}

	@GetMapping("/{id}/history")
	public Mono<List<OrderStatusHistoryResponse>> getOrderHistory(@PathVariable("id") UUID orderId) {
		return orderService.getOrderHistory(orderId);
	}

	@GetMapping("/customer/{customerId}")
	public Mono<PageResponse<OrderResponse>> getOrdersByCustomerId(
			@PathVariable UUID customerId,
			@RequestParam(defaultValue = "0") int page,
			@RequestParam(name = "pageSize", defaultValue = "20") int pageSize) {
		return orderService.getOrdersByCustomerId(customerId, page, pageSize);
	}

	@GetMapping
	public Mono<PageResponse<OrderResponse>> getAllOrders(
			@RequestParam(required = false) OrderStatus status,
			@RequestParam(required = false)
			@DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fromDate,
			@RequestParam(required = false)
			@DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate toDate,
			@RequestParam(defaultValue = "0") int page,
			@RequestParam(name = "pageSize", defaultValue = "20") int pageSize) {
		return orderService.getAllOrders(status, fromDate, toDate, page, pageSize);
	}

	@PutMapping("/{id}/status")
	public Mono<OrderResponse> updateOrderStatus(
			@PathVariable("id") UUID orderId,
			@RequestBody UpdateStatusRequest request) {
		return orderService.updateOrderStatus(orderId, request);
	}

	@PostMapping("/{id}/items")
	public Mono<OrderResponse> addOrderItem(
			@PathVariable("id") UUID orderId,
			@RequestBody AddItemRequest request) {
		return orderService.addOrderItem(orderId, request);
	}

	@DeleteMapping("/{id}/items/{itemId}")
	public Mono<OrderResponse> removeOrderItem(
			@PathVariable("id") UUID orderId,
			@PathVariable UUID itemId) {
		return orderService.removeOrderItem(orderId, itemId);
	}

	@DeleteMapping("/{id}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public Mono<Void> cancelOrder(@PathVariable("id") UUID orderId) {
		return orderService.cancelOrder(orderId);
	}

	@GetMapping("/summary")
	public Mono<OrderSummaryResponse> getSummary(
			@RequestParam
			@DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fromDate,
			@RequestParam
			@DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate toDate) {
		return orderService.getSummary(fromDate, toDate);
	}
}
