FROM python:3.13-slim

LABEL org.opencontainers.image.title="urirun v8 flow orchestrator"

WORKDIR /app
COPY flow_runner.py ./
CMD ["python", "/app/flow_runner.py", "/flows/cross_service_report.yaml"]
