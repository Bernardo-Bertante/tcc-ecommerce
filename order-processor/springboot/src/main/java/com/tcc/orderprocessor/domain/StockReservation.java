package com.tcc.orderprocessor.domain;

import java.time.LocalDateTime;
import java.util.UUID;

public record StockReservation(
		UUID orderId,
		UUID productId,
		int quantity,
		LocalDateTime reservedAt
) {
}