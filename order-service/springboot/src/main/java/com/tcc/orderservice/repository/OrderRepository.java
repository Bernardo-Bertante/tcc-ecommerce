package com.tcc.orderservice.repository;

import java.util.UUID;

import org.springframework.data.r2dbc.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import com.tcc.orderservice.domain.Order;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface OrderRepository extends ReactiveCrudRepository<Order, UUID>, OrderRepositoryCustom {

	@Query("""
			SELECT *
			FROM orders
			WHERE customer_id = :customerId
			ORDER BY created_at DESC
			LIMIT :limit OFFSET :offset
			""")
	Flux<Order> findByCustomerIdPaged(@Param("customerId") UUID customerId,
				@Param("limit") int limit,
				@Param("offset") long offset);

	@Query("""
			SELECT COUNT(*)
			FROM orders
			WHERE customer_id = :customerId
			""")
	Mono<Long> countByCustomerId(@Param("customerId") UUID customerId);
}
