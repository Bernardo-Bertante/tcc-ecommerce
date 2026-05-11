package com.tcc.orderservice.dto.response;

import java.math.BigDecimal;
import java.util.UUID;

public class OrderItemResponse {

	private UUID id;
	private UUID productId;
	private String productName;
	private Integer quantity;
	private BigDecimal unitPrice;
	private BigDecimal subtotal;

	public OrderItemResponse() {
	}

	public OrderItemResponse(UUID id,
			UUID productId,
			String productName,
			Integer quantity,
			BigDecimal unitPrice,
			BigDecimal subtotal) {
		this.id = id;
		this.productId = productId;
		this.productName = productName;
		this.quantity = quantity;
		this.unitPrice = unitPrice;
		this.subtotal = subtotal;
	}

	public UUID getId() {
		return id;
	}

	public void setId(UUID id) {
		this.id = id;
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

	public BigDecimal getSubtotal() {
		return subtotal;
	}

	public void setSubtotal(BigDecimal subtotal) {
		this.subtotal = subtotal;
	}
}
