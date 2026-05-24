package com.tcc.orderprocessor.function;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import com.fasterxml.jackson.databind.JsonNode;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.service.OrderProcessingService;

import io.quarkus.funqy.Funq;

@ApplicationScoped
public class QuarkusOrderProcessorFunction {

	private final OrderProcessingService service;
	private final LambdaRequestMapper requestMapper;

	@Inject
	public QuarkusOrderProcessorFunction(OrderProcessingService service, LambdaRequestMapper requestMapper) {
		this.service = service;
		this.requestMapper = requestMapper;
	}

	@Funq("processOrder")
	public ProcessingResult processOrder(JsonNode event) {
		return service.process(requestMapper.toProcessingRequest(event));
	}

}