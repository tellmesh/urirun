# Java runtime column.
FROM eclipse-temurin:21-jdk
COPY adapters/java /src/java
WORKDIR /src/java
CMD ["bash","-c","d=$(mktemp -d); javac -d \"$d\" Urirun.java example/HashConnector.java && java -cp \"$d\" HashConnector > /shared/java.json && echo 'java: emitted /shared/java.json'"]
