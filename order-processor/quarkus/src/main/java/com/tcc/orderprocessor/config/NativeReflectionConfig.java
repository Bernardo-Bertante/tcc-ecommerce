package com.tcc.orderprocessor.config;

import com.tcc.orderprocessor.domain.Address;
import com.tcc.orderprocessor.domain.ProcessingItem;
import com.tcc.orderprocessor.domain.ProcessingRequest;

import io.quarkus.amazon.lambda.runtime.FunctionError;
import io.quarkus.runtime.annotations.RegisterForReflection;

@RegisterForReflection(targets = {
		Address.class,
		FunctionError.class,
		ProcessingItem.class,
		ProcessingRequest.class,
})
public final class NativeReflectionConfig {

	private NativeReflectionConfig() {
	}

}