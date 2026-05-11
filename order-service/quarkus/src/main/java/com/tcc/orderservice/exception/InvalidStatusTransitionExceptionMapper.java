package com.tcc.orderservice.exception;

import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;

@Provider
public class InvalidStatusTransitionExceptionMapper implements ExceptionMapper<InvalidStatusTransitionException> {

    @Override
    public Response toResponse(InvalidStatusTransitionException exception) {
        return buildProblem(422, "Invalid status transition", exception.getMessage());
    }

    private Response buildProblem(int status, String title, String detail) {
        return Response.status(status)
                .type("application/problem+json")
                .entity(new ProblemResponse(status, title, detail))
                .build();
    }
}
