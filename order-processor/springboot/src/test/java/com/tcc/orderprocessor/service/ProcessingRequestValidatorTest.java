package com.tcc.orderprocessor.service;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.domain.Address;
import com.tcc.orderprocessor.domain.ProcessingItem;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.exception.InvalidProcessingRequestException;

class ProcessingRequestValidatorTest {

	private final ProcessingRequestValidator validator = new ProcessingRequestValidator();

	@Test
	void acceptsValidRequest() {
		assertThatCode(() -> validator.validate(ProcessingFixtures.validRequest())).doesNotThrowAnyException();
	}

	@Test
	void rejectsMissingOrderId() {
		ProcessingRequest request = new ProcessingRequest(
				null,
				ProcessingFixtures.CUSTOMER_ID,
				List.of(ProcessingFixtures.keyboard()),
				new Address("37200-000", "MG", "Lavras"),
				new BigDecimal("399.80")
		);

		assertThatThrownBy(() -> validator.validate(request))
				.isInstanceOf(InvalidProcessingRequestException.class)
				.hasMessage("orderId is required");
	}

	@Test
	void rejectsInvalidItem() {
		ProcessingItem invalidItem = new ProcessingItem(ProcessingFixtures.KEYBOARD_ID, " ", 0, BigDecimal.ZERO);
		ProcessingRequest request = new ProcessingRequest(
				ProcessingFixtures.ORDER_ID,
				ProcessingFixtures.CUSTOMER_ID,
				List.of(invalidItem),
				new Address("37200-000", "MG", "Lavras"),
				new BigDecimal("399.80")
		);

		assertThatThrownBy(() -> validator.validate(request))
				.isInstanceOf(InvalidProcessingRequestException.class)
				.hasMessage("items[0].productName is required");
	}

	@Test
	void rejectsInvalidAddressState() {
		ProcessingRequest request = new ProcessingRequest(
				ProcessingFixtures.ORDER_ID,
				ProcessingFixtures.CUSTOMER_ID,
				List.of(ProcessingFixtures.keyboard()),
				new Address("37200-000", "MINAS", "Lavras"),
				new BigDecimal("399.80")
		);

		assertThatThrownBy(() -> validator.validate(request))
				.isInstanceOf(InvalidProcessingRequestException.class)
				.hasMessage("shippingAddress.state must contain exactly 2 characters");
	}

	@Test
	void rejectsNonPositiveTotalAmount() {
		ProcessingRequest request = new ProcessingRequest(
				ProcessingFixtures.ORDER_ID,
				ProcessingFixtures.CUSTOMER_ID,
				List.of(ProcessingFixtures.keyboard()),
				new Address("37200-000", "MG", "Lavras"),
				BigDecimal.ZERO
		);

		assertThatThrownBy(() -> validator.validate(request))
				.isInstanceOf(InvalidProcessingRequestException.class)
				.hasMessage("totalAmount must be greater than zero");
	}

}