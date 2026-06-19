# Build context is the repository root so the urirun package is available.
# One image runs both the workers (CMD overridden per service) and the tester.
FROM python:3.12-slim

WORKDIR /app

COPY adapters/python /app/urirun-pkg
RUN pip install --no-cache-dir /app/urirun-pkg grpcio

COPY v8/examples/multi_transport/worker.py /app/worker.py
COPY v8/examples/multi_transport/run_multi_test.py /app/run_multi_test.py
COPY v8/examples/multi_transport/web-bindings.json /app/web-bindings.json
COPY v8/examples/multi_transport/rpc-bindings.json /app/rpc-bindings.json

CMD ["python", "/app/worker.py"]
