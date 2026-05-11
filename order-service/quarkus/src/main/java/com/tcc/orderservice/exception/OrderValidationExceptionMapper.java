package com.tcc.orderservice.exception;

import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;

@Provider
public class OrderValidationExceptionMapper implements ExceptionMapper<OrderValidationException> {

    @Override
    public Response toResponse(OrderValidationException exception) {
        return buildProblem(Response.Status.BAD_REQUEST, "Validation error", exception.getMessage());
    }

    private Response buildProblem(Response.Status status, String title, String detail) {
        return Response.status(status)
                .type("application/problem+json")
                .entity(new ProblemResponse(status.getStatusCode(), title, detail))
                .build();
    }
}
