package com.tcc.orderservice.exception;

public class OrderValidationException extends RuntimeException {

	public OrderValidationException(String message) {
		super(message);
	}
}
