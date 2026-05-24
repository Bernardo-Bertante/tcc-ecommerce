package com.tcc.orderprocessor.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.domain.Address;
import com.tcc.orderprocessor.domain.ProcessingItem;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.domain.StockReservation;
import com.tcc.orderprocessor.exception.InvalidProcessingRequestException;
import com.tcc.orderprocessor.repository.ProcessedOrderRepository;
import com.tcc.orderprocessor.repository.StockReservationRepository;

class OrderProcessingServiceTest {

	@Test
	void returnsCompleteProcessingResultForValidRequest() {
		RecordingProcessedOrderRepository processedOrderRepository = new RecordingProcessedOrderRepository();
		RecordingStockReservationRepository stockReservationRepository = new RecordingStockReservationRepository();
		OrderProcessingService service = newService(processedOrderRepository, stockReservationRepository);

		ProcessingResult result = service.process(ProcessingFixtures.validRequest());

		assertThat(result.orderId()).isEqualTo(ProcessingFixtures.ORDER_ID);
		assertThat(result.fiscalNumber()).isEqualTo("NF-3F2504E04F89");
		assertThat(result.shippingCost()).isEqualByComparingTo("19.90");
		assertThat(result.taxAmount()).isEqualByComparingTo("31.98");
		assertThat(result.finalAmount()).isEqualByComparingTo("451.68");
		assertThat(result.estimatedDeliveryDays()).isEqualTo(2);
		assertThat(result.processedAt()).isEqualTo(ProcessingFixtures.PROCESSED_AT);
	}

	@Test
	void validatesCalculatesPersistsAndReturnsSameResult() {
		RecordingProcessedOrderRepository processedOrderRepository = new RecordingProcessedOrderRepository();
		RecordingStockReservationRepository stockReservationRepository = new RecordingStockReservationRepository();
		OrderProcessingService service = newService(processedOrderRepository, stockReservationRepository);

		ProcessingRequest request = ProcessingFixtures.validRequestWithTwoItems();
		ProcessingResult result = service.process(request);

		assertThat(processedOrderRepository.request).isSameAs(request);
		assertThat(processedOrderRepository.result).isEqualTo(result);
		assertThat(stockReservationRepository.reservations).hasSize(2);
		assertThat(stockReservationRepository.reservations)
				.allSatisfy(reservation -> {
					assertThat(reservation.orderId()).isEqualTo(ProcessingFixtures.ORDER_ID);
					assertThat(reservation.reservedAt()).isEqualTo(ProcessingFixtures.PROCESSED_AT);
				});
		assertThat(result.finalAmount()).isEqualByComparingTo("505.58");
	}

	@Test
	void createsOneReservationPerItemWithMatchingProductIdAndQuantity() {
		RecordingProcessedOrderRepository processedOrderRepository = new RecordingProcessedOrderRepository();
		RecordingStockReservationRepository stockReservationRepository = new RecordingStockReservationRepository();
		OrderProcessingService service = newService(processedOrderRepository, stockReservationRepository);

		service.process(ProcessingFixtures.validRequestWithTwoItems());

		assertThat(stockReservationRepository.reservations)
				.containsExactly(
						new StockReservation(
								ProcessingFixtures.ORDER_ID,
								ProcessingFixtures.KEYBOARD_ID,
								2,
								ProcessingFixtures.PROCESSED_AT
						),
						new StockReservation(
								ProcessingFixtures.ORDER_ID,
								ProcessingFixtures.MOUSE_ID,
								1,
								ProcessingFixtures.PROCESSED_AT
						)
				);
	}

	@Test
	void rejectsInvalidRequestBeforePersisting() {
		RecordingProcessedOrderRepository processedOrderRepository = new RecordingProcessedOrderRepository();
		RecordingStockReservationRepository stockReservationRepository = new RecordingStockReservationRepository();
		OrderProcessingService service = newService(processedOrderRepository, stockReservationRepository);
		ProcessingRequest invalidRequest = new ProcessingRequest(
				null,
				ProcessingFixtures.CUSTOMER_ID,
				List.of(new ProcessingItem(ProcessingFixtures.KEYBOARD_ID, "Mechanical Keyboard", 2, new java.math.BigDecimal("199.90"))),
				new Address("37200-000", "MG", "Lavras"),
				new java.math.BigDecimal("399.80")
		);

		assertThatThrownBy(() -> service.process(invalidRequest))
				.isInstanceOf(InvalidProcessingRequestException.class)
				.hasMessage("orderId is required");
		assertThat(processedOrderRepository.saveCalls).isZero();
		assertThat(stockReservationRepository.saveAllCalls).isZero();
	}

	private static OrderProcessingService newService(
			ProcessedOrderRepository processedOrderRepository,
			StockReservationRepository stockReservationRepository
	) {
		return new OrderProcessingService(
				new ProcessingRequestValidator(),
				new ProcessingCalculator(),
				processedOrderRepository,
				stockReservationRepository,
				fixedClock()
		);
	}

	private static Clock fixedClock() {
		return Clock.fixed(Instant.parse("2026-05-20T10:00:00Z"), ZoneOffset.UTC);
	}

	private static final class RecordingProcessedOrderRepository implements ProcessedOrderRepository {

		private ProcessingRequest request;
		private ProcessingResult result;
		private int saveCalls;

		@Override
		public void save(ProcessingRequest request, ProcessingResult result) {
			this.saveCalls += 1;
			this.request = request;
			this.result = result;
		}

	}

	private static final class RecordingStockReservationRepository implements StockReservationRepository {

		private final List<StockReservation> reservations = new ArrayList<>();
		private int saveAllCalls;

		@Override
		public void saveAll(List<StockReservation> reservations) {
			this.saveAllCalls += 1;
			this.reservations.addAll(reservations);
		}

	}

}