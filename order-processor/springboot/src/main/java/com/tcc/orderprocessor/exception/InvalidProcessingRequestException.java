package com.tcc.orderprocessor.exception;

public class InvalidProcessingRequestException extends RuntimeException {

	public InvalidProcessingRequestException(String message) {
		super(message);
	}

}