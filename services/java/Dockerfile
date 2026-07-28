FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline -q
COPY src ./src
RUN mvn package -q

FROM eclipse-temurin:17-jre-jammy
WORKDIR /srv
COPY --from=builder /build/target/smoke-test-factory-0.1.0.jar app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
