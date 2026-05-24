package com.tcc.orderprocessor.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import com.tcc.orderprocessor.ProcessingFixtures;
import com.tcc.orderprocessor.domain.ProcessingResult;

class ProcessingCalculatorTest {

	private final ProcessingCalculator calculator = new ProcessingCalculator();

	@Test
	void fiscalNumberIsDeterministic() {
		String first = calculator.fiscalNumber(ProcessingFixtures.ORDER_ID);
		String second = calculator.fiscalNumber(ProcessingFixtures.ORDER_ID);

		assertThat(first).isEqualTo("NF-3F2504E04F89");
		assertThat(second).isEqualTo(first);
	}

	@Test
	void calculatesExpectedResultForValidMgRequest() {
		ProcessingResult result = calculator.calculate(ProcessingFixtures.validRequest(), ProcessingFixtures.PROCESSED_AT);

		assertThat(result.orderId()).isEqualTo(ProcessingFixtures.ORDER_ID);
		assertThat(result.fiscalNumber()).isEqualTo("NF-3F2504E04F89");
		assertMoney(result.shippingCost(), "19.90");
		assertMoney(result.taxAmount(), "31.98");
		assertMoney(result.finalAmount(), "451.68");
		assertThat(result.estimatedDeliveryDays()).isEqualTo(2);
		assertThat(result.processedAt()).isEqualTo(ProcessingFixtures.PROCESSED_AT);
	}

	@ParameterizedTest
	@CsvSource({
		"MG,19.90,2",
		"SP,19.90,3",
		"PR,24.90,5",
		"GO,29.90,5",
		"MT,29.90,6",
		"BA,34.90,7",
		"AM,39.90,10",
		"XX,29.90,6"
	})
	void calculatesShippingAndDeliveryByState(String state, String expectedShipping, int expectedDays) {
		assertMoney(calculator.shippingCost(state), expectedShipping);
		assertThat(calculator.estimatedDeliveryDays(state)).isEqualTo(expectedDays);
	}

	@Test
	void calculatesTaxWithHalfUpScaleTwo() {
		assertMoney(calculator.taxAmount(new BigDecimal("10.07")), "0.81");
		assertMoney(calculator.taxAmount(new BigDecimal("10.06")), "0.80");
	}

	@Test
	void calculatesFinalAmountAsTotalPlusShippingAndTax() {
		ProcessingResult result = calculator.calculate(ProcessingFixtures.validRequest(), ProcessingFixtures.PROCESSED_AT);
		BigDecimal expected = ProcessingFixtures.validRequest().totalAmount()
				.add(result.shippingCost())
				.add(result.taxAmount())
				.setScale(2, java.math.RoundingMode.HALF_UP);

		assertThat(result.finalAmount()).isEqualByComparingTo(expected);
		assertThat(result.finalAmount().scale()).isEqualTo(2);
	}

	private static void assertMoney(BigDecimal actual, String expected) {
		assertThat(actual).isEqualByComparingTo(expected);
		assertThat(actual.scale()).isEqualTo(2);
	}

}