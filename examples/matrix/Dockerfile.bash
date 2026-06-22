# Bash runtime column.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends coreutils && rm -rf /var/lib/apt/lists/*
COPY adapters/bash /src/bash
WORKDIR /src/bash
CMD ["bash","-c","bash example/hash-connector.sh > /shared/bash.json && echo 'bash: emitted /shared/bash.json'"]
