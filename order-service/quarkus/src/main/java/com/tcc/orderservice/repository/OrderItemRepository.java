package com.tcc.orderservice.repository;

import java.util.Collection;
import java.util.List;
import java.util.UUID;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderservice.domain.OrderItem;

import io.quarkus.hibernate.reactive.panache.PanacheRepositoryBase;
import io.smallrye.mutiny.Uni;

@ApplicationScoped
public class OrderItemRepository implements PanacheRepositoryBase<OrderItem, UUID> {

    public Uni<List<OrderItem>> findByOrderId(UUID orderId) {
        return find("orderId", orderId).list();
    }

    public Uni<List<OrderItem>> findByOrderIdIn(Collection<UUID> orderIds) {
        if (orderIds == null || orderIds.isEmpty()) {
            return Uni.createFrom().item(List.of());
        }

        return find("orderId in ?1", orderIds).list();
    }

    public Uni<Void> deleteByIdAndOrderId(UUID id, UUID orderId) {
        return find("id = ?1 and orderId = ?2", id, orderId)
                .firstResult()
                .onItem()
                .transformToUni(orderItem -> orderItem == null
                        ? Uni.createFrom().voidItem()
                        : delete(orderItem));
    }
}
