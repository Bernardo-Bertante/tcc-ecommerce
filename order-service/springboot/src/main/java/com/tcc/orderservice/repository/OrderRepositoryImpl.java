package com.tcc.orderservice.repository;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;

import com.tcc.orderservice.domain.Order;
import com.tcc.orderservice.domain.OrderStatus;

import io.r2dbc.spi.Row;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class OrderRepositoryImpl implements OrderRepositoryCustom {

	private final DatabaseClient databaseClient;

	public OrderRepositoryImpl(DatabaseClient databaseClient) {
		this.databaseClient = databaseClient;
	}

	@Override
	public Flux<Order> findFilteredOrders(OrderStatus status,
			LocalDate fromDate,
			LocalDate toDate,
			int limit,
			long offset) {
		if (limit <= 0) {
			throw new IllegalArgumentException("limit must be greater than 0");
		}

		if (offset < 0) {
			throw new IllegalArgumentException("offset cannot be negative");
		}

		QueryFragment queryFragment = buildFilterFragment(status, fromDate, toDate);
		String sql = "SELECT * FROM orders "
				+ queryFragment.whereClause()
				+ " ORDER BY created_at DESC LIMIT :limit OFFSET :offset";

		Map<String, Object> params = new LinkedHashMap<>(queryFragment.params());
		params.put("limit", limit);
		params.put("offset", offset);

		return bindAll(databaseClient.sql(sql), params)
				.map((row, metadata) -> mapOrder(row))
				.all();
	}

	@Override
	public Mono<Long> countFilteredOrders(OrderStatus status, LocalDate fromDate, LocalDate toDate) {
		QueryFragment queryFragment = buildFilterFragment(status, fromDate, toDate);
		String sql = "SELECT COUNT(*) AS total_orders FROM orders " + queryFragment.whereClause();

		return bindAll(databaseClient.sql(sql), queryFragment.params())
				.map((row, metadata) -> toLong(row.get("total_orders")))
				.one()
				.defaultIfEmpty(0L);
	}

	private QueryFragment buildFilterFragment(OrderStatus status, LocalDate fromDate, LocalDate toDate) {
		Map<String, Object> params = new LinkedHashMap<>();
		StringBuilder whereClause = new StringBuilder("WHERE 1=1");

		if (status != null) {
			whereClause.append(" AND status = :status");
			params.put("status", status.name());
		}

		if (fromDate != null) {
			whereClause.append(" AND created_at >= :fromTimestamp");
			params.put("fromTimestamp", fromDate.atStartOfDay());
		}

		if (toDate != null) {
			whereClause.append(" AND created_at < :toTimestamp");
			params.put("toTimestamp", toDate.plusDays(1).atStartOfDay());
		}

		return new QueryFragment(whereClause.toString(), params);
	}

	private DatabaseClient.GenericExecuteSpec bindAll(DatabaseClient.GenericExecuteSpec executeSpec,
			Map<String, Object> params) {
		DatabaseClient.GenericExecuteSpec boundSpec = executeSpec;
		for (Map.Entry<String, Object> param : params.entrySet()) {
			boundSpec = boundSpec.bind(param.getKey(), param.getValue());
		}

		return boundSpec;
	}

	private Order mapOrder(Row row) {
		Order order = new Order();
		order.setId(row.get("id", UUID.class));
		order.setCustomerId(row.get("customer_id", UUID.class));

		String status = row.get("status", String.class);
		if (status != null) {
			order.setStatus(OrderStatus.valueOf(status));
		}

		order.setTotalAmount(toBigDecimal(row.get("total_amount")));
		order.setDiscountAmount(toBigDecimal(row.get("discount_amount")));
		order.setFinalAmount(toBigDecimal(row.get("final_amount")));
		order.setShippingZipCode(row.get("shipping_zip_code", String.class));
		order.setShippingStreet(row.get("shipping_street", String.class));
		order.setShippingNumber(row.get("shipping_number", String.class));
		order.setShippingComplement(row.get("shipping_complement", String.class));
		order.setShippingCity(row.get("shipping_city", String.class));
		order.setShippingState(row.get("shipping_state", String.class));
		order.setCreatedAt(toLocalDateTime(row.get("created_at")));
		order.setUpdatedAt(toLocalDateTime(row.get("updated_at")));

		return order;
	}

	private Long toLong(Object value) {
		if (value == null) {
			return 0L;
		}

		if (value instanceof Number number) {
			return number.longValue();
		}

		return Long.parseLong(value.toString());
	}

	private BigDecimal toBigDecimal(Object value) {
		if (value == null) {
			return BigDecimal.ZERO;
		}

		if (value instanceof BigDecimal decimal) {
			return decimal;
		}

		if (value instanceof Number number) {
			return new BigDecimal(number.toString());
		}

		return new BigDecimal(value.toString());
	}

	private LocalDateTime toLocalDateTime(Object value) {
		if (value == null) {
			return null;
		}

		if (value instanceof LocalDateTime localDateTime) {
			return localDateTime;
		}

		if (value instanceof OffsetDateTime offsetDateTime) {
			return offsetDateTime.toLocalDateTime();
		}

		if (value instanceof Instant instant) {
			return instant.atOffset(ZoneOffset.UTC).toLocalDateTime();
		}

		if (value instanceof ZonedDateTime zonedDateTime) {
			return zonedDateTime.toLocalDateTime();
		}

		throw new IllegalArgumentException("Unsupported datetime type: " + value.getClass().getName());
	}

	private record QueryFragment(String whereClause, Map<String, Object> params) {
	}
}
