package com.tcc.orderprocessor.config;

import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.cloud.function.json.JacksonMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

@Configuration(proxyBeanMethods = false)
public class JacksonConfig {

	@Bean
	ObjectMapper objectMapper() {
		return new ObjectMapper()
				.registerModule(new JavaTimeModule())
				.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
	}

	@Bean
	BeanPostProcessor jsonMapperCustomizer() {
		return new BeanPostProcessor() {
			@Override
			public Object postProcessAfterInitialization(Object bean, String beanName) {
				if (bean instanceof JacksonMapper jacksonMapper) {
					jacksonMapper.configureObjectMapper(objectMapper -> objectMapper
							.registerModule(new JavaTimeModule())
							.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS));
				}
				return bean;
			}
		};
	}

}