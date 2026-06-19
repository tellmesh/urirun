FROM python:3.13-slim

LABEL org.opencontainers.image.title="urirun v8 Python worker"
LABEL io.tellmesh.urirun.manifest="/app/bindings.json"

WORKDIR /app
COPY bindings.json server.py ./
EXPOSE 8080
CMD ["python", "/app/server.py"]
