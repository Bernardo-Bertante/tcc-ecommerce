package com.tcc.order_service_springboot;

import org.springframework.boot.SpringApplication;

public class TestOrderServiceSpringbootApplication {

	public static void main(String[] args) {
		SpringApplication.from(OrderServiceSpringbootApplication::main).with(TestcontainersConfiguration.class).run(args);
	}

}
