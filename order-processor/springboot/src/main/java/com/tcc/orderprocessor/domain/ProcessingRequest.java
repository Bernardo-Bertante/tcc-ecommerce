package com.tcc.orderprocessor.domain;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record ProcessingRequest(
		UUID orderId,
		UUID customerId,
		List<ProcessingItem> items,
		Address shippingAddress,
		BigDecimal totalAmount
) {
}