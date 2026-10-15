package com.tcc.orderprocessor.exp;

import java.util.Map;

import jakarta.enterprise.event.Observes;
import jakarta.inject.Singleton;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.tcc.orderprocessor.config.DynamoDbProperties;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.function.LambdaRequestMapper;
import com.tcc.orderprocessor.function.QuarkusOrderProcessorFunction;
import com.tcc.orderprocessor.repository.ProcessedOrderRepository;
import com.tcc.orderprocessor.repository.StockReservationRepository;
import com.tcc.orderprocessor.service.OrderProcessingService;
import com.tcc.orderprocessor.service.ProcessingCalculator;
import com.tcc.orderprocessor.service.ProcessingRequestValidator;

import io.quarkus.arc.Arc;
import io.quarkus.arc.ArcContainer;
import io.quarkus.arc.ClientProxy;
import io.quarkus.runtime.StartupEvent;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;

/**
 * exp-lazy V2: with EXP_LAZY_PREP=1, runs during init (StartupEvent fires inside Quarkus.manualStart, which the
 * Quarkus SnapStart full warm-up calls from the handler constructor) the same work the first call does. The only
 * writes are marker items with the fixed key 00000000-0000-0000-0000-000000000000, excluded from the analysis.
 * Without the variable (V1) it only records the StartupEvent point and touches no application bean.
 */
@Singleton
public class LazyPrep {

	static final String MARKER_EVENT = "{\"version\":\"2.0\",\"routeKey\":\"$default\",\"rawPath\":\"/\","
			+ "\"rawQueryString\":\"\",\"headers\":{\"content-type\":\"application/json\"},"
			+ "\"requestContext\":{\"accountId\":\"anonymous\",\"http\":{\"method\":\"POST\",\"path\":\"/\","
			+ "\"protocol\":\"HTTP/1.1\",\"sourceIp\":\"127.0.0.1\",\"userAgent\":\"exp-lazy-prep\"},"
			+ "\"requestId\":\"exp-lazy-prep\",\"routeKey\":\"$default\",\"stage\":\"$default\"},"
			+ "\"body\":\"{\\\"orderId\\\":\\\"00000000-0000-0000-0000-000000000000\\\","
			+ "\\\"customerId\\\":\\\"65d5c63f-1e92-4cc9-8f94-29b875e361e6\\\",\\\"items\\\":["
			+ "{\\\"productId\\\":\\\"a7c8446f-a702-4a79-a184-a89f3f13b956\\\",\\\"productName\\\":\\\"Mechanical Keyboard\\\",\\\"quantity\\\":1,\\\"unitPrice\\\":9.99},"
			+ "{\\\"productId\\\":\\\"5443a0bd-6af8-41f7-a6ea-09a6e941b1ac\\\",\\\"productName\\\":\\\"Wireless Mouse\\\",\\\"quantity\\\":2,\\\"unitPrice\\\":11.36},"
			+ "{\\\"productId\\\":\\\"7f8b811b-43be-4805-a9a0-c33fd07f23d2\\\",\\\"productName\\\":\\\"USB-C Hub\\\",\\\"quantity\\\":3,\\\"unitPrice\\\":12.73}],"
			+ "\\\"shippingAddress\\\":{\\\"zipCode\\\":\\\"37200-000\\\",\\\"state\\\":\\\"MG\\\",\\\"city\\\":\\\"Lavras\\\"},"
			+ "\\\"totalAmount\\\":70.9}\",\"isBase64Encoded\":false}";

	void onStart(@Observes StartupEvent event) {
		LazyProbe.mark("init_startup_event");
		if (!"1".equals(System.getenv("EXP_LAZY_PREP"))) {
			return;
		}
		try {
			prepare();
		}
		catch (Throwable t) {
			LazyProbe.mark("prep_fail", t.getClass().getName() + ": " + t.getMessage());
		}
	}

	private static void prepare() throws Exception {
		LazyProbe.mark("prep_in");
		ArcContainer arc = Arc.container();
		force(arc.instance(QuarkusOrderProcessorFunction.class).get());
		LambdaRequestMapper mapper = force(arc.instance(LambdaRequestMapper.class).get());
		OrderProcessingService service = force(arc.instance(OrderProcessingService.class).get());
		force(arc.instance(ProcessingRequestValidator.class).get());
		force(arc.instance(ProcessingCalculator.class).get());
		force(arc.instance(ProcessedOrderRepository.class).get());
		force(arc.instance(StockReservationRepository.class).get());
		LazyProbe.mark("prep_beans_done");

		ObjectMapper objectMapper = arc.instance(ObjectMapper.class).get();
		JsonNode markerEvent = objectMapper.readTree(MARKER_EVENT);
		ProcessingRequest markerRequest = mapper.toProcessingRequest(markerEvent);
		LazyProbe.mark("prep_json_in_done");

		DynamoDbClient client = arc.instance(DynamoDbClient.class).get();
		DynamoDbProperties properties = arc.instance(DynamoDbProperties.class).get();
		client.getItem(GetItemRequest.builder()
				.tableName(properties.processedOrdersTable())
				.key(Map.of("orderId", AttributeValue.builder().s("exp-lazy-warmup-inexistente").build()))
				.build());
		LazyProbe.mark("prep_getitem_done");

		ProcessingResult markerResult = service.process(markerRequest);
		LazyProbe.mark("prep_marker_puts_done");

		objectMapper.writeValueAsString(markerResult);
		LazyProbe.mark("prep_out");
	}

	@SuppressWarnings("unchecked")
	private static <T> T force(T bean) {
		if (bean instanceof ClientProxy proxy) {
			proxy.arc_contextualInstance();
		}
		return bean;
	}

}
