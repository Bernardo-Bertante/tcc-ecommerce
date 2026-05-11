package com.tcc.orderservice.domain;

public enum OrderStatus {
	PENDING,
	CONFIRMED,
	PROCESSING,
	SHIPPED,
	DELIVERED,
	CANCELLED;

	public boolean canTransitionTo(OrderStatus nextStatus) {
		if (nextStatus == null) {
			return false;
		}

		return switch (this) {
			case PENDING -> nextStatus == CONFIRMED || nextStatus == CANCELLED;
			case CONFIRMED -> nextStatus == PROCESSING || nextStatus == CANCELLED;
			case PROCESSING -> nextStatus == SHIPPED || nextStatus == CANCELLED;
			case SHIPPED -> nextStatus == DELIVERED;
			case DELIVERED, CANCELLED -> false;
		};
	}

	public void assertCanTransitionTo(OrderStatus nextStatus) {
		if (!canTransitionTo(nextStatus)) {
			throw new IllegalStateException("Invalid status transition: " + this + " -> " + nextStatus);
		}
	}

	public boolean canBeCancelled() {
		return canTransitionTo(CANCELLED);
	}

	public boolean isTerminal() {
		return this == DELIVERED || this == CANCELLED;
	}
}
