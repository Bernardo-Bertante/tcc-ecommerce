package com.tcc.orderservice.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.Test;

class OrderTest {

	@Test
	void shouldRecalculateFinalAmountWithHalfUpRounding() {
		Order order = new Order();
		order.setTotalAmount(new BigDecimal("100.005"));
		order.setDiscountAmount(new BigDecimal("10.004"));

		order.recalculateFinalAmount();

		assertEquals(new BigDecimal("100.01"), order.getTotalAmount());
		assertEquals(new BigDecimal("10.00"), order.getDiscountAmount());
		assertEquals(new BigDecimal("90.01"), order.getFinalAmount());
		assertTrue(order.hasConsistentAmounts());
	}

	@Test
	void shouldRecalculateAmountsFromItems() {
		OrderItem itemOne = new OrderItem(
				UUID.randomUUID(),
				UUID.randomUUID(),
				UUID.randomUUID(),
				"Teclado",
				2,
				new BigDecimal("10.00"),
				null
		);
		OrderItem itemTwo = new OrderItem(
				UUID.randomUUID(),
				UUID.randomUUID(),
				UUID.randomUUID(),
				"Mouse",
				1,
				new BigDecimal("5.555"),
				null
		);

		Order order = new Order();
		order.setItems(List.of(itemOne, itemTwo));
		order.setDiscountAmount(new BigDecimal("1.111"));

		order.recalculateAmountsFromItems();

		assertEquals(new BigDecimal("25.56"), order.getTotalAmount());
		assertEquals(new BigDecimal("1.11"), order.getDiscountAmount());
		assertEquals(new BigDecimal("24.45"), order.getFinalAmount());
		assertTrue(order.hasConsistentAmounts());
	}

	@Test
	void shouldRejectDiscountGreaterThanTotalAmount() {
		Order order = new Order();
		order.setTotalAmount(new BigDecimal("10.00"));
		order.setDiscountAmount(new BigDecimal("10.01"));

		assertThrows(IllegalArgumentException.class, order::recalculateFinalAmount);
	}
}
