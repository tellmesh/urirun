FROM python:3.13-slim

LABEL org.opencontainers.image.title="urirun v8 shell worker"
LABEL io.tellmesh.urirun.manifest="/app/bindings.json"

WORKDIR /app
COPY bindings.json server.py write_report.sh ./
RUN chmod +x /app/write_report.sh
EXPOSE 8080
CMD ["python", "/app/server.py"]
