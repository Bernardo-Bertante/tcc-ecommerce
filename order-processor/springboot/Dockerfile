FROM public.ecr.aws/lambda/java:21

ARG LAMBDA_ZIP=build/distributions/order-processor-springboot-0.0.1-SNAPSHOT-lambda.zip

COPY ${LAMBDA_ZIP} /tmp/function.zip
RUN cd ${LAMBDA_TASK_ROOT} && jar -xf /tmp/function.zip && rm /tmp/function.zip

CMD ["org.springframework.cloud.function.adapter.aws.FunctionInvoker::handleRequest"]
