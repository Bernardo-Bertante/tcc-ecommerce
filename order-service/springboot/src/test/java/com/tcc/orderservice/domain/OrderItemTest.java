package com.tcc.orderservice.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import java.util.UUID;

import org.junit.jupiter.api.Test;

class OrderItemTest {

	@Test
	void shouldRecalculateSubtotalWithHalfUpRounding() {
		OrderItem item = new OrderItem(
				UUID.randomUUID(),
				UUID.randomUUID(),
				UUID.randomUUID(),
				"Notebook",
				3,
				new BigDecimal("10.005"),
				null
		);

		assertEquals(new BigDecimal("30.03"), item.getSubtotal());
	}

	@Test
	void shouldRejectInvalidQuantity() {
		assertThrows(IllegalArgumentException.class, () -> new OrderItem(
				UUID.randomUUID(),
				UUID.randomUUID(),
				UUID.randomUUID(),
				"Notebook",
				0,
				new BigDecimal("10.00"),
				null
		));
	}

	@Test
	void shouldRejectInvalidUnitPrice() {
		assertThrows(IllegalArgumentException.class, () -> new OrderItem(
				UUID.randomUUID(),
				UUID.randomUUID(),
				UUID.randomUUID(),
				"Notebook",
				1,
				BigDecimal.ZERO,
				null
		));
	}
}