package com.tcc.orderprocessor.function;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.domain.StockReservation;
import com.tcc.orderprocessor.repository.ProcessedOrderRepository;
import com.tcc.orderprocessor.repository.StockReservationRepository;
import com.tcc.orderprocessor.service.OrderProcessingService;
import com.tcc.orderprocessor.service.ProcessingCalculator;
import com.tcc.orderprocessor.service.ProcessingRequestValidator;

class QuarkusOrderProcessorFunctionTest {

	@Test
	void processOrderDelegatesToSharedServiceLogic() {
		RecordingProcessedOrderRepository processedOrderRepository = new RecordingProcessedOrderRepository();
		RecordingStockReservationRepository stockReservationRepository = new RecordingStockReservationRepository();
		OrderProcessingService service = new OrderProcessingService(
				new ProcessingRequestValidator(),
				new ProcessingCalculator(),
				processedOrderRepository,
				stockReservationRepository,
				Clock.fixed(Instant.parse("2026-05-20T10:00:00Z"), ZoneOffset.UTC)
		);
		ObjectMapper objectMapper = new ObjectMapper();
		QuarkusOrderProcessorFunction function = new QuarkusOrderProcessorFunction(service, new LambdaRequestMapper(objectMapper));

		ProcessingResult result = function.processOrder(objectMapper.valueToTree(ProcessingFixtures.validRequest()));

		assertThat(result.fiscalNumber()).isEqualTo("NF-3F2504E04F89");
		assertThat(result.finalAmount()).isEqualByComparingTo("451.68");
		assertThat(processedOrderRepository.result).isEqualTo(result);
		assertThat(stockReservationRepository.reservations).hasSize(1);
	}

	private static final class RecordingProcessedOrderRepository implements ProcessedOrderRepository {

		private ProcessingResult result;

		@Override
		public void save(ProcessingRequest request, ProcessingResult result) {
			this.result = result;
		}

	}

	private static final class RecordingStockReservationRepository implements StockReservationRepository {

		private List<StockReservation> reservations = List.of();

		@Override
		public void saveAll(List<StockReservation> reservations) {
			this.reservations = reservations;
		}

	}

}