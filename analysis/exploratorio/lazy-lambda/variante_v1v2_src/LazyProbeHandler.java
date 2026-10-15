package com.tcc.orderprocessor.exp;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestStreamHandler;

import io.quarkus.funqy.lambda.FunqyStreamHandler;

/** Thin wrapper over FunqyStreamHandler (exp-lazy V1/V2): marks init and invocation boundaries. */
public class LazyProbeHandler implements RequestStreamHandler {

	static {
		LazyProbe.meta();
		LazyProbe.mark("init_wrapper_clinit");
	}

	private final FunqyStreamHandler delegate;

	public LazyProbeHandler() {
		LazyProbe.mark("init_quarkus_in");
		delegate = new FunqyStreamHandler();
		LazyProbe.mark("init_end");
		LazyProbe.flush();
	}

	@Override
	public void handleRequest(InputStream inputStream, OutputStream outputStream, Context context) throws IOException {
		LazyProbe.beginInvocation(context.getAwsRequestId());
		LazyProbe.mark("w_in");
		try {
			delegate.handleRequest(inputStream, outputStream, context);
		}
		finally {
			LazyProbe.mark("w_out");
			if (LazyProbe.invocation() == 1) {
				LazyProbe.tmpListing();
			}
			LazyProbe.flush();
		}
	}

}
