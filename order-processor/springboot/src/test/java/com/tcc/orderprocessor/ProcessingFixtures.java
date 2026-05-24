package com.tcc.orderprocessor;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import com.tcc.orderprocessor.domain.Address;
import com.tcc.orderprocessor.domain.ProcessingItem;
import com.tcc.orderprocessor.domain.ProcessingRequest;

public final class ProcessingFixtures {

	public static final UUID ORDER_ID = UUID.fromString("3f2504e0-4f89-11d3-9a0c-0305e82c3301");
	public static final UUID CUSTOMER_ID = UUID.fromString("8b9d7b5e-9d2a-4b4f-8c5a-8b3d6f5d1a11");
	public static final UUID KEYBOARD_ID = UUID.fromString("93b6c5c8-0f9a-4c2a-8c4c-6f0f3d6a9c2b");
	public static final UUID MOUSE_ID = UUID.fromString("7b5c3d6a-07be-4d47-8a3f-60c0c10b6510");
	public static final LocalDateTime PROCESSED_AT = LocalDateTime.of(2026, 5, 20, 10, 0);

	private ProcessingFixtures() {
	}

	public static ProcessingRequest validRequest() {
		return new ProcessingRequest(
				ORDER_ID,
				CUSTOMER_ID,
				List.of(keyboard()),
				new Address("37200-000", "MG", "Lavras"),
				new BigDecimal("399.80")
		);
	}

	public static ProcessingRequest validRequestWithTwoItems() {
		return new ProcessingRequest(
				ORDER_ID,
				CUSTOMER_ID,
				List.of(keyboard(), mouse()),
				new Address("37200-000", "MG", "Lavras"),
				new BigDecimal("449.70")
		);
	}

	public static ProcessingItem keyboard() {
		return new ProcessingItem(KEYBOARD_ID, "Mechanical Keyboard", 2, new BigDecimal("199.90"));
	}

	public static ProcessingItem mouse() {
		return new ProcessingItem(MOUSE_ID, "Wireless Mouse", 1, new BigDecimal("49.90"));
	}

}