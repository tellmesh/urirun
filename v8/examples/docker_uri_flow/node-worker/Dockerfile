FROM node:22-alpine

LABEL org.opencontainers.image.title="urirun v8 Node worker"
LABEL io.tellmesh.urirun.manifest="/app/bindings.json"

WORKDIR /app
COPY bindings.json server.js ./
EXPOSE 8080
CMD ["node", "/app/server.js"]
