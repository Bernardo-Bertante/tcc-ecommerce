package com.tcc.orderservice.dto.request;

import com.tcc.orderservice.domain.OrderStatus;

public class UpdateStatusRequest {

	private OrderStatus status;

	public UpdateStatusRequest() {
	}

	public UpdateStatusRequest(OrderStatus status) {
		this.status = status;
	}

	public OrderStatus getStatus() {
		return status;
	}

	public void setStatus(OrderStatus status) {
		this.status = status;
	}
}
