package com.tcc.orderservice.repository;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.response.OrderSummaryResponse;

import io.smallrye.mutiny.Uni;
import io.vertx.mutiny.sqlclient.Pool;
import io.vertx.mutiny.sqlclient.Row;
import io.vertx.mutiny.sqlclient.RowSet;
import io.vertx.mutiny.sqlclient.Tuple;

@ApplicationScoped
public class OrderSummaryRepository {

    private final Pool pgPool;

    public OrderSummaryRepository(Pool pgPool) {
        this.pgPool = pgPool;
    }

    public Uni<Long> countOrdersByDateRange(LocalDate fromDate, LocalDate toDate) {
        DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

        return pgPool.preparedQuery("""
                SELECT COUNT(*) AS total_orders
                FROM orders
                WHERE created_at >= $1
                  AND created_at < $2
                """)
                .execute(Tuple.of(dateRange.fromTimestamp(), dateRange.toTimestamp()))
                .map(this::extractTotalOrders);
    }

    public Uni<BigDecimal> sumRevenueByDateRange(LocalDate fromDate, LocalDate toDate) {
        DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

        return pgPool.preparedQuery("""
                SELECT COALESCE(SUM(final_amount), 0) AS total_revenue
                FROM orders
                WHERE created_at >= $1
                  AND created_at < $2
                """)
                .execute(Tuple.of(dateRange.fromTimestamp(), dateRange.toTimestamp()))
                .map(this::extractTotalRevenue);
    }

    public Uni<Map<OrderStatus, Long>> countOrdersByStatusInDateRange(LocalDate fromDate, LocalDate toDate) {
        DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

        return pgPool.preparedQuery("""
                SELECT status, COUNT(*) AS total_orders
                FROM orders
                WHERE created_at >= $1
                  AND created_at < $2
                GROUP BY status
                """)
                .execute(Tuple.of(dateRange.fromTimestamp(), dateRange.toTimestamp()))
                .map(this::mapStatusCounts);
    }

    public Uni<List<OrderSummaryResponse.TopCustomerSummary>> findTopCustomersByRevenue(LocalDate fromDate,
            LocalDate toDate,
            int limit) {
        DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be greater than 0");
        }

        return pgPool.preparedQuery("""
                SELECT customer_id,
                       COALESCE(SUM(final_amount), 0) AS total_spent,
                       COUNT(*) AS order_count
                FROM orders
                WHERE created_at >= $1
                  AND created_at < $2
                GROUP BY customer_id
                ORDER BY total_spent DESC, order_count DESC
                LIMIT $3
                """)
                .execute(Tuple.of(dateRange.fromTimestamp(), dateRange.toTimestamp(), limit))
                .map(this::mapTopCustomers);
    }

    public Uni<List<OrderSummaryResponse.RevenueByDaySummary>> findRevenueByDay(LocalDate fromDate, LocalDate toDate) {
        DateRange dateRange = validateAndBuildDateRange(fromDate, toDate);

        return pgPool.preparedQuery("""
                SELECT CAST(created_at AT TIME ZONE 'UTC' AS DATE) AS revenue_day,
                       COALESCE(SUM(final_amount), 0) AS revenue,
                       COUNT(*) AS order_count
                FROM orders
                WHERE created_at >= $1
                  AND created_at < $2
                GROUP BY CAST(created_at AT TIME ZONE 'UTC' AS DATE)
                ORDER BY revenue_day ASC
                """)
                .execute(Tuple.of(dateRange.fromTimestamp(), dateRange.toTimestamp()))
                .map(this::mapRevenueByDay);
    }

    private long extractTotalOrders(RowSet<Row> rows) {
        for (Row row : rows) {
            Long totalOrders = row.getLong("total_orders");
            return totalOrders == null ? 0L : totalOrders;
        }

        return 0L;
    }

    private BigDecimal extractTotalRevenue(RowSet<Row> rows) {
        for (Row row : rows) {
            BigDecimal totalRevenue = row.getBigDecimal("total_revenue");
            return totalRevenue == null ? BigDecimal.ZERO : totalRevenue;
        }

        return BigDecimal.ZERO;
    }

    private Map<OrderStatus, Long> mapStatusCounts(RowSet<Row> rows) {
        EnumMap<OrderStatus, Long> counts = new EnumMap<>(OrderStatus.class);
        for (Row row : rows) {
            OrderStatus status = OrderStatus.valueOf(row.getString("status"));
            Long totalOrders = row.getLong("total_orders");
            counts.put(status, totalOrders == null ? 0L : totalOrders);
        }

        return counts;
    }

    private List<OrderSummaryResponse.TopCustomerSummary> mapTopCustomers(RowSet<Row> rows) {
        List<OrderSummaryResponse.TopCustomerSummary> topCustomers = new ArrayList<>();
        for (Row row : rows) {
            BigDecimal totalSpent = row.getBigDecimal("total_spent");
            Long orderCount = row.getLong("order_count");
            topCustomers.add(new OrderSummaryResponse.TopCustomerSummary(
                    row.getUUID("customer_id"),
                    totalSpent == null ? BigDecimal.ZERO : totalSpent,
                    orderCount == null ? 0L : orderCount));
        }

        return topCustomers;
    }

    private List<OrderSummaryResponse.RevenueByDaySummary> mapRevenueByDay(RowSet<Row> rows) {
        List<OrderSummaryResponse.RevenueByDaySummary> revenueByDay = new ArrayList<>();
        for (Row row : rows) {
            BigDecimal revenue = row.getBigDecimal("revenue");
            Long orderCount = row.getLong("order_count");
            revenueByDay.add(new OrderSummaryResponse.RevenueByDaySummary(
                    row.getLocalDate("revenue_day"),
                    revenue == null ? BigDecimal.ZERO : revenue,
                    orderCount == null ? 0L : orderCount));
        }

        return revenueByDay;
    }

    private DateRange validateAndBuildDateRange(LocalDate fromDate, LocalDate toDate) {
        if (fromDate == null || toDate == null) {
            throw new IllegalArgumentException("fromDate and toDate are required");
        }

        if (fromDate.isAfter(toDate)) {
            throw new IllegalArgumentException("fromDate cannot be after toDate");
        }

        OffsetDateTime fromTimestamp = fromDate.atStartOfDay().atOffset(ZoneOffset.UTC);
        OffsetDateTime toTimestamp = toDate.plusDays(1).atStartOfDay().atOffset(ZoneOffset.UTC);
        return new DateRange(fromTimestamp, toTimestamp);
    }

    private record DateRange(OffsetDateTime fromTimestamp, OffsetDateTime toTimestamp) {
    }
}
