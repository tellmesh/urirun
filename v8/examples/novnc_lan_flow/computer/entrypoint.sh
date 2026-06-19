#!/usr/bin/env bash
set -euo pipefail

PC_NAME="${PC_NAME:-pc}"
PC_ROLE="${PC_ROLE:-node}"
API_PORT="${API_PORT:-9000}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
LOG_DIR="/workspace/logs"
LOG_FILE="$LOG_DIR/events.log"

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"

cat > /workspace/README.txt <<EOF
${PC_NAME} (${PC_ROLE})

URI API:
  http://${PC_NAME}:${API_PORT}/routes
  http://${PC_NAME}:${API_PORT}/run

Example URI:
  pc://${PC_NAME}/terminal/command/run
  log://${PC_NAME}/session/query/recent
EOF

echo "{\"event\":\"desktop.starting\",\"pc\":\"$PC_NAME\",\"role\":\"$PC_ROLE\"}" >> "$LOG_FILE"

Xvfb "$DISPLAY" -screen 0 1280x800x16 >/tmp/xvfb.log 2>&1 &
fluxbox >/tmp/fluxbox.log 2>&1 &
x11vnc -display "$DISPLAY" -nopw -forever -shared -listen 0.0.0.0 -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ "$NOVNC_PORT" localhost:5900 >/tmp/novnc.log 2>&1 &
python3 /opt/urirun-pc/pc_agent.py >/tmp/pc-agent.log 2>&1 &

sleep 2
DISPLAY="$DISPLAY" xterm -geometry 112x22+18+22 -title "${PC_NAME} URI logs" \
  -e "bash -lc 'printf \"${PC_NAME} (${PC_ROLE}) URI log\\n\\n\"; tail -n +1 -f ${LOG_FILE}'" &
DISPLAY="$DISPLAY" xterm -geometry 92x12+42+430 -title "${PC_NAME} shell" \
  -e "bash -lc 'cd /workspace; echo ${PC_NAME} shell; echo Try: curl -s http://localhost:${API_PORT}/routes; exec bash -l'" &

while true; do
  sleep 30
  echo "{\"event\":\"desktop.heartbeat\",\"pc\":\"$PC_NAME\",\"peers\":\"${PEERS:-}\"}" >> "$LOG_FILE"
done
