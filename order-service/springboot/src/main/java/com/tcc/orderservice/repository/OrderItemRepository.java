package com.tcc.orderservice.repository;

import java.util.Collection;
import java.util.UUID;

import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import com.tcc.orderservice.domain.OrderItem;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface OrderItemRepository extends ReactiveCrudRepository<OrderItem, UUID> {

	Flux<OrderItem> findByOrderId(UUID orderId);

	Flux<OrderItem> findByOrderIdIn(Collection<UUID> orderIds);

	Mono<Void> deleteByIdAndOrderId(UUID id, UUID orderId);
}
