package com.tcc.orderprocessor.repository;

import com.tcc.orderprocessor.domain.ProcessingRequest;
import com.tcc.orderprocessor.domain.ProcessingResult;

public interface ProcessedOrderRepository {

	void save(ProcessingRequest request, ProcessingResult result);

}