package com.tcc.orderprocessor.function;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.tcc.orderprocessor.domain.ProcessingRequest;

@ApplicationScoped
public class LambdaRequestMapper {

	private final ObjectMapper objectMapper;

	@Inject
	public LambdaRequestMapper(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public ProcessingRequest toProcessingRequest(JsonNode event) {
		try {
			return objectMapper.treeToValue(requestNode(event), ProcessingRequest.class);
		}
		catch (JsonProcessingException exception) {
			throw new IllegalArgumentException("Invalid processing request JSON", exception);
		}
	}

	private JsonNode requestNode(JsonNode event) throws JsonProcessingException {
		if (!isFunctionUrlEvent(event)) {
			return event;
		}

		JsonNode body = event.path("body");
		if (!body.isTextual()) {
			return body.isMissingNode() || body.isNull() ? objectMapper.createObjectNode() : body;
		}

		String bodyText = body.asText();
		if (event.path("isBase64Encoded").asBoolean(false)) {
			bodyText = new String(Base64.getDecoder().decode(bodyText), StandardCharsets.UTF_8);
		}
		if (bodyText.isBlank()) {
			return objectMapper.createObjectNode();
		}
		return objectMapper.readTree(bodyText);
	}

	private boolean isFunctionUrlEvent(JsonNode event) {
		return event != null
				&& event.has("requestContext")
				&& event.path("requestContext").has("http")
				&& event.has("body");
	}

}