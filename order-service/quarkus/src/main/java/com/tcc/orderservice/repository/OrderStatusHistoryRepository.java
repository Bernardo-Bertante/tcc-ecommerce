package com.tcc.orderservice.repository;

import java.util.List;
import java.util.UUID;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderservice.domain.OrderStatusHistory;

import io.quarkus.hibernate.reactive.panache.PanacheRepositoryBase;
import io.smallrye.mutiny.Uni;

@ApplicationScoped
public class OrderStatusHistoryRepository implements PanacheRepositoryBase<OrderStatusHistory, UUID> {

    public Uni<List<OrderStatusHistory>> findByOrderIdOrderByChangedAtAsc(UUID orderId) {
        return find("orderId = ?1 order by changedAt asc", orderId).list();
    }
}
