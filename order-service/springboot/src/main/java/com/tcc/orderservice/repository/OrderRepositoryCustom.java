package com.tcc.orderservice.repository;

import java.time.LocalDate;

import com.tcc.orderservice.domain.Order;
import com.tcc.orderservice.domain.OrderStatus;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface OrderRepositoryCustom {

	Flux<Order> findFilteredOrders(OrderStatus status, LocalDate fromDate, LocalDate toDate, int limit, long offset);

	Mono<Long> countFilteredOrders(OrderStatus status, LocalDate fromDate, LocalDate toDate);
}
