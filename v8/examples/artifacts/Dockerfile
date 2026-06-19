FROM python:3.13-slim

LABEL org.opencontainers.image.title="urirun v8 demo tool"
LABEL org.opencontainers.image.source="https://github.com/tellmesh/urihandler"
LABEL io.tellmesh.urirun.manifest="urirun.manifest.json"

WORKDIR /app
COPY urirun.manifest.json /usr/share/urirun/manifest.json
CMD ["python3", "-V"]
