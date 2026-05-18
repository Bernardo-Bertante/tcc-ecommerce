package com.tcc.orderservice.repository;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.UUID;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderservice.domain.Order;
import com.tcc.orderservice.domain.OrderItem;
import com.tcc.orderservice.domain.OrderStatus;

import io.smallrye.mutiny.Uni;
import io.vertx.mutiny.sqlclient.Pool;
import io.vertx.mutiny.sqlclient.Row;
import io.vertx.mutiny.sqlclient.RowSet;
import io.vertx.mutiny.sqlclient.Tuple;

@ApplicationScoped
public class OrderReadRepository {

    private final Pool pgPool;

    public OrderReadRepository(Pool pgPool) {
        this.pgPool = pgPool;
    }

    public Uni<List<Order>> findByCustomerIdPaged(UUID customerId, int limit, long offset) {
        validateLimitAndOffset(limit, offset);

        return pgPool.preparedQuery("""
                SELECT *
                FROM orders
                WHERE customer_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """)
                .execute(Tuple.of(customerId, limit, offset))
                .map(this::mapOrders);
    }

    public Uni<Order> findById(UUID orderId) {
        return pgPool.preparedQuery("""
                SELECT *
                FROM orders
                WHERE id = $1
                """)
                .execute(Tuple.of(orderId))
                .map(this::mapSingleOrder);
    }

    public Uni<Long> countByCustomerId(UUID customerId) {
        return pgPool.preparedQuery("""
                SELECT COUNT(*) AS total_orders
                FROM orders
                WHERE customer_id = $1
                """)
                .execute(Tuple.of(customerId))
                .map(this::extractTotalOrders);
    }

    public Uni<List<Order>> findFilteredOrders(OrderStatus status,
            LocalDate fromDate,
            LocalDate toDate,
            int limit,
            long offset) {
        validateLimitAndOffset(limit, offset);

        QuerySpec querySpec = buildFilterQuery(status, fromDate, toDate);
        List<Object> params = new ArrayList<>(querySpec.params());
        params.add(limit);
        params.add(offset);

        String sql = "SELECT * FROM orders "
                + querySpec.whereClause()
                + " ORDER BY created_at DESC LIMIT $"
                + (params.size() - 1)
                + " OFFSET $"
                + params.size();

        return pgPool.preparedQuery(sql)
                .execute(Tuple.tuple(params))
                .map(this::mapOrders);
    }

    public Uni<Long> countFilteredOrders(OrderStatus status, LocalDate fromDate, LocalDate toDate) {
        QuerySpec querySpec = buildFilterQuery(status, fromDate, toDate);
        String sql = "SELECT COUNT(*) AS total_orders FROM orders " + querySpec.whereClause();

        return pgPool.preparedQuery(sql)
                .execute(Tuple.tuple(querySpec.params()))
                .map(this::extractTotalOrders);
    }

    public Uni<List<OrderItem>> findItemsByOrderId(UUID orderId) {
        return pgPool.preparedQuery("""
                SELECT *
                FROM order_items
                WHERE order_id = $1
                """)
                .execute(Tuple.of(orderId))
                .map(this::mapOrderItems);
    }

    public Uni<List<OrderItem>> findItemsByOrderIdIn(Collection<UUID> orderIds) {
        if (orderIds == null || orderIds.isEmpty()) {
            return Uni.createFrom().item(List.of());
        }

        return pgPool.preparedQuery("""
                SELECT *
                FROM order_items
                WHERE order_id = ANY($1)
                """)
                .execute(Tuple.of(orderIds.toArray(UUID[]::new)))
                .map(this::mapOrderItems);
    }

    private QuerySpec buildFilterQuery(OrderStatus status, LocalDate fromDate, LocalDate toDate) {
        StringBuilder whereClause = new StringBuilder("WHERE 1=1");
        List<Object> params = new ArrayList<>();

        if (status != null) {
            params.add(status.name());
            whereClause.append(" AND status = $").append(params.size());
        }

        if (fromDate != null) {
            params.add(fromDate.atStartOfDay().atOffset(ZoneOffset.UTC));
            whereClause.append(" AND created_at >= $").append(params.size());
        }

        if (toDate != null) {
            params.add(toDate.plusDays(1).atStartOfDay().atOffset(ZoneOffset.UTC));
            whereClause.append(" AND created_at < $").append(params.size());
        }

        return new QuerySpec(whereClause.toString(), params);
    }

    private List<Order> mapOrders(RowSet<Row> rows) {
        List<Order> orders = new ArrayList<>();
        for (Row row : rows) {
            orders.add(mapOrder(row));
        }

        return orders;
    }

    private Order mapSingleOrder(RowSet<Row> rows) {
        for (Row row : rows) {
            return mapOrder(row);
        }

        return null;
    }

    private Order mapOrder(Row row) {
        Order order = new Order();
        order.setId(row.getUUID("id"));
        order.setCustomerId(row.getUUID("customer_id"));

        String status = row.getString("status");
        if (status != null) {
            order.setStatus(OrderStatus.valueOf(status));
        }

        order.setTotalAmount(toBigDecimal(row.getBigDecimal("total_amount")));
        order.setDiscountAmount(toBigDecimal(row.getBigDecimal("discount_amount")));
        order.setFinalAmount(toBigDecimal(row.getBigDecimal("final_amount")));
        order.setShippingZipCode(row.getString("shipping_zip_code"));
        order.setShippingStreet(row.getString("shipping_street"));
        order.setShippingNumber(row.getString("shipping_number"));
        order.setShippingComplement(row.getString("shipping_complement"));
        order.setShippingCity(row.getString("shipping_city"));
        order.setShippingState(row.getString("shipping_state"));
        order.setCreatedAt(toLocalDateTime(row.getOffsetDateTime("created_at")));
        order.setUpdatedAt(toLocalDateTime(row.getOffsetDateTime("updated_at")));

        return order;
    }

    private List<OrderItem> mapOrderItems(RowSet<Row> rows) {
        List<OrderItem> orderItems = new ArrayList<>();
        for (Row row : rows) {
            orderItems.add(mapOrderItem(row));
        }

        return orderItems;
    }

    private OrderItem mapOrderItem(Row row) {
        OrderItem orderItem = new OrderItem();
        orderItem.setId(row.getUUID("id"));
        orderItem.setOrderId(row.getUUID("order_id"));
        orderItem.setProductId(row.getUUID("product_id"));
        orderItem.setProductName(row.getString("product_name"));
        orderItem.setQuantity(row.getInteger("quantity"));
        orderItem.setUnitPrice(toBigDecimal(row.getBigDecimal("unit_price")));
        orderItem.setSubtotal(toBigDecimal(row.getBigDecimal("subtotal")));
        return orderItem;
    }

    private long extractTotalOrders(RowSet<Row> rows) {
        for (Row row : rows) {
            Long totalOrders = row.getLong("total_orders");
            return totalOrders == null ? 0L : totalOrders;
        }

        return 0L;
    }

    private BigDecimal toBigDecimal(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }

    private LocalDateTime toLocalDateTime(OffsetDateTime value) {
        return value == null ? null : value.toLocalDateTime();
    }

    private void validateLimitAndOffset(int limit, long offset) {
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be greater than 0");
        }

        if (offset < 0) {
            throw new IllegalArgumentException("offset cannot be negative");
        }
    }

    private record QuerySpec(String whereClause, List<Object> params) {
    }
}