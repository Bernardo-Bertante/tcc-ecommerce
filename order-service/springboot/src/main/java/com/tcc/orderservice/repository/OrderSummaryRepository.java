package com.tcc.orderservice.repository;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.response.OrderSummaryResponse;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface OrderSummaryRepository {

	Mono<Long> countOrdersByDateRange(LocalDate fromDate, LocalDate toDate);

	Mono<BigDecimal> sumRevenueByDateRange(LocalDate fromDate, LocalDate toDate);

	Mono<Map<OrderStatus, Long>> countOrdersByStatusInDateRange(LocalDate fromDate, LocalDate toDate);

	Flux<OrderSummaryResponse.TopCustomerSummary> findTopCustomersByRevenue(LocalDate fromDate, LocalDate toDate, int limit);

	Flux<OrderSummaryResponse.RevenueByDaySummary> findRevenueByDay(LocalDate fromDate, LocalDate toDate);
}
