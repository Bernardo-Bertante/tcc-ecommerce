package com.tcc.orderservice.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.UUID;

import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Transient;
import org.springframework.data.domain.Persistable;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("order_items")
public class OrderItem implements Persistable<UUID> {

	private static final int MONEY_SCALE = 2;
	private static final RoundingMode MONEY_ROUNDING = RoundingMode.HALF_UP;

	@Id
	private UUID id;

	@Column("order_id")
	private UUID orderId;

	@Column("product_id")
	private UUID productId;

	@Column("product_name")
	private String productName;

	@Column("quantity")
	private Integer quantity;

	@Column("unit_price")
	private BigDecimal unitPrice;

	@Column("subtotal")
	private BigDecimal subtotal;

	@Transient
	private boolean newEntity;

	public OrderItem() {
		this.newEntity = false;
	}

	public OrderItem(UUID id,
			UUID orderId,
			UUID productId,
			String productName,
			Integer quantity,
			BigDecimal unitPrice,
			BigDecimal subtotal) {
		this.id = id;
		this.orderId = orderId;
		this.productId = productId;
		this.productName = productName;
		this.quantity = quantity;
		this.unitPrice = unitPrice;

		validateQuantityAndPrice();
		this.subtotal = subtotal == null ? calculateSubtotal() : normalizeMoney(subtotal);
		this.newEntity = false;
	}

	public void markNew() {
		this.newEntity = true;
	}

	public void markPersisted() {
		this.newEntity = false;
	}

	public void recalculateSubtotal() {
		validateQuantityAndPrice();
		this.subtotal = calculateSubtotal();
	}

	private BigDecimal calculateSubtotal() {
		return normalizeMoney(this.unitPrice)
				.multiply(BigDecimal.valueOf(this.quantity.longValue()))
				.setScale(MONEY_SCALE, MONEY_ROUNDING);
	}

	private void validateQuantityAndPrice() {
		if (this.quantity == null || this.quantity < 1) {
			throw new IllegalArgumentException("quantity must be greater than or equal to 1");
		}

		if (this.unitPrice == null || this.unitPrice.compareTo(BigDecimal.ZERO) <= 0) {
			throw new IllegalArgumentException("unitPrice must be greater than 0");
		}
	}

	private static BigDecimal normalizeMoney(BigDecimal amount) {
		if (amount == null) {
			return BigDecimal.ZERO.setScale(MONEY_SCALE, MONEY_ROUNDING);
		}

		return amount.setScale(MONEY_SCALE, MONEY_ROUNDING);
	}

	public UUID getId() {
		return id;
	}

	@Override
	public boolean isNew() {
		return this.newEntity;
	}

	public void setId(UUID id) {
		this.id = id;
	}

	public UUID getOrderId() {
		return orderId;
	}

	public void setOrderId(UUID orderId) {
		this.orderId = orderId;
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
		if (this.quantity != null && this.unitPrice != null) {
			recalculateSubtotal();
		}
	}

	public BigDecimal getUnitPrice() {
		return unitPrice;
	}

	public void setUnitPrice(BigDecimal unitPrice) {
		this.unitPrice = unitPrice;
		if (this.quantity != null && this.unitPrice != null) {
			recalculateSubtotal();
		}
	}

	public BigDecimal getSubtotal() {
		return subtotal;
	}

	public void setSubtotal(BigDecimal subtotal) {
		this.subtotal = normalizeMoney(subtotal);
	}
}
