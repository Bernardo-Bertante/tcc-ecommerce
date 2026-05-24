package com.tcc.orderprocessor.config;

import java.net.URI;
import java.time.Clock;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.StringUtils;

import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.DynamoDbClientBuilder;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(DynamoDbProperties.class)
public class DynamoDbConfig {

	@Bean
	DynamoDbClient dynamoDbClient(
			@Value("${aws.region:us-east-1}") String awsRegion,
			@Value("${dynamodb.endpoint:}") String dynamoDbEndpoint
	) {
		DynamoDbClientBuilder builder = DynamoDbClient.builder()
				.region(Region.of(awsRegion));

		if (StringUtils.hasText(dynamoDbEndpoint)) {
			builder.endpointOverride(URI.create(dynamoDbEndpoint))
					.credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create("local", "local")));
		} else {
			builder.credentialsProvider(DefaultCredentialsProvider.create());
		}

		return builder.build();
	}

	@Bean
	Clock clock() {
		return Clock.systemUTC();
	}

}
