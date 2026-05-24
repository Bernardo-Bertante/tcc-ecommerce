package com.tcc.orderprocessor.domain;

import java.math.BigDecimal;
import java.util.UUID;

public record ProcessingItem(
		UUID productId,
		String productName,
		int quantity,
		BigDecimal unitPrice
) {
}