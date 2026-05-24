package com.tcc.orderprocessor.function;

import java.util.function.Function;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.fasterxml.jackson.databind.JsonNode;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.service.OrderProcessingService;

@Configuration(proxyBeanMethods = false)
public class SpringOrderProcessorFunction {

	@Bean
	Function<JsonNode, ProcessingResult> processOrder(OrderProcessingService service, LambdaRequestMapper requestMapper) {
		return event -> service.process(requestMapper.toProcessingRequest(event));
	}

}