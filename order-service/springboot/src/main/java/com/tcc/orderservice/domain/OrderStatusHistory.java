package com.tcc.orderservice.domain;

import java.time.LocalDateTime;
import java.util.UUID;

import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Transient;
import org.springframework.data.domain.Persistable;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("order_status_history")
public class OrderStatusHistory implements Persistable<UUID> {

	@Id
	private UUID id;

	@Column("order_id")
	private UUID orderId;

	@Column("previous_status")
	private OrderStatus previousStatus;

	@Column("new_status")
	private OrderStatus newStatus;

	@Column("changed_at")
	private LocalDateTime changedAt;

	@Transient
	private boolean newEntity;

	public OrderStatusHistory() {
		this.newEntity = false;
	}

	public OrderStatusHistory(UUID id,
			UUID orderId,
			OrderStatus previousStatus,
			OrderStatus newStatus,
			LocalDateTime changedAt) {
		if (newStatus == null) {
			throw new IllegalArgumentException("newStatus cannot be null");
		}

		this.id = id;
		this.orderId = orderId;
		this.previousStatus = previousStatus;
		this.newStatus = newStatus;
		this.changedAt = changedAt;
		this.newEntity = false;
	}

	public static OrderStatusHistory initial(UUID id,
			UUID orderId,
			OrderStatus newStatus,
			LocalDateTime changedAt) {
		OrderStatusHistory history = new OrderStatusHistory(id, orderId, null, newStatus, changedAt);
		history.markNew();
		return history;
	}

	public static OrderStatusHistory transition(UUID id,
			UUID orderId,
			OrderStatus previousStatus,
			OrderStatus newStatus,
			LocalDateTime changedAt) {
		if (previousStatus == null) {
			throw new IllegalArgumentException("previousStatus cannot be null for transition history");
		}

		OrderStatusHistory history = new OrderStatusHistory(id, orderId, previousStatus, newStatus, changedAt);
		history.markNew();
		return history;
	}

	public void markNew() {
		this.newEntity = true;
	}

	public void markPersisted() {
		this.newEntity = false;
	}

	public boolean isInitialEntry() {
		return this.previousStatus == null;
	}

	public UUID getId() {
		return id;
	}

	@Override
	public boolean isNew() {
		return this.newEntity;
	}

	public void setId(UUID id) {
		this.id = id;
	}

	public UUID getOrderId() {
		return orderId;
	}

	public void setOrderId(UUID orderId) {
		this.orderId = orderId;
	}

	public OrderStatus getPreviousStatus() {
		return previousStatus;
	}

	public void setPreviousStatus(OrderStatus previousStatus) {
		this.previousStatus = previousStatus;
	}

	public OrderStatus getNewStatus() {
		return newStatus;
	}

	public void setNewStatus(OrderStatus newStatus) {
		if (newStatus == null) {
			throw new IllegalArgumentException("newStatus cannot be null");
		}

		this.newStatus = newStatus;
	}

	public LocalDateTime getChangedAt() {
		return changedAt;
	}

	public void setChangedAt(LocalDateTime changedAt) {
		this.changedAt = changedAt;
	}
}
