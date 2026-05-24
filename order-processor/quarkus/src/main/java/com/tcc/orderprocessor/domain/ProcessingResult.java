package com.tcc.orderprocessor.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

public record ProcessingResult(
		UUID orderId,
		String fiscalNumber,
		BigDecimal shippingCost,
		BigDecimal taxAmount,
		BigDecimal finalAmount,
		int estimatedDeliveryDays,
		LocalDateTime processedAt
) {
}