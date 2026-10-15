package com.tcc.orderprocessor.exp;

import software.amazon.awssdk.core.SdkRequest;
import software.amazon.awssdk.core.interceptor.Context;
import software.amazon.awssdk.core.interceptor.ExecutionAttributes;
import software.amazon.awssdk.core.interceptor.ExecutionInterceptor;

/** Splits each SDK call (exp-lazy): before/after HTTP transmission (connection, TLS, network) vs. the rest. */
public class ProbeInterceptor implements ExecutionInterceptor {

	@Override
	public void beforeExecution(Context.BeforeExecution context, ExecutionAttributes executionAttributes) {
		LazyProbe.mark("sdk_before_exec", describe(context.request()));
	}

	@Override
	public void beforeTransmission(Context.BeforeTransmission context, ExecutionAttributes executionAttributes) {
		LazyProbe.mark("sdk_before_tx", describe(context.request()));
	}

	@Override
	public void afterTransmission(Context.AfterTransmission context, ExecutionAttributes executionAttributes) {
		LazyProbe.mark("sdk_after_tx", describe(context.request()) + " http=" + context.httpResponse().statusCode());
	}

	@Override
	public void afterExecution(Context.AfterExecution context, ExecutionAttributes executionAttributes) {
		LazyProbe.mark("sdk_after_exec", describe(context.request()));
	}

	@Override
	public void onExecutionFailure(Context.FailedExecution context, ExecutionAttributes executionAttributes) {
		Throwable t = context.exception();
		LazyProbe.mark("sdk_fail", describe(context.request()) + " " + t.getClass().getName() + ": " + t.getMessage());
	}

	private static String describe(SdkRequest request) {
		return request.getClass().getSimpleName() + " table="
				+ request.getValueForField("TableName", String.class).orElse("?");
	}

}
