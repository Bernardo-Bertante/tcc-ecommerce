package com.tcc.orderservice.repository;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.EnumMap;
import java.util.Map;
import java.util.UUID;

import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.response.OrderSummaryResponse;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class OrderSummaryRepositoryImpl implements OrderSummaryRepository {

	private final DatabaseClient databaseClient;

	public OrderSummaryRepositoryImpl(DatabaseClient databaseClient) {
		this.databaseClient = databaseClient;
	}

	@Override
	public Mono<Long> countOrdersByDateRange(LocalDate fromDate, LocalDate toDate) {
		DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

		return databaseClient.sql("""
				SELECT COUNT(*) AS total_orders
				FROM orders
				WHERE created_at >= :fromTimestamp
				  AND created_at < :toTimestamp
				""")
				.bind("fromTimestamp", dateRange.fromTimestamp())
				.bind("toTimestamp", dateRange.toTimestamp())
				.map((row, metadata) -> toLong(row.get("total_orders")))
				.one()
				.defaultIfEmpty(0L);
	}

	@Override
	public Mono<BigDecimal> sumRevenueByDateRange(LocalDate fromDate, LocalDate toDate) {
		DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

		return databaseClient.sql("""
				SELECT COALESCE(SUM(final_amount), 0) AS total_revenue
				FROM orders
				WHERE created_at >= :fromTimestamp
				  AND created_at < :toTimestamp
				""")
				.bind("fromTimestamp", dateRange.fromTimestamp())
				.bind("toTimestamp", dateRange.toTimestamp())
				.map((row, metadata) -> toBigDecimal(row.get("total_revenue")))
				.one()
				.defaultIfEmpty(BigDecimal.ZERO);
	}

	@Override
	public Mono<Map<OrderStatus, Long>> countOrdersByStatusInDateRange(LocalDate fromDate, LocalDate toDate) {
		DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

		return databaseClient.sql("""
				SELECT status, COUNT(*) AS total_orders
				FROM orders
				WHERE created_at >= :fromTimestamp
				  AND created_at < :toTimestamp
				GROUP BY status
				""")
				.bind("fromTimestamp", dateRange.fromTimestamp())
				.bind("toTimestamp", dateRange.toTimestamp())
				.map((row, metadata) -> Map.entry(
						OrderStatus.valueOf(row.get("status", String.class)),
						toLong(row.get("total_orders"))
				))
				.all()
				.reduceWith(() -> initializeStatusCounts(),
						(statusCountMap, entry) -> {
							statusCountMap.put(entry.getKey(), entry.getValue());
							return statusCountMap;
						})
				.map(map -> (Map<OrderStatus, Long>) map);
	}

	@Override
	public Flux<OrderSummaryResponse.TopCustomerSummary> findTopCustomersByRevenue(LocalDate fromDate,
			LocalDate toDate,
			int limit) {
		DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);
		if (limit <= 0) {
			throw new IllegalArgumentException("limit must be greater than 0");
		}

		return databaseClient.sql("""
				SELECT customer_id,
				       COALESCE(SUM(final_amount), 0) AS total_spent,
				       COUNT(*) AS order_count
				FROM orders
				WHERE created_at >= :fromTimestamp
				  AND created_at < :toTimestamp
				GROUP BY customer_id
				ORDER BY total_spent DESC, order_count DESC
				LIMIT :limit
				""")
				.bind("fromTimestamp", dateRange.fromTimestamp())
				.bind("toTimestamp", dateRange.toTimestamp())
				.bind("limit", limit)
				.map((row, metadata) -> new OrderSummaryResponse.TopCustomerSummary(
						row.get("customer_id", UUID.class),
						toBigDecimal(row.get("total_spent")),
						toLong(row.get("order_count"))
				))
				.all();
	}

	@Override
	public Flux<OrderSummaryResponse.RevenueByDaySummary> findRevenueByDay(LocalDate fromDate, LocalDate toDate) {
		DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

		return databaseClient.sql("""
				SELECT CAST(created_at AT TIME ZONE 'UTC' AS DATE) AS revenue_day,
				       COALESCE(SUM(final_amount), 0) AS revenue,
				       COUNT(*) AS order_count
				FROM orders
				WHERE created_at >= :fromTimestamp
				  AND created_at < :toTimestamp
				GROUP BY CAST(created_at AT TIME ZONE 'UTC' AS DATE)
				ORDER BY revenue_day ASC
				""")
				.bind("fromTimestamp", dateRange.fromTimestamp())
				.bind("toTimestamp", dateRange.toTimestamp())
				.map((row, metadata) -> new OrderSummaryResponse.RevenueByDaySummary(
						row.get("revenue_day", LocalDate.class),
						toBigDecimal(row.get("revenue")),
						toLong(row.get("order_count"))
				))
				.all();
	}

	private DateRange validateAndBuildDateRange(LocalDate fromDate, LocalDate toDate) {
		if (fromDate == null || toDate == null) {
			throw new IllegalArgumentException("fromDate and toDate are required");
		}

		if (fromDate.isAfter(toDate)) {
			throw new IllegalArgumentException("fromDate cannot be after toDate");
		}

		LocalDateTime fromTimestamp = fromDate.atStartOfDay();
		LocalDateTime toTimestamp = toDate.plusDays(1).atStartOfDay();
		return new DateRange(fromTimestamp, toTimestamp);
	}

	private EnumMap<OrderStatus, Long> initializeStatusCounts() {
		EnumMap<OrderStatus, Long> statusCounts = new EnumMap<>(OrderStatus.class);
		for (OrderStatus status : OrderStatus.values()) {
			statusCounts.put(status, 0L);
		}

		return statusCounts;
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

	private record DateRange(LocalDateTime fromTimestamp, LocalDateTime toTimestamp) {
	}
}
