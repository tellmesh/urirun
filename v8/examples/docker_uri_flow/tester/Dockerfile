# Build context is the repository root so the urihandler package is available.
FROM python:3.12-slim

WORKDIR /app

# Install the real library (pulls pydantic + jsonschema from pyproject).
COPY adapters/python /app/urihandler-pkg
RUN pip install --no-cache-dir /app/urihandler-pkg

COPY v8/examples/docker_uri_flow/tester/run_compose_test.py /app/run_compose_test.py

CMD ["python", "/app/run_compose_test.py"]
