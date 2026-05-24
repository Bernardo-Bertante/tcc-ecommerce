package com.tcc.orderprocessor.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.UUID;

import jakarta.enterprise.context.ApplicationScoped;

import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;

@ApplicationScoped
public class ProcessingCalculator {

	private static final int MONEY_SCALE = 2;
	private static final BigDecimal TAX_RATE = new BigDecimal("0.08");

	public ProcessingResult calculate(ProcessingRequest request, LocalDateTime processedAt) {
		BigDecimal totalAmount = money(request.totalAmount());
		BigDecimal shippingCost = shippingCost(request.shippingAddress().state());
		BigDecimal taxAmount = taxAmount(totalAmount);
		BigDecimal finalAmount = money(totalAmount.add(shippingCost).add(taxAmount));

		return new ProcessingResult(
				request.orderId(),
				fiscalNumber(request.orderId()),
				shippingCost,
				taxAmount,
				finalAmount,
				estimatedDeliveryDays(request.shippingAddress().state()),
				processedAt
		);
	}

	public String fiscalNumber(UUID orderId) {
		String hex = orderId.toString().replace("-", "").toUpperCase(Locale.ROOT);
		return "NF-" + hex.substring(0, 12);
	}

	public BigDecimal shippingCost(String state) {
		return switch (normalizeState(state)) {
			case "MG", "SP", "RJ", "ES" -> money("19.90");
			case "PR", "SC", "RS" -> money("24.90");
			case "GO", "DF", "MT", "MS" -> money("29.90");
			case "BA", "SE", "AL", "PE", "PB", "RN", "CE", "PI", "MA" -> money("34.90");
			case "AM", "PA", "AC", "RO", "RR", "AP", "TO" -> money("39.90");
			default -> money("29.90");
		};
	}

	public BigDecimal taxAmount(BigDecimal totalAmount) {
		return money(totalAmount.multiply(TAX_RATE));
	}

	public int estimatedDeliveryDays(String state) {
		return switch (normalizeState(state)) {
			case "MG" -> 2;
			case "SP", "RJ", "ES" -> 3;
			case "PR", "SC", "RS", "GO", "DF" -> 5;
			case "BA", "SE", "AL", "PE", "PB", "RN", "CE", "PI", "MA" -> 7;
			case "AM", "PA", "AC", "RO", "RR", "AP", "TO" -> 10;
			default -> 6;
		};
	}

	public BigDecimal money(BigDecimal value) {
		return value.setScale(MONEY_SCALE, RoundingMode.HALF_UP);
	}

	private BigDecimal money(String value) {
		return money(new BigDecimal(value));
	}

	private String normalizeState(String state) {
		return state == null ? "" : state.trim().toUpperCase(Locale.ROOT);
	}

}