package com.tcc.orderprocessor.service;

import java.math.BigDecimal;
import java.util.List;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderprocessor.domain.Address;
import com.tcc.orderprocessor.domain.ProcessingItem;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.exception.InvalidProcessingRequestException;

@ApplicationScoped
public class ProcessingRequestValidator {

	public void validate(ProcessingRequest request) {
		if (request == null) {
			throw invalid("request is required");
		}
		if (request.orderId() == null) {
			throw invalid("orderId is required");
		}
		if (request.customerId() == null) {
			throw invalid("customerId is required");
		}
		validateItems(request.items());
		validateAddress(request.shippingAddress());
		if (request.totalAmount() == null || request.totalAmount().compareTo(BigDecimal.ZERO) <= 0) {
			throw invalid("totalAmount must be greater than zero");
		}
	}

	private void validateItems(List<ProcessingItem> items) {
		if (items == null || items.isEmpty()) {
			throw invalid("items must contain at least one item");
		}

		for (int index = 0; index < items.size(); index += 1) {
			ProcessingItem item = items.get(index);
			if (item == null) {
				throw invalid("items[%d] is required".formatted(index));
			}
			if (item.productId() == null) {
				throw invalid("items[%d].productId is required".formatted(index));
			}
			if (isBlank(item.productName())) {
				throw invalid("items[%d].productName is required".formatted(index));
			}
			if (item.quantity() < 1) {
				throw invalid("items[%d].quantity must be at least 1".formatted(index));
			}
			if (item.unitPrice() == null || item.unitPrice().compareTo(BigDecimal.ZERO) <= 0) {
				throw invalid("items[%d].unitPrice must be greater than zero".formatted(index));
			}
		}
	}

	private void validateAddress(Address address) {
		if (address == null) {
			throw invalid("shippingAddress is required");
		}
		if (isBlank(address.zipCode())) {
			throw invalid("shippingAddress.zipCode is required");
		}
		if (isBlank(address.state())) {
			throw invalid("shippingAddress.state is required");
		}
		if (address.state().trim().length() != 2) {
			throw invalid("shippingAddress.state must contain exactly 2 characters");
		}
		if (isBlank(address.city())) {
			throw invalid("shippingAddress.city is required");
		}
	}

	private InvalidProcessingRequestException invalid(String message) {
		return new InvalidProcessingRequestException(message);
	}

	private boolean isBlank(String value) {
		return value == null || value.isBlank();
	}

}