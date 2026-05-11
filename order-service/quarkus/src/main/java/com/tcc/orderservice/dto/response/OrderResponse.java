package com.tcc.orderservice.dto.response;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import com.tcc.orderservice.domain.OrderStatus;

public class OrderResponse {

	private UUID id;
	private UUID customerId;
	private OrderStatus status;
	private BigDecimal totalAmount;
	private BigDecimal discountAmount;
	private BigDecimal finalAmount;
	private ShippingAddressResponse shippingAddress;
	private List<OrderItemResponse> items;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public OrderResponse() {
		this.items = new ArrayList<>();
	}

	public OrderResponse(UUID id,
			UUID customerId,
			OrderStatus status,
			BigDecimal totalAmount,
			BigDecimal discountAmount,
			BigDecimal finalAmount,
			ShippingAddressResponse shippingAddress,
			List<OrderItemResponse> items,
			LocalDateTime createdAt,
			LocalDateTime updatedAt) {
		this.id = id;
		this.customerId = customerId;
		this.status = status;
		this.totalAmount = totalAmount;
		this.discountAmount = discountAmount;
		this.finalAmount = finalAmount;
		this.shippingAddress = shippingAddress;
		this.items = items == null ? new ArrayList<>() : new ArrayList<>(items);
		this.createdAt = createdAt;
		this.updatedAt = updatedAt;
	}

	public UUID getId() {
		return id;
	}

	public void setId(UUID id) {
		this.id = id;
	}

	public UUID getCustomerId() {
		return customerId;
	}

	public void setCustomerId(UUID customerId) {
		this.customerId = customerId;
	}

	public OrderStatus getStatus() {
		return status;
	}

	public void setStatus(OrderStatus status) {
		this.status = status;
	}

	public BigDecimal getTotalAmount() {
		return totalAmount;
	}

	public void setTotalAmount(BigDecimal totalAmount) {
		this.totalAmount = totalAmount;
	}

	public BigDecimal getDiscountAmount() {
		return discountAmount;
	}

	public void setDiscountAmount(BigDecimal discountAmount) {
		this.discountAmount = discountAmount;
	}

	public BigDecimal getFinalAmount() {
		return finalAmount;
	}

	public void setFinalAmount(BigDecimal finalAmount) {
		this.finalAmount = finalAmount;
	}

	public ShippingAddressResponse getShippingAddress() {
		return shippingAddress;
	}

	public void setShippingAddress(ShippingAddressResponse shippingAddress) {
		this.shippingAddress = shippingAddress;
	}

	public List<OrderItemResponse> getItems() {
		if (items == null) {
			items = new ArrayList<>();
		}

		return items;
	}

	public void setItems(List<OrderItemResponse> items) {
		this.items = items == null ? new ArrayList<>() : new ArrayList<>(items);
	}

	public LocalDateTime getCreatedAt() {
		return createdAt;
	}

	public void setCreatedAt(LocalDateTime createdAt) {
		this.createdAt = createdAt;
	}

	public LocalDateTime getUpdatedAt() {
		return updatedAt;
	}

	public void setUpdatedAt(LocalDateTime updatedAt) {
		this.updatedAt = updatedAt;
	}

	public static class ShippingAddressResponse {

		private String zipCode;
		private String street;
		private String number;
		private String complement;
		private String city;
		private String state;

		public ShippingAddressResponse() {
		}

		public ShippingAddressResponse(String zipCode,
				String street,
				String number,
				String complement,
				String city,
				String state) {
			this.zipCode = zipCode;
			this.street = street;
			this.number = number;
			this.complement = complement;
			this.city = city;
			this.state = state;
		}

		public String getZipCode() {
			return zipCode;
		}

		public void setZipCode(String zipCode) {
			this.zipCode = zipCode;
		}

		public String getStreet() {
			return street;
		}

		public void setStreet(String street) {
			this.street = street;
		}

		public String getNumber() {
			return number;
		}

		public void setNumber(String number) {
			this.number = number;
		}

		public String getComplement() {
			return complement;
		}

		public void setComplement(String complement) {
			this.complement = complement;
		}

		public String getCity() {
			return city;
		}

		public void setCity(String city) {
			this.city = city;
		}

		public String getState() {
			return state;
		}

		public void setState(String state) {
			this.state = state;
		}
	}
}
