package com.tcc.orderservice.domain;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class OrderStatusTest {

	@Test
	void shouldAllowConfiguredTransitions() {
		assertTrue(OrderStatus.PENDING.canTransitionTo(OrderStatus.CONFIRMED));
		assertTrue(OrderStatus.PENDING.canTransitionTo(OrderStatus.CANCELLED));
		assertTrue(OrderStatus.CONFIRMED.canTransitionTo(OrderStatus.PROCESSING));
		assertTrue(OrderStatus.CONFIRMED.canTransitionTo(OrderStatus.CANCELLED));
		assertTrue(OrderStatus.PROCESSING.canTransitionTo(OrderStatus.SHIPPED));
		assertTrue(OrderStatus.PROCESSING.canTransitionTo(OrderStatus.CANCELLED));
		assertTrue(OrderStatus.SHIPPED.canTransitionTo(OrderStatus.DELIVERED));
	}

	@Test
	void shouldRejectInvalidTransitions() {
		assertFalse(OrderStatus.PENDING.canTransitionTo(OrderStatus.SHIPPED));
		assertFalse(OrderStatus.CONFIRMED.canTransitionTo(OrderStatus.DELIVERED));
		assertFalse(OrderStatus.SHIPPED.canTransitionTo(OrderStatus.CANCELLED));
		assertFalse(OrderStatus.DELIVERED.canTransitionTo(OrderStatus.PENDING));
		assertFalse(OrderStatus.CANCELLED.canTransitionTo(OrderStatus.CONFIRMED));
		assertFalse(OrderStatus.PENDING.canTransitionTo(null));
	}

	@Test
	void shouldFlagTerminalAndCancellableStates() {
		assertFalse(OrderStatus.PENDING.isTerminal());
		assertTrue(OrderStatus.DELIVERED.isTerminal());
		assertTrue(OrderStatus.CANCELLED.isTerminal());

		assertTrue(OrderStatus.PENDING.canBeCancelled());
		assertTrue(OrderStatus.CONFIRMED.canBeCancelled());
		assertTrue(OrderStatus.PROCESSING.canBeCancelled());
		assertFalse(OrderStatus.SHIPPED.canBeCancelled());
		assertFalse(OrderStatus.DELIVERED.canBeCancelled());
		assertFalse(OrderStatus.CANCELLED.canBeCancelled());
	}
}