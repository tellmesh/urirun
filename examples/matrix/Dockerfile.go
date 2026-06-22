# Go runtime column: emit the shared hash bindings via the Go SDK example.
FROM golang:1.22-bookworm
COPY adapters/go /src/go
WORKDIR /src/go
# Write the emitted contract to the shared volume for the matrix verifier.
CMD ["sh", "-c", "go run ./example/hash-connector > /shared/go.json && echo 'go: emitted /shared/go.json'"]
