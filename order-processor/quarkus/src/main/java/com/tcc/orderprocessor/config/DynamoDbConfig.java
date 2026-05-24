package com.tcc.orderprocessor.config;

import java.net.URI;
import java.time.Clock;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Singleton;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.DynamoDbClientBuilder;

@ApplicationScoped
public class DynamoDbConfig {

	@Produces
	@Singleton
	DynamoDbClient dynamoDbClient(
			@ConfigProperty(name = "aws.region", defaultValue = "us-east-1") String awsRegion,
			@ConfigProperty(name = "dynamodb.endpoint", defaultValue = "") String dynamoDbEndpoint
	) {
		DynamoDbClientBuilder builder = DynamoDbClient.builder()
				.httpClientBuilder(UrlConnectionHttpClient.builder())
				.region(Region.of(awsRegion));

		if (dynamoDbEndpoint != null && !dynamoDbEndpoint.isBlank()) {
			builder.endpointOverride(URI.create(dynamoDbEndpoint))
					.credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create("local", "local")));
		} else {
			builder.credentialsProvider(DefaultCredentialsProvider.create());
		}

		return builder.build();
	}

	@Produces
	@Singleton
	Clock clock() {
		return Clock.systemUTC();
	}

}
