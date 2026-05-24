package com.tcc.orderprocessor.domain;

public record Address(
		String zipCode,
		String state,
		String city
) {
}