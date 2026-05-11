package com.tcc.orderservice.exception;

import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;

@Provider
public class OrderNotFoundExceptionMapper implements ExceptionMapper<OrderNotFoundException> {

    @Override
    public Response toResponse(OrderNotFoundException exception) {
        return buildProblem(Response.Status.NOT_FOUND, "Order not found", exception.getMessage());
    }

    private Response buildProblem(Response.Status status, String title, String detail) {
        return Response.status(status)
                .type("application/problem+json")
                .entity(new ProblemResponse(status.getStatusCode(), title, detail))
                .build();
    }
}
