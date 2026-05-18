FROM registry.access.redhat.com/ubi9/openjdk-21-runtime:1.24

ENV LANGUAGE='en_US:en'

ARG JAR_FILE=build/libs/order-service-springboot-0.0.1-SNAPSHOT.jar

COPY --chown=185 ${JAR_FILE} /deployments/app.jar

EXPOSE 8081
USER 185

ENV JAVA_APP_JAR="/deployments/app.jar"

ENTRYPOINT ["/opt/jboss/container/java/run/run-java.sh"]
