package com.tcc.orderservice.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Transient;
import org.springframework.data.domain.Persistable;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("orders")
public class Order implements Persistable<UUID> {

	private static final int MONEY_SCALE = 2;
	private static final RoundingMode MONEY_ROUNDING = RoundingMode.HALF_UP;

	@Id
	private UUID id;

	@Column("customer_id")
	private UUID customerId;

	@Column("status")
	private OrderStatus status;

	@Column("total_amount")
	private BigDecimal totalAmount;

	@Column("discount_amount")
	private BigDecimal discountAmount;

	@Column("final_amount")
	private BigDecimal finalAmount;

	@Column("shipping_zip_code")
	private String shippingZipCode;

	@Column("shipping_street")
	private String shippingStreet;

	@Column("shipping_number")
	private String shippingNumber;

	@Column("shipping_complement")
	private String shippingComplement;

	@Column("shipping_city")
	private String shippingCity;

	@Column("shipping_state")
	private String shippingState;

	@Column("created_at")
	private LocalDateTime createdAt;

	@Column("updated_at")
	private LocalDateTime updatedAt;

	@Transient
	private List<OrderItem> items;

	@Transient
	private boolean newEntity;

	public Order() {
		this.status = OrderStatus.PENDING;
		this.totalAmount = zeroMoney();
		this.discountAmount = zeroMoney();
		this.finalAmount = zeroMoney();
		this.items = new ArrayList<>();
		this.newEntity = false;
	}

	public Order(UUID id,
			UUID customerId,
			OrderStatus status,
			BigDecimal totalAmount,
			BigDecimal discountAmount,
			BigDecimal finalAmount,
			String shippingZipCode,
			String shippingStreet,
			String shippingNumber,
			String shippingComplement,
			String shippingCity,
			String shippingState,
			LocalDateTime createdAt,
			LocalDateTime updatedAt,
			List<OrderItem> items) {
		this.id = id;
		this.customerId = customerId;
		this.status = status;
		this.totalAmount = normalizeMoney(totalAmount);
		this.discountAmount = normalizeMoney(discountAmount);
		this.finalAmount = normalizeMoney(finalAmount);
		this.shippingZipCode = shippingZipCode;
		this.shippingStreet = shippingStreet;
		this.shippingNumber = shippingNumber;
		this.shippingComplement = shippingComplement;
		this.shippingCity = shippingCity;
		this.shippingState = shippingState;
		this.createdAt = createdAt;
		this.updatedAt = updatedAt;
		this.items = items == null ? new ArrayList<>() : new ArrayList<>(items);
		this.newEntity = false;
	}

	public void markNew() {
		this.newEntity = true;
	}

	public void markPersisted() {
		this.newEntity = false;
	}

	public void recalculateFinalAmount() {
		this.totalAmount = normalizeMoney(this.totalAmount);
		this.discountAmount = normalizeMoney(this.discountAmount);

		if (this.discountAmount.compareTo(this.totalAmount) > 0) {
			throw new IllegalArgumentException("discountAmount cannot be greater than totalAmount");
		}

		this.finalAmount = normalizeMoney(this.totalAmount.subtract(this.discountAmount));
	}

	public void recalculateAmountsFromItems() {
		BigDecimal newTotalAmount = getItems().stream()
				.peek(OrderItem::recalculateSubtotal)
				.map(OrderItem::getSubtotal)
				.map(Order::normalizeMoney)
				.reduce(zeroMoney(), BigDecimal::add);

		this.totalAmount = normalizeMoney(newTotalAmount);
		recalculateFinalAmount();
	}

	public boolean hasConsistentAmounts() {
		BigDecimal normalizedTotal = normalizeMoney(this.totalAmount);
		BigDecimal normalizedDiscount = normalizeMoney(this.discountAmount);
		BigDecimal normalizedFinal = normalizeMoney(this.finalAmount);

		if (normalizedDiscount.compareTo(normalizedTotal) > 0) {
			return false;
		}

		BigDecimal expectedFinal = normalizeMoney(normalizedTotal.subtract(normalizedDiscount));
		return expectedFinal.compareTo(normalizedFinal) == 0;
	}

	private static BigDecimal zeroMoney() {
		return BigDecimal.ZERO.setScale(MONEY_SCALE, MONEY_ROUNDING);
	}

	private static BigDecimal normalizeMoney(BigDecimal amount) {
		if (amount == null) {
			return zeroMoney();
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
		this.totalAmount = normalizeMoney(totalAmount);
	}

	public BigDecimal getDiscountAmount() {
		return discountAmount;
	}

	public void setDiscountAmount(BigDecimal discountAmount) {
		this.discountAmount = normalizeMoney(discountAmount);
	}

	public BigDecimal getFinalAmount() {
		return finalAmount;
	}

	public void setFinalAmount(BigDecimal finalAmount) {
		this.finalAmount = normalizeMoney(finalAmount);
	}

	public String getShippingZipCode() {
		return shippingZipCode;
	}

	public void setShippingZipCode(String shippingZipCode) {
		this.shippingZipCode = shippingZipCode;
	}

	public String getShippingStreet() {
		return shippingStreet;
	}

	public void setShippingStreet(String shippingStreet) {
		this.shippingStreet = shippingStreet;
	}

	public String getShippingNumber() {
		return shippingNumber;
	}

	public void setShippingNumber(String shippingNumber) {
		this.shippingNumber = shippingNumber;
	}

	public String getShippingComplement() {
		return shippingComplement;
	}

	public void setShippingComplement(String shippingComplement) {
		this.shippingComplement = shippingComplement;
	}

	public String getShippingCity() {
		return shippingCity;
	}

	public void setShippingCity(String shippingCity) {
		this.shippingCity = shippingCity;
	}

	public String getShippingState() {
		return shippingState;
	}

	public void setShippingState(String shippingState) {
		this.shippingState = shippingState;
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

	public List<OrderItem> getItems() {
		if (this.items == null) {
			this.items = new ArrayList<>();
		}

		return items;
	}

	public void setItems(List<OrderItem> items) {
		this.items = items == null ? new ArrayList<>() : new ArrayList<>(items);
	}
}
