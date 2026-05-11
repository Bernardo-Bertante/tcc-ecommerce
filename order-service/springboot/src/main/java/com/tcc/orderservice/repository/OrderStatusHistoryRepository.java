package com.tcc.orderservice.repository;

import java.util.UUID;

import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import com.tcc.orderservice.domain.OrderStatusHistory;

import reactor.core.publisher.Flux;

public interface OrderStatusHistoryRepository extends ReactiveCrudRepository<OrderStatusHistory, UUID> {

	Flux<OrderStatusHistory> findByOrderIdOrderByChangedAtAsc(UUID orderId);
}
