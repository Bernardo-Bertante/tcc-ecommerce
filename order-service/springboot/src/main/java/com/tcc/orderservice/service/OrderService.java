package com.tcc.orderservice.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.tcc.orderservice.domain.Order;
import com.tcc.orderservice.domain.OrderItem;
import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.domain.OrderStatusHistory;
import com.tcc.orderservice.dto.request.AddItemRequest;
import com.tcc.orderservice.dto.request.CreateOrderRequest;
import com.tcc.orderservice.dto.request.ShippingAddressRequest;
import com.tcc.orderservice.dto.request.UpdateStatusRequest;
import com.tcc.orderservice.dto.response.OrderItemResponse;
import com.tcc.orderservice.dto.response.OrderResponse;
import com.tcc.orderservice.dto.response.OrderStatusHistoryResponse;
import com.tcc.orderservice.dto.response.OrderSummaryResponse;
import com.tcc.orderservice.dto.response.PageResponse;
import com.tcc.orderservice.exception.InvalidStatusTransitionException;
import com.tcc.orderservice.exception.OrderNotFoundException;
import com.tcc.orderservice.exception.OrderValidationException;
import com.tcc.orderservice.repository.OrderItemRepository;
import com.tcc.orderservice.repository.OrderRepository;
import com.tcc.orderservice.repository.OrderStatusHistoryRepository;
import com.tcc.orderservice.repository.OrderSummaryRepository;

import reactor.core.publisher.Mono;

@Service
public class OrderService {

	private static final int MONEY_SCALE = 2;
	private static final int MAX_PAGE_SIZE = 100;
	private static final int TOP_CUSTOMERS_LIMIT = 10;

	private final OrderRepository orderRepository;
	private final OrderItemRepository orderItemRepository;
	private final OrderStatusHistoryRepository orderStatusHistoryRepository;
	private final OrderSummaryRepository orderSummaryRepository;

	public OrderService(OrderRepository orderRepository,
			OrderItemRepository orderItemRepository,
			OrderStatusHistoryRepository orderStatusHistoryRepository,
			OrderSummaryRepository orderSummaryRepository) {
		this.orderRepository = orderRepository;
		this.orderItemRepository = orderItemRepository;
		this.orderStatusHistoryRepository = orderStatusHistoryRepository;
		this.orderSummaryRepository = orderSummaryRepository;
	}

	public Mono<OrderResponse> createOrder(CreateOrderRequest request) {
		validateCreateOrderRequest(request);

		LocalDateTime now = LocalDateTime.now();
		UUID orderId = UUID.randomUUID();
		List<OrderItem> orderItems = mapRequestItemsToDomain(orderId, request.getItems());
		Order order = buildNewOrder(orderId, request, now, orderItems);

		return orderRepository.save(order)
				.flatMap(savedOrder -> orderItemRepository.saveAll(orderItems)
						.collectList()
						.flatMap(savedItems -> orderStatusHistoryRepository
								.save(OrderStatusHistory.initial(
										UUID.randomUUID(),
										savedOrder.getId(),
										OrderStatus.PENDING,
										now))
								.thenReturn(savedItems))
						.map(savedItems -> toOrderResponse(savedOrder, savedItems)));
	}

	public Mono<OrderResponse> getOrderById(UUID orderId) {
		return requireOrder(orderId)
				.flatMap(this::loadItemsAndMapOrder);
	}

	public Mono<List<OrderStatusHistoryResponse>> getOrderHistory(UUID orderId) {
		return requireOrder(orderId)
				.thenMany(orderStatusHistoryRepository.findByOrderIdOrderByChangedAtAsc(orderId))
				.map(this::toOrderStatusHistoryResponse)
				.collectList();
	}

	public Mono<PageResponse<OrderResponse>> getOrdersByCustomerId(UUID customerId, int page, int pageSize) {
		if (customerId == null) {
			throw new OrderValidationException("customerId is required");
		}

		validatePageParams(page, pageSize);
		long offset = calculateOffset(page, pageSize);

		Mono<Long> totalElementsMono = orderRepository.countByCustomerId(customerId)
				.defaultIfEmpty(0L);

		Mono<List<Order>> ordersMono = orderRepository.findByCustomerIdPaged(customerId, pageSize, offset)
				.collectList();

		return Mono.zip(totalElementsMono, ordersMono)
				.flatMap(tuple -> toPagedOrderResponse(tuple.getT2(), tuple.getT1(), page, pageSize));
	}

	public Mono<PageResponse<OrderResponse>> getAllOrders(OrderStatus status,
			LocalDate fromDate,
			LocalDate toDate,
			int page,
			int pageSize) {
		validatePageParams(page, pageSize);
		validateOptionalDateRange(fromDate, toDate);
		long offset = calculateOffset(page, pageSize);

		Mono<Long> totalElementsMono = orderRepository.countFilteredOrders(status, fromDate, toDate)
				.defaultIfEmpty(0L);

		Mono<List<Order>> ordersMono = orderRepository.findFilteredOrders(status, fromDate, toDate, pageSize, offset)
				.collectList();

		return Mono.zip(totalElementsMono, ordersMono)
				.flatMap(tuple -> toPagedOrderResponse(tuple.getT2(), tuple.getT1(), page, pageSize));
	}

	public Mono<OrderResponse> updateOrderStatus(UUID orderId, UpdateStatusRequest request) {
		if (request == null || request.getStatus() == null) {
			throw new OrderValidationException("status is required");
		}

		return requireOrder(orderId)
				.flatMap(order -> transitionOrderStatus(order, request.getStatus()))
				.flatMap(this::loadItemsAndMapOrder);
	}

	public Mono<OrderResponse> addOrderItem(UUID orderId, AddItemRequest request) {
		validateAddItemRequest(request);

		return requireOrder(orderId)
				.flatMap(order -> {
					ensureOrderIsPending(order);
					OrderItem orderItem = toOrderItem(orderId, request);

					return orderItemRepository.save(orderItem)
							.then(recalculateOrderFromPersistedItems(order));
				});
	}

	public Mono<OrderResponse> removeOrderItem(UUID orderId, UUID itemId) {
		if (itemId == null) {
			throw new OrderValidationException("itemId is required");
		}

		return requireOrder(orderId)
				.flatMap(order -> {
					ensureOrderIsPending(order);

					return orderItemRepository.findByOrderId(orderId)
							.collectList()
							.flatMap(items -> {
								if (items.isEmpty()) {
									throw new OrderValidationException("Order has no items");
								}

								boolean itemExists = items.stream()
										.anyMatch(item -> itemId.equals(item.getId()));
								if (!itemExists) {
									throw new OrderValidationException("Order item not found: " + itemId);
								}

								if (items.size() <= 1) {
									throw new OrderValidationException("Order must have at least one item");
								}

								return orderItemRepository.deleteByIdAndOrderId(itemId, orderId)
										.then(recalculateOrderFromPersistedItems(order));
							});
				});
	}

	public Mono<Void> cancelOrder(UUID orderId) {
		return requireOrder(orderId)
				.flatMap(order -> transitionOrderStatus(order, OrderStatus.CANCELLED))
				.then();
	}

	public Mono<OrderSummaryResponse> getSummary(LocalDate fromDate, LocalDate toDate) {
		validateSummaryDateRange(fromDate, toDate);

		Mono<Long> totalOrdersMono = orderSummaryRepository.countOrdersByDateRange(fromDate, toDate)
				.defaultIfEmpty(0L);

		Mono<BigDecimal> totalRevenueMono = orderSummaryRepository.sumRevenueByDateRange(fromDate, toDate)
				.defaultIfEmpty(BigDecimal.ZERO);

		Mono<Map<OrderStatus, Long>> ordersByStatusMono = orderSummaryRepository
				.countOrdersByStatusInDateRange(fromDate, toDate)
				.map(this::fillMissingStatuses)
				.defaultIfEmpty(fillMissingStatuses(null));

		Mono<List<OrderSummaryResponse.TopCustomerSummary>> topCustomersMono = orderSummaryRepository
				.findTopCustomersByRevenue(fromDate, toDate, TOP_CUSTOMERS_LIMIT)
				.collectList();

		Mono<List<OrderSummaryResponse.RevenueByDaySummary>> revenueByDayMono = orderSummaryRepository
				.findRevenueByDay(fromDate, toDate)
				.collectList();

		return Mono.zip(totalOrdersMono, totalRevenueMono, ordersByStatusMono, topCustomersMono, revenueByDayMono)
				.map(tuple -> {
					Long totalOrders = tuple.getT1();
					BigDecimal totalRevenue = normalizeMoney(tuple.getT2());
					Map<OrderStatus, Long> ordersByStatus = fillMissingStatuses(tuple.getT3());
					List<OrderSummaryResponse.TopCustomerSummary> topCustomers = tuple.getT4();
					List<OrderSummaryResponse.RevenueByDaySummary> revenueByDay = tuple.getT5();

					BigDecimal averageOrderValue = calculateAverageOrderValue(totalRevenue, totalOrders);

					return new OrderSummaryResponse(totalOrders,
							totalRevenue,
							averageOrderValue,
							ordersByStatus,
							topCustomers,
							revenueByDay);
				});
	}

	private Mono<Order> requireOrder(UUID orderId) {
		if (orderId == null) {
			throw new OrderValidationException("orderId is required");
		}

		return orderRepository.findById(orderId)
				.switchIfEmpty(Mono.error(new OrderNotFoundException(orderId)));
	}

	private Mono<OrderResponse> loadItemsAndMapOrder(Order order) {
		return orderItemRepository.findByOrderId(order.getId())
				.collectList()
				.map(orderItems -> toOrderResponse(order, orderItems));
	}

	private Mono<OrderResponse> recalculateOrderFromPersistedItems(Order order) {
		return orderItemRepository.findByOrderId(order.getId())
				.collectList()
				.flatMap(items -> {
					if (items.isEmpty()) {
						throw new OrderValidationException("Order must have at least one item");
					}

					recalculateOrderAmounts(order, items);
					order.setUpdatedAt(LocalDateTime.now());

					return orderRepository.save(order)
							.map(savedOrder -> toOrderResponse(savedOrder, items));
				});
	}

	private Mono<Order> transitionOrderStatus(Order order, OrderStatus nextStatus) {
		OrderStatus currentStatus = order.getStatus();
		if (currentStatus == null) {
			throw new OrderValidationException("Current order status is missing");
		}

		if (nextStatus == null) {
			throw new OrderValidationException("Target status is required");
		}

		if (!currentStatus.canTransitionTo(nextStatus)) {
			throw new InvalidStatusTransitionException(currentStatus, nextStatus);
		}

		LocalDateTime changedAt = LocalDateTime.now();
		order.setStatus(nextStatus);
		order.setUpdatedAt(changedAt);

		OrderStatusHistory history = OrderStatusHistory.transition(
				UUID.randomUUID(),
				order.getId(),
				currentStatus,
				nextStatus,
				changedAt);

		return orderRepository.save(order)
				.flatMap(savedOrder -> orderStatusHistoryRepository.save(history)
						.thenReturn(savedOrder));
	}

	private PageResponse<OrderResponse> emptyPage(long totalElements, int page, int pageSize) {
		return new PageResponse<>(
				List.of(),
				totalElements,
				calculateTotalPages(totalElements, pageSize),
				page,
				pageSize);
	}

	private Mono<PageResponse<OrderResponse>> toPagedOrderResponse(List<Order> orders,
			long totalElements,
			int page,
			int pageSize) {
		if (orders.isEmpty()) {
			return Mono.just(emptyPage(totalElements, page, pageSize));
		}

		Set<UUID> orderIds = orders.stream()
				.map(Order::getId)
				.collect(Collectors.toSet());

		return orderItemRepository.findByOrderIdIn(orderIds)
				.collectList()
				.map(items -> {
					Map<UUID, List<OrderItem>> itemsByOrderId = items.stream()
							.collect(Collectors.groupingBy(OrderItem::getOrderId));

					List<OrderResponse> content = orders.stream()
							.map(order -> toOrderResponse(order,
									itemsByOrderId.getOrDefault(order.getId(), List.of())))
							.toList();

					return new PageResponse<>(
							content,
							totalElements,
							calculateTotalPages(totalElements, pageSize),
							page,
							pageSize);
				});
	}

	private Order buildNewOrder(UUID orderId,
			CreateOrderRequest request,
			LocalDateTime now,
			List<OrderItem> orderItems) {
		Order order = new Order();
		order.markNew();
		order.setId(orderId);
		order.setCustomerId(request.getCustomerId());
		order.setStatus(OrderStatus.PENDING);
		order.setDiscountAmount(normalizeMoney(request.getDiscountAmount()));
		order.setCreatedAt(now);
		order.setUpdatedAt(now);

		ShippingAddressRequest shippingAddress = request.getShippingAddress();
		order.setShippingZipCode(shippingAddress.getZipCode());
		order.setShippingStreet(shippingAddress.getStreet());
		order.setShippingNumber(shippingAddress.getNumber());
		order.setShippingComplement(shippingAddress.getComplement());
		order.setShippingCity(shippingAddress.getCity());
		order.setShippingState(shippingAddress.getState());

		recalculateOrderAmounts(order, orderItems);
		return order;
	}

	private void recalculateOrderAmounts(Order order, List<OrderItem> orderItems) {
		order.setItems(orderItems);
		try {
			order.recalculateAmountsFromItems();
		} catch (IllegalArgumentException ex) {
			throw new OrderValidationException(ex.getMessage());
		}

		if (!order.hasConsistentAmounts()) {
			throw new OrderValidationException("Order amounts are inconsistent");
		}
	}

	private List<OrderItem> mapRequestItemsToDomain(UUID orderId, List<AddItemRequest> itemRequests) {
		List<OrderItem> orderItems = new ArrayList<>();
		for (AddItemRequest itemRequest : itemRequests) {
			orderItems.add(toOrderItem(orderId, itemRequest));
		}

		return orderItems;
	}

	private OrderItem toOrderItem(UUID orderId, AddItemRequest request) {
		validateAddItemRequest(request);

		try {
			OrderItem orderItem = new OrderItem(
					UUID.randomUUID(),
					orderId,
					request.getProductId(),
					request.getProductName(),
					request.getQuantity(),
					request.getUnitPrice(),
					null);
			orderItem.markNew();
			return orderItem;
		} catch (IllegalArgumentException ex) {
			throw new OrderValidationException(ex.getMessage());
		}
	}

	private OrderResponse toOrderResponse(Order order, List<OrderItem> orderItems) {
		List<OrderItemResponse> itemResponses = orderItems == null
				? List.of()
				: orderItems.stream()
						.map(this::toOrderItemResponse)
						.toList();

		OrderResponse.ShippingAddressResponse shippingAddressResponse =
				new OrderResponse.ShippingAddressResponse(
						order.getShippingZipCode(),
						order.getShippingStreet(),
						order.getShippingNumber(),
						order.getShippingComplement(),
						order.getShippingCity(),
						order.getShippingState());

		return new OrderResponse(
				order.getId(),
				order.getCustomerId(),
				order.getStatus(),
				normalizeMoney(order.getTotalAmount()),
				normalizeMoney(order.getDiscountAmount()),
				normalizeMoney(order.getFinalAmount()),
				shippingAddressResponse,
				itemResponses,
				order.getCreatedAt(),
				order.getUpdatedAt());
	}

	private OrderItemResponse toOrderItemResponse(OrderItem orderItem) {
		return new OrderItemResponse(
				orderItem.getId(),
				orderItem.getProductId(),
				orderItem.getProductName(),
				orderItem.getQuantity(),
				normalizeMoney(orderItem.getUnitPrice()),
				normalizeMoney(orderItem.getSubtotal()));
	}

	private OrderStatusHistoryResponse toOrderStatusHistoryResponse(OrderStatusHistory statusHistory) {
		return new OrderStatusHistoryResponse(
				statusHistory.getId(),
				statusHistory.getOrderId(),
				statusHistory.getPreviousStatus(),
				statusHistory.getNewStatus(),
				statusHistory.getChangedAt());
	}

	private int calculateTotalPages(long totalElements, int pageSize) {
		if (totalElements <= 0) {
			return 0;
		}

		return (int) ((totalElements + pageSize - 1) / pageSize);
	}

	private long calculateOffset(int page, int pageSize) {
		return (long) page * pageSize;
	}

	private void ensureOrderIsPending(Order order) {
		if (order.getStatus() != OrderStatus.PENDING) {
			throw new OrderValidationException("Operation allowed only when order status is PENDING");
		}
	}

	private void validateCreateOrderRequest(CreateOrderRequest request) {
		if (request == null) {
			throw new OrderValidationException("Create order request is required");
		}

		if (request.getCustomerId() == null) {
			throw new OrderValidationException("customerId is required");
		}

		if (request.getShippingAddress() == null) {
			throw new OrderValidationException("shippingAddress is required");
		}

		validateShippingAddress(request.getShippingAddress());

		if (request.getItems() == null || request.getItems().isEmpty()) {
			throw new OrderValidationException("Order must contain at least one item");
		}

		for (AddItemRequest itemRequest : request.getItems()) {
			validateAddItemRequest(itemRequest);
		}
	}

	private void validateAddItemRequest(AddItemRequest request) {
		if (request == null) {
			throw new OrderValidationException("Add item request is required");
		}

		if (request.getProductId() == null) {
			throw new OrderValidationException("productId is required");
		}

		if (isBlank(request.getProductName())) {
			throw new OrderValidationException("productName is required");
		}

		if (request.getQuantity() == null || request.getQuantity() < 1) {
			throw new OrderValidationException("quantity must be greater than or equal to 1");
		}

		if (request.getUnitPrice() == null || request.getUnitPrice().compareTo(BigDecimal.ZERO) <= 0) {
			throw new OrderValidationException("unitPrice must be greater than 0");
		}
	}

	private void validateShippingAddress(ShippingAddressRequest shippingAddress) {
		if (isBlank(shippingAddress.getZipCode())) {
			throw new OrderValidationException("shippingAddress.zipCode is required");
		}

		if (isBlank(shippingAddress.getStreet())) {
			throw new OrderValidationException("shippingAddress.street is required");
		}

		if (isBlank(shippingAddress.getNumber())) {
			throw new OrderValidationException("shippingAddress.number is required");
		}

		if (isBlank(shippingAddress.getCity())) {
			throw new OrderValidationException("shippingAddress.city is required");
		}

		if (isBlank(shippingAddress.getState())) {
			throw new OrderValidationException("shippingAddress.state is required");
		}

		if (shippingAddress.getState().trim().length() != 2) {
			throw new OrderValidationException("shippingAddress.state must have 2 characters");
		}
	}

	private void validatePageParams(int page, int pageSize) {
		if (page < 0) {
			throw new OrderValidationException("page must be greater than or equal to 0");
		}

		if (pageSize <= 0) {
			throw new OrderValidationException("pageSize must be greater than 0");
		}

		if (pageSize > MAX_PAGE_SIZE) {
			throw new OrderValidationException("pageSize must be less than or equal to " + MAX_PAGE_SIZE);
		}
	}

	private void validateOptionalDateRange(LocalDate fromDate, LocalDate toDate) {
		if (fromDate != null && toDate != null && fromDate.isAfter(toDate)) {
			throw new OrderValidationException("fromDate cannot be after toDate");
		}
	}

	private void validateSummaryDateRange(LocalDate fromDate, LocalDate toDate) {
		if (fromDate == null || toDate == null) {
			throw new OrderValidationException("fromDate and toDate are required");
		}

		if (fromDate.isAfter(toDate)) {
			throw new OrderValidationException("fromDate cannot be after toDate");
		}
	}

	private boolean isBlank(String value) {
		return value == null || value.trim().isEmpty();
	}

	private Map<OrderStatus, Long> fillMissingStatuses(Map<OrderStatus, Long> source) {
		EnumMap<OrderStatus, Long> counts = new EnumMap<>(OrderStatus.class);
		for (OrderStatus status : OrderStatus.values()) {
			long value = 0L;
			if (source != null && source.get(status) != null) {
				value = source.get(status);
			}
			counts.put(status, value);
		}

		return counts;
	}

	private BigDecimal calculateAverageOrderValue(BigDecimal totalRevenue, Long totalOrders) {
		if (totalOrders == null || totalOrders <= 0) {
			return BigDecimal.ZERO.setScale(MONEY_SCALE, RoundingMode.HALF_UP);
		}

		return normalizeMoney(totalRevenue)
				.divide(BigDecimal.valueOf(totalOrders), MONEY_SCALE, RoundingMode.HALF_UP);
	}

	private BigDecimal normalizeMoney(BigDecimal value) {
		if (value == null) {
			return BigDecimal.ZERO.setScale(MONEY_SCALE, RoundingMode.HALF_UP);
		}

		return value.setScale(MONEY_SCALE, RoundingMode.HALF_UP);
	}
}

