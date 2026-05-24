package com.tcc.orderprocessor.function;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.service.ProcessingCalculator;

import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;

@QuarkusTest
class ProcessingJsonSerializationTest {

	@Inject
	ObjectMapper objectMapper;

	@Test
	void serializesProcessedAtAsIsoString() throws Exception {
		ProcessingResult result = new ProcessingCalculator()
				.calculate(ProcessingFixtures.validRequest(), ProcessingFixtures.PROCESSED_AT);

		String json = objectMapper.writeValueAsString(result);

		assertThat(json).contains("\"processedAt\":\"2026-05-20T10:00:00\"");
	}

}