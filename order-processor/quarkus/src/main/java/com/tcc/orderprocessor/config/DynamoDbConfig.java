package com.tcc.orderprocessor.config;

import java.net.URI;
import java.time.Clock;
import java.util.Optional;

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
            @ConfigProperty(name = "dynamodb.endpoint") Optional<String> dynamoDbEndpoint
    ) {
        DynamoDbClientBuilder builder = DynamoDbClient.builder()
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                .region(Region.of(awsRegion))
                .credentialsProvider(DefaultCredentialsProvider.create());

        dynamoDbEndpoint
                .filter(endpoint -> !endpoint.isBlank())
                .ifPresent(endpoint -> {
                    builder.endpointOverride(URI.create(endpoint));

                    if (isLocalEndpoint(endpoint)) {
                        builder.credentialsProvider(
                                StaticCredentialsProvider.create(
                                        AwsBasicCredentials.create("local", "local")
                                )
                        );
                    }
                });

        return builder.build();
    }

    private boolean isLocalEndpoint(String endpoint) {
        return endpoint.contains("localhost")
                || endpoint.contains("127.0.0.1")
                || endpoint.contains("localstack")
                || endpoint.contains("dynamodb-local");
    }

    @Produces
    @Singleton
    Clock clock() {
        return Clock.systemUTC();
    }
}