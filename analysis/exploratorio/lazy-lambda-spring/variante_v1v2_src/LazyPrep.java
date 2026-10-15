package com.tcc.orderprocessor.exp;

import java.util.Map;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationContext;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.tcc.orderprocessor.config.DynamoDbProperties;
import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;
import com.tcc.orderprocessor.function.LambdaRequestMapper;
import com.tcc.orderprocessor.repository.ProcessedOrderRepository;
import com.tcc.orderprocessor.repository.StockReservationRepository;
import com.tcc.orderprocessor.service.OrderProcessingService;
import com.tcc.orderprocessor.service.ProcessingCalculator;
import com.tcc.orderprocessor.service.ProcessingRequestValidator;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;

/**
 * exp-lazy-sb V2: with EXP_LAZY_PREP=1, runs during init (ApplicationReadyEvent fires inside SpringApplication.run,
 * called by the FunctionInvoker constructor) the same steps as the Quarkus V2 preparation. Every application bean is
 * already an eager singleton at this point, so step 1 only fetches them (nothing is created twice). The only writes
 * are marker items with the fixed key 00000000-0000-0000-0000-000000000000, excluded from the analysis.
 * Without the variable (V1) it only records the ApplicationReadyEvent point.
 */
@Component
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

	private final ApplicationContext context;

	public LazyPrep(ApplicationContext context) {
		this.context = context;
	}

	@EventListener(ApplicationReadyEvent.class)
	public void onReady() {
		LazyProbe.mark("init_ready_event");
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

	private void prepare() throws Exception {
		LazyProbe.mark("prep_in");
		context.getBean("processOrder");
		LambdaRequestMapper mapper = context.getBean(LambdaRequestMapper.class);
		OrderProcessingService service = context.getBean(OrderProcessingService.class);
		context.getBean(ProcessingRequestValidator.class);
		context.getBean(ProcessingCalculator.class);
		context.getBean(ProcessedOrderRepository.class);
		context.getBean(StockReservationRepository.class);
		LazyProbe.mark("prep_beans_done");

		ObjectMapper objectMapper = context.getBean(ObjectMapper.class);
		JsonNode markerEvent = objectMapper.readTree(MARKER_EVENT);
		ProcessingRequest markerRequest = mapper.toProcessingRequest(markerEvent);
		LazyProbe.mark("prep_json_in_done");

		DynamoDbClient client = context.getBean(DynamoDbClient.class);
		DynamoDbProperties properties = context.getBean(DynamoDbProperties.class);
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

}
