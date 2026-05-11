package com.tcc.orderservice.dto.response;

import java.time.LocalDateTime;
import java.util.UUID;

import com.tcc.orderservice.domain.OrderStatus;

public class OrderStatusHistoryResponse {

	private UUID id;
	private UUID orderId;
	private OrderStatus previousStatus;
	private OrderStatus newStatus;
	private LocalDateTime changedAt;

	public OrderStatusHistoryResponse() {
	}

	public OrderStatusHistoryResponse(UUID id,
			UUID orderId,
			OrderStatus previousStatus,
			OrderStatus newStatus,
			LocalDateTime changedAt) {
		this.id = id;
		this.orderId = orderId;
		this.previousStatus = previousStatus;
		this.newStatus = newStatus;
		this.changedAt = changedAt;
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
		this.newStatus = newStatus;
	}

	public LocalDateTime getChangedAt() {
		return changedAt;
	}

	public void setChangedAt(LocalDateTime changedAt) {
		this.changedAt = changedAt;
	}
}
