package com.tcc.orderprocessor.function;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.domain.ProcessingRequest;

class LambdaRequestMapperTest {

	private final ObjectMapper objectMapper = new ObjectMapper();
	private final LambdaRequestMapper mapper = new LambdaRequestMapper(objectMapper);

	@Test
	void mapsDirectLambdaPayload() {
		ProcessingRequest request = mapper.toProcessingRequest(objectMapper.valueToTree(ProcessingFixtures.validRequest()));

		assertThat(request.orderId()).isEqualTo(ProcessingFixtures.ORDER_ID);
		assertThat(request.items()).hasSize(1);
	}

	@Test
	void mapsFunctionUrlPayloadBody() throws JsonProcessingException {
		ObjectNode event = functionUrlEvent(objectMapper.writeValueAsString(ProcessingFixtures.validRequest()));

		ProcessingRequest request = mapper.toProcessingRequest(event);

		assertThat(request.orderId()).isEqualTo(ProcessingFixtures.ORDER_ID);
		assertThat(request.customerId()).isEqualTo(ProcessingFixtures.CUSTOMER_ID);
		assertThat(request.items()).hasSize(1);
	}

	private ObjectNode functionUrlEvent(String body) {
		ObjectNode event = objectMapper.createObjectNode();
		event.put("version", "2.0");
		event.put("body", body);
		event.put("isBase64Encoded", false);
		ObjectNode requestContext = event.putObject("requestContext");
		requestContext.putObject("http").put("method", "POST");
		return event;
	}

}