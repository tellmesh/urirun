FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1
ENV API_PORT=9000
ENV NOVNC_PORT=6080

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    fluxbox \
    fonts-dejavu-core \
    iputils-ping \
    netcat-openbsd \
    novnc \
    procps \
    python3 \
    websockify \
    x11vnc \
    xterm \
    xvfb \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY pc_agent.py entrypoint.sh /opt/urirun-pc/
RUN chmod +x /opt/urirun-pc/entrypoint.sh

EXPOSE 6080 9000
ENTRYPOINT ["/opt/urirun-pc/entrypoint.sh"]
