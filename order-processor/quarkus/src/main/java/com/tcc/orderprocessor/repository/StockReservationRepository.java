package com.tcc.orderprocessor.repository;

import java.util.List;

import com.tcc.orderprocessor.domain.StockReservation;

public interface StockReservationRepository {

	void saveAll(List<StockReservation> reservations);

}