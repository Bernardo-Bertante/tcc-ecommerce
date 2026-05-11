package com.tcc.orderservice.dto.request;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class CreateOrderRequest {

	private UUID customerId;
	private BigDecimal discountAmount;
	private List<AddItemRequest> items;
	private ShippingAddressRequest shippingAddress;

	public CreateOrderRequest() {
		this.items = new ArrayList<>();
	}

	public CreateOrderRequest(UUID customerId,
			BigDecimal discountAmount,
			List<AddItemRequest> items,
			ShippingAddressRequest shippingAddress) {
		this.customerId = customerId;
		this.discountAmount = discountAmount;
		this.items = items == null ? new ArrayList<>() : new ArrayList<>(items);
		this.shippingAddress = shippingAddress;
	}

	public UUID getCustomerId() {
		return customerId;
	}

	public void setCustomerId(UUID customerId) {
		this.customerId = customerId;
	}

	public BigDecimal getDiscountAmount() {
		return discountAmount;
	}

	public void setDiscountAmount(BigDecimal discountAmount) {
		this.discountAmount = discountAmount;
	}

	public List<AddItemRequest> getItems() {
		if (items == null) {
			items = new ArrayList<>();
		}

		return items;
	}

	public void setItems(List<AddItemRequest> items) {
		this.items = items == null ? new ArrayList<>() : new ArrayList<>(items);
	}

	public ShippingAddressRequest getShippingAddress() {
		return shippingAddress;
	}

	public void setShippingAddress(ShippingAddressRequest shippingAddress) {
		this.shippingAddress = shippingAddress;
	}
}
