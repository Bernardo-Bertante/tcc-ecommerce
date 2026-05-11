package com.tcc.orderservice.repository;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderservice.domain.Order;
import com.tcc.orderservice.domain.OrderStatus;

import io.quarkus.hibernate.reactive.panache.PanacheQuery;
import io.quarkus.hibernate.reactive.panache.PanacheRepositoryBase;
import io.smallrye.mutiny.Uni;

@ApplicationScoped
public class OrderRepository implements PanacheRepositoryBase<Order, UUID> {

    public Uni<List<Order>> findByCustomerIdPaged(UUID customerId, int limit, long offset) {
        validateLimitAndOffset(limit, offset);

        PanacheQuery<Order> query = find("customerId = ?1 order by createdAt desc", customerId);
        return query.range(toIntExact(offset, "offset"), toIntExact(offset + limit - 1L, "offset + limit - 1")).list();
    }

    public Uni<Long> countByCustomerId(UUID customerId) {
        return count("customerId", customerId);
    }

    public Uni<List<Order>> findFilteredOrders(OrderStatus status,
            LocalDate fromDate,
            LocalDate toDate,
            int limit,
            long offset) {
        validateLimitAndOffset(limit, offset);

        QuerySpec querySpec = buildFilterQuery(status, fromDate, toDate);
        PanacheQuery<Order> query = find(querySpec.query() + " order by createdAt desc", querySpec.params());
        return query.range(toIntExact(offset, "offset"), toIntExact(offset + limit - 1L, "offset + limit - 1")).list();
    }

    public Uni<Long> countFilteredOrders(OrderStatus status, LocalDate fromDate, LocalDate toDate) {
        QuerySpec querySpec = buildFilterQuery(status, fromDate, toDate);
        return find(querySpec.query(), querySpec.params()).count();
    }

    private QuerySpec buildFilterQuery(OrderStatus status, LocalDate fromDate, LocalDate toDate) {
        StringBuilder query = new StringBuilder("1 = 1");
        List<Object> params = new ArrayList<>();

        if (status != null) {
            query.append(" and status = ?").append(params.size() + 1);
            params.add(status);
        }

        if (fromDate != null) {
            query.append(" and createdAt >= ?").append(params.size() + 1);
            params.add(fromDate.atStartOfDay().atOffset(ZoneOffset.UTC));
        }

        if (toDate != null) {
            query.append(" and createdAt < ?").append(params.size() + 1);
            params.add(toDate.plusDays(1).atStartOfDay().atOffset(ZoneOffset.UTC));
        }

        return new QuerySpec(query.toString(), params.toArray());
    }

    private void validateLimitAndOffset(int limit, long offset) {
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be greater than 0");
        }

        if (offset < 0) {
            throw new IllegalArgumentException("offset cannot be negative");
        }
    }

    private int toIntExact(long value, String label) {
        if (value > Integer.MAX_VALUE) {
            throw new IllegalArgumentException(label + " must fit in Integer range");
        }

        return (int) value;
    }

    private record QuerySpec(String query, Object[] params) {
    }
}
