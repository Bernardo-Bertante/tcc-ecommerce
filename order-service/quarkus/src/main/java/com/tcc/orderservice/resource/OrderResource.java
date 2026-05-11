package com.tcc.orderservice.resource;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import com.tcc.orderservice.domain.OrderStatus;
import com.tcc.orderservice.dto.request.AddItemRequest;
import com.tcc.orderservice.dto.request.CreateOrderRequest;
import com.tcc.orderservice.dto.request.UpdateStatusRequest;
import com.tcc.orderservice.dto.response.OrderResponse;
import com.tcc.orderservice.dto.response.OrderStatusHistoryResponse;
import com.tcc.orderservice.dto.response.OrderSummaryResponse;
import com.tcc.orderservice.dto.response.PageResponse;
import com.tcc.orderservice.service.OrderService;

import io.smallrye.mutiny.Uni;

@Path("/orders")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class OrderResource {

    private final OrderService orderService;

    public OrderResource(OrderService orderService) {
        this.orderService = orderService;
    }

    @POST
    public Uni<Response> createOrder(CreateOrderRequest request) {
        return orderService.createOrder(request)
                .map(orderResponse -> Response.status(Response.Status.CREATED).entity(orderResponse).build());
    }

    @GET
    @Path("/{id}")
    public Uni<OrderResponse> getOrderById(@PathParam("id") UUID orderId) {
        return orderService.getOrderById(orderId);
    }

    @GET
    @Path("/{id}/history")
    public Uni<List<OrderStatusHistoryResponse>> getOrderHistory(@PathParam("id") UUID orderId) {
        return orderService.getOrderHistory(orderId);
    }

    @GET
    @Path("/customer/{customerId}")
    public Uni<PageResponse<OrderResponse>> getOrdersByCustomerId(
            @PathParam("customerId") UUID customerId,
            @QueryParam("page") Integer page,
            @QueryParam("pageSize") Integer pageSize) {
        return orderService.getOrdersByCustomerId(
                customerId,
                page == null ? 0 : page,
                pageSize == null ? 20 : pageSize);
    }

    @GET
    public Uni<PageResponse<OrderResponse>> getAllOrders(
            @QueryParam("status") OrderStatus status,
            @QueryParam("fromDate") LocalDate fromDate,
            @QueryParam("toDate") LocalDate toDate,
            @QueryParam("page") Integer page,
            @QueryParam("pageSize") Integer pageSize) {
        return orderService.getAllOrders(
                status,
                fromDate,
                toDate,
                page == null ? 0 : page,
                pageSize == null ? 20 : pageSize);
    }

    @GET
    @Path("/summary")
    public Uni<OrderSummaryResponse> getSummary(
            @QueryParam("fromDate") LocalDate fromDate,
            @QueryParam("toDate") LocalDate toDate) {
        return orderService.getSummary(fromDate, toDate);
    }

    @PUT
    @Path("/{id}/status")
    public Uni<OrderResponse> updateOrderStatus(
            @PathParam("id") UUID orderId,
            UpdateStatusRequest request) {
        return orderService.updateOrderStatus(orderId, request);
    }

    @POST
    @Path("/{id}/items")
    public Uni<OrderResponse> addOrderItem(
            @PathParam("id") UUID orderId,
            AddItemRequest request) {
        return orderService.addOrderItem(orderId, request);
    }

    @DELETE
    @Path("/{id}/items/{itemId}")
    public Uni<OrderResponse> removeOrderItem(
            @PathParam("id") UUID orderId,
            @PathParam("itemId") UUID itemId) {
        return orderService.removeOrderItem(orderId, itemId);
    }

    @DELETE
    @Path("/{id}")
    public Uni<Response> cancelOrder(@PathParam("id") UUID orderId) {
        return orderService.cancelOrder(orderId)
                .replaceWith(Response.noContent().build());
    }
}
