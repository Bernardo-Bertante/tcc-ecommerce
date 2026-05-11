package com.tcc.orderservice.exception;

import com.tcc.orderservice.domain.OrderStatus;

public class InvalidStatusTransitionException extends RuntimeException {

	public InvalidStatusTransitionException(OrderStatus currentStatus, OrderStatus nextStatus) {
		super("Invalid status transition: " + currentStatus + " -> " + nextStatus);
	}
}
