package com.tcc.orderservice.domain;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "order_status_history")
public class OrderStatusHistory {

	@Id
	private UUID id;

	@Column(name = "order_id")
	private UUID orderId;

	@Column(name = "previous_status")
	@Enumerated(EnumType.STRING)
	private OrderStatus previousStatus;

	@Column(name = "new_status")
	@Enumerated(EnumType.STRING)
	private OrderStatus newStatus;

	@Column(name = "changed_at")
	private OffsetDateTime changedAt;

	public OrderStatusHistory() {
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
		this.changedAt = toOffsetDateTime(changedAt);
	}

	public static OrderStatusHistory initial(UUID id,
			UUID orderId,
			OrderStatus newStatus,
			LocalDateTime changedAt) {
		return new OrderStatusHistory(id, orderId, null, newStatus, changedAt);
	}

	public static OrderStatusHistory transition(UUID id,
			UUID orderId,
			OrderStatus previousStatus,
			OrderStatus newStatus,
			LocalDateTime changedAt) {
		if (previousStatus == null) {
			throw new IllegalArgumentException("previousStatus cannot be null for transition history");
		}

		return new OrderStatusHistory(id, orderId, previousStatus, newStatus, changedAt);
	}

	public boolean isInitialEntry() {
		return this.previousStatus == null;
	}

	public UUID getId() {
		return id;
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
		return toLocalDateTime(changedAt);
	}

	public void setChangedAt(LocalDateTime changedAt) {
		this.changedAt = toOffsetDateTime(changedAt);
	}

	private static OffsetDateTime toOffsetDateTime(LocalDateTime value) {
		return value == null ? null : value.atOffset(ZoneOffset.UTC);
	}

	private static LocalDateTime toLocalDateTime(OffsetDateTime value) {
		return value == null ? null : value.toLocalDateTime();
	}
}
