package com.tcc.orderprocessor.service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.stereotype.Service;

import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.domain.StockReservation;
import com.tcc.orderprocessor.exception.ProcessingException;
import com.tcc.orderprocessor.repository.ProcessedOrderRepository;
import com.tcc.orderprocessor.repository.StockReservationRepository;

import software.amazon.awssdk.core.exception.SdkException;

@Service
public class OrderProcessingService {

	private final ProcessingRequestValidator validator;
	private final ProcessingCalculator calculator;
	private final ProcessedOrderRepository processedOrderRepository;
	private final StockReservationRepository stockReservationRepository;
	private final Clock clock;

	public OrderProcessingService(
			ProcessingRequestValidator validator,
			ProcessingCalculator calculator,
			ProcessedOrderRepository processedOrderRepository,
			StockReservationRepository stockReservationRepository,
			Clock clock
	) {
		this.validator = validator;
		this.calculator = calculator;
		this.processedOrderRepository = processedOrderRepository;
		this.stockReservationRepository = stockReservationRepository;
		this.clock = clock;
	}

	public ProcessingResult process(ProcessingRequest request) {
		validator.validate(request);

		LocalDateTime processedAt = LocalDateTime.now(clock);
		ProcessingResult result = calculator.calculate(request, processedAt);
		List<StockReservation> reservations = request.items().stream()
				.map(item -> new StockReservation(request.orderId(), item.productId(), item.quantity(), processedAt))
				.toList();

		try {
			processedOrderRepository.save(request, result);
			stockReservationRepository.saveAll(reservations);
			return result;
		} catch (SdkException exception) {
			throw new ProcessingException("Failed to persist processing result", exception);
		}
	}

}