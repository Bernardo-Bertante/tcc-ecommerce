package com.tcc.orderservice.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class OrderExceptionHandler {

	@ExceptionHandler(OrderNotFoundException.class)
	public ResponseEntity<ProblemDetail> handleOrderNotFound(OrderNotFoundException exception) {
		return buildProblem(
				HttpStatus.NOT_FOUND,
				"Order not found",
				exception.getMessage());
	}

	@ExceptionHandler(InvalidStatusTransitionException.class)
	public ResponseEntity<ProblemDetail> handleInvalidStatusTransition(InvalidStatusTransitionException exception) {
		return buildProblem(
				HttpStatus.UNPROCESSABLE_ENTITY,
				"Invalid status transition",
				exception.getMessage());
	}

	@ExceptionHandler(OrderValidationException.class)
	public ResponseEntity<ProblemDetail> handleOrderValidation(OrderValidationException exception) {
		return buildProblem(
				HttpStatus.BAD_REQUEST,
				"Validation error",
				exception.getMessage());
	}

	private ResponseEntity<ProblemDetail> buildProblem(HttpStatus status, String title, String detail) {
		ProblemDetail problemDetail = ProblemDetail.forStatusAndDetail(status, detail);
		problemDetail.setTitle(title);
		return ResponseEntity.status(status).body(problemDetail);
	}
}