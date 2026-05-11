package com.tcc.orderservice.dto.response;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import com.tcc.orderservice.domain.OrderStatus;

public class OrderSummaryResponse {

	private Long totalOrders;
	private BigDecimal totalRevenue;
	private BigDecimal averageOrderValue;
	private Map<OrderStatus, Long> ordersByStatus;
	private List<TopCustomerSummary> topCustomers;
	private List<RevenueByDaySummary> revenueByDay;

	public OrderSummaryResponse() {
		this.ordersByStatus = new EnumMap<>(OrderStatus.class);
		this.topCustomers = new ArrayList<>();
		this.revenueByDay = new ArrayList<>();
	}

	public OrderSummaryResponse(Long totalOrders,
			BigDecimal totalRevenue,
			BigDecimal averageOrderValue,
			Map<OrderStatus, Long> ordersByStatus,
			List<TopCustomerSummary> topCustomers,
			List<RevenueByDaySummary> revenueByDay) {
		this.totalOrders = totalOrders;
		this.totalRevenue = totalRevenue;
		this.averageOrderValue = averageOrderValue;
		this.ordersByStatus = ordersByStatus == null
				? new EnumMap<>(OrderStatus.class)
				: new EnumMap<>(ordersByStatus);
		this.topCustomers = topCustomers == null ? new ArrayList<>() : new ArrayList<>(topCustomers);
		this.revenueByDay = revenueByDay == null ? new ArrayList<>() : new ArrayList<>(revenueByDay);
	}

	public Long getTotalOrders() {
		return totalOrders;
	}

	public void setTotalOrders(Long totalOrders) {
		this.totalOrders = totalOrders;
	}

	public BigDecimal getTotalRevenue() {
		return totalRevenue;
	}

	public void setTotalRevenue(BigDecimal totalRevenue) {
		this.totalRevenue = totalRevenue;
	}

	public BigDecimal getAverageOrderValue() {
		return averageOrderValue;
	}

	public void setAverageOrderValue(BigDecimal averageOrderValue) {
		this.averageOrderValue = averageOrderValue;
	}

	public Map<OrderStatus, Long> getOrdersByStatus() {
		if (ordersByStatus == null) {
			ordersByStatus = new EnumMap<>(OrderStatus.class);
		}

		return ordersByStatus;
	}

	public void setOrdersByStatus(Map<OrderStatus, Long> ordersByStatus) {
		this.ordersByStatus = ordersByStatus == null
				? new EnumMap<>(OrderStatus.class)
				: new EnumMap<>(ordersByStatus);
	}

	public List<TopCustomerSummary> getTopCustomers() {
		if (topCustomers == null) {
			topCustomers = new ArrayList<>();
		}

		return topCustomers;
	}

	public void setTopCustomers(List<TopCustomerSummary> topCustomers) {
		this.topCustomers = topCustomers == null ? new ArrayList<>() : new ArrayList<>(topCustomers);
	}

	public List<RevenueByDaySummary> getRevenueByDay() {
		if (revenueByDay == null) {
			revenueByDay = new ArrayList<>();
		}

		return revenueByDay;
	}

	public void setRevenueByDay(List<RevenueByDaySummary> revenueByDay) {
		this.revenueByDay = revenueByDay == null ? new ArrayList<>() : new ArrayList<>(revenueByDay);
	}

	public static class TopCustomerSummary {

		private UUID customerId;
		private BigDecimal totalSpent;
		private Long orderCount;

		public TopCustomerSummary() {
		}

		public TopCustomerSummary(UUID customerId, BigDecimal totalSpent, Long orderCount) {
			this.customerId = customerId;
			this.totalSpent = totalSpent;
			this.orderCount = orderCount;
		}

		public UUID getCustomerId() {
			return customerId;
		}

		public void setCustomerId(UUID customerId) {
			this.customerId = customerId;
		}

		public BigDecimal getTotalSpent() {
			return totalSpent;
		}

		public void setTotalSpent(BigDecimal totalSpent) {
			this.totalSpent = totalSpent;
		}

		public Long getOrderCount() {
			return orderCount;
		}

		public void setOrderCount(Long orderCount) {
			this.orderCount = orderCount;
		}
	}

	public static class RevenueByDaySummary {

		private LocalDate date;
		private BigDecimal revenue;
		private Long orderCount;

		public RevenueByDaySummary() {
		}

		public RevenueByDaySummary(LocalDate date, BigDecimal revenue, Long orderCount) {
			this.date = date;
			this.revenue = revenue;
			this.orderCount = orderCount;
		}

		public LocalDate getDate() {
			return date;
		}

		public void setDate(LocalDate date) {
			this.date = date;
		}

		public BigDecimal getRevenue() {
			return revenue;
		}

		public void setRevenue(BigDecimal revenue) {
			this.revenue = revenue;
		}

		public Long getOrderCount() {
			return orderCount;
		}

		public void setOrderCount(Long orderCount) {
			this.orderCount = orderCount;
		}
	}
}
