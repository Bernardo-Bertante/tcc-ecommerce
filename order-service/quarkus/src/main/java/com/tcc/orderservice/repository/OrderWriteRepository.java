package com.tcc.orderservice.repository;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderservice.domain.Order;
import com.tcc.orderservice.domain.OrderItem;
import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.domain.OrderStatusHistory;

import io.smallrye.mutiny.Uni;
import io.vertx.mutiny.sqlclient.Pool;
import io.vertx.mutiny.sqlclient.SqlClient;
import io.vertx.mutiny.sqlclient.Tuple;

/**
 * Raw reactive write repository used by hot write paths to avoid holding a
 * Hibernate Reactive session for the duration of a sequence of sequential
 * persists. Multi-statement write flows reuse a single leased connection, but
 * they still execute without an explicit SQL transaction so each statement
 * preserves the Spring reference semantics.
 */
@ApplicationScoped
public class OrderWriteRepository {

    private static final String INSERT_ORDER_SQL = """
            INSERT INTO orders (
                id, customer_id, status,
                total_amount, discount_amount, final_amount,
                shipping_zip_code, shipping_street, shipping_number,
                shipping_complement, shipping_city, shipping_state,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6,
                $7, $8, $9,
                $10, $11, $12,
                $13, $14
            )
            """;

    private static final String INSERT_ORDER_ITEM_SQL = """
            INSERT INTO order_items (
                id, order_id, product_id, product_name,
                quantity, unit_price, subtotal
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7
            )
            """;

    private static final String INSERT_ORDER_STATUS_HISTORY_SQL = """
            INSERT INTO order_status_history (
                id, order_id, previous_status, new_status, changed_at
            ) VALUES (
                $1, $2, $3, $4, $5
            )
            """;

    private static final String UPDATE_ORDER_STATUS_SQL = """
            UPDATE orders
            SET status = $1,
                updated_at = $2
            WHERE id = $3
            """;

    private final Pool pgPool;

    public OrderWriteRepository(Pool pgPool) {
        this.pgPool = pgPool;
    }

    public Uni<Void> createOrderWithItemsAndHistory(Order order,
            List<OrderItem> items,
            OrderStatusHistory initialHistory) {
        if (order == null) {
            throw new IllegalArgumentException("order is required");
        }
        if (items == null || items.isEmpty()) {
            throw new IllegalArgumentException("items is required");
        }
        if (initialHistory == null) {
            throw new IllegalArgumentException("initialHistory is required");
        }

        return pgPool.withConnection(connection -> insertOrder(connection, order)
            .chain(() -> insertOrderItemsBatch(connection, items))
            .chain(() -> insertOrderStatusHistory(connection, initialHistory)))
                .replaceWithVoid();
    }

    public Uni<Void> updateOrderStatusWithHistory(Order order, OrderStatusHistory history) {
        if (order == null) {
            throw new IllegalArgumentException("order is required");
        }
        if (history == null) {
            throw new IllegalArgumentException("history is required");
        }

        return pgPool.withConnection(connection -> updateOrderStatus(connection, order)
            .chain(() -> insertOrderStatusHistory(connection, history)))
                .replaceWithVoid();
    }

    private Uni<Void> insertOrder(SqlClient client, Order order) {
        Tuple tuple = Tuple.from(Arrays.asList(
                order.getId(),
                order.getCustomerId(),
                order.getStatus() == null ? OrderStatus.PENDING.name() : order.getStatus().name(),
                order.getTotalAmount(),
                order.getDiscountAmount(),
                order.getFinalAmount(),
                order.getShippingZipCode(),
                order.getShippingStreet(),
                order.getShippingNumber(),
                order.getShippingComplement(),
                order.getShippingCity(),
                order.getShippingState(),
                toOffsetDateTime(order.getCreatedAt()),
                toOffsetDateTime(order.getUpdatedAt())));

        return client.preparedQuery(INSERT_ORDER_SQL)
                .execute(tuple)
                .replaceWithVoid();
    }

    private Uni<Void> insertOrderItemsBatch(SqlClient client, List<OrderItem> items) {
        List<Tuple> batch = new ArrayList<>(items.size());
        for (OrderItem item : items) {
            batch.add(Tuple.from(Arrays.asList(
                    item.getId(),
                    item.getOrderId(),
                    item.getProductId(),
                    item.getProductName(),
                    item.getQuantity(),
                    item.getUnitPrice(),
                    item.getSubtotal())));
        }

        return client.preparedQuery(INSERT_ORDER_ITEM_SQL)
                .executeBatch(batch)
                .replaceWithVoid();
    }

    private Uni<Void> updateOrderStatus(SqlClient client, Order order) {
        Tuple tuple = Tuple.from(Arrays.asList(
                order.getStatus() == null ? null : order.getStatus().name(),
                toOffsetDateTime(order.getUpdatedAt()),
                order.getId()));

        return client.preparedQuery(UPDATE_ORDER_STATUS_SQL)
                .execute(tuple)
                .replaceWithVoid();
    }

    private Uni<Void> insertOrderStatusHistory(SqlClient client, OrderStatusHistory history) {
        Tuple tuple = Tuple.from(Arrays.asList(
                history.getId(),
                history.getOrderId(),
                history.getPreviousStatus() == null ? null : history.getPreviousStatus().name(),
                history.getNewStatus() == null ? null : history.getNewStatus().name(),
                toOffsetDateTime(history.getChangedAt())));

        return client.preparedQuery(INSERT_ORDER_STATUS_HISTORY_SQL)
                .execute(tuple)
                .replaceWithVoid();
    }

    private static OffsetDateTime toOffsetDateTime(LocalDateTime value) {
        return value == null ? null : value.atOffset(ZoneOffset.UTC);
    }
}
