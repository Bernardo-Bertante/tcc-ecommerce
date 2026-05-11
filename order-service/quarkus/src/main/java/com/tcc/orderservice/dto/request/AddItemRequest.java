package com.tcc.orderservice.dto.request;

import java.math.BigDecimal;
import java.util.UUID;

public class AddItemRequest {

	private UUID productId;
	private String productName;
	private Integer quantity;
	private BigDecimal unitPrice;

	public AddItemRequest() {
	}

	public AddItemRequest(UUID productId, String productName, Integer quantity, BigDecimal unitPrice) {
		this.productId = productId;
		this.productName = productName;
		this.quantity = quantity;
		this.unitPrice = unitPrice;
	}

	public UUID getProductId() {
		return productId;
	}

	public void setProductId(UUID productId) {
		this.productId = productId;
	}

	public String getProductName() {
		return productName;
	}

	public void setProductName(String productName) {
		this.productName = productName;
	}

	public Integer getQuantity() {
		return quantity;
	}

	public void setQuantity(Integer quantity) {
		this.quantity = quantity;
	}

	public BigDecimal getUnitPrice() {
		return unitPrice;
	}

	public void setUnitPrice(BigDecimal unitPrice) {
		this.unitPrice = unitPrice;
	}
}
