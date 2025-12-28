#!/bin/bash
set -e

usage() {
    cat <<'EOF'
Usage: ./run_mcp.sh [-s] [--port PORT]

Runs the server + a Cloudflare tunnel for use with ChatGPT Apps & Connectors.
If the requested port is already in use, the script automatically selects the
next available port.

Options:
  -s               Skip frontend build
  -p, --port PORT  Preferred port (default: $PORT or 8000)
  -h, --help       Show this help
EOF
}

# Function to cleanup background processes on exit
cleanup() {
    echo "Shutting down..."
    kill $(jobs -p) 2>/dev/null || true
    exit
}
trap cleanup SIGINT SIGTERM

SKIP_FRONTEND=0
PREFERRED_PORT="${PORT:-8000}"

while [[ $# -gt 0 ]]; do
    case "${1:-}" in
        -s)
            SKIP_FRONTEND=1
            shift
            ;;
        -p|--port)
            PREFERRED_PORT="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: ${1}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! [[ "${PREFERRED_PORT}" =~ ^[0-9]+$ ]] || [[ "${PREFERRED_PORT}" -lt 1 ]] || [[ "${PREFERRED_PORT}" -gt 65535 ]]; then
    echo "Error: invalid port '${PREFERRED_PORT}'" >&2
    exit 2
fi

PYTHON_BIN="python3"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

is_port_free() {
    local port="${1}"
    "${PYTHON_BIN}" - "${port}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
s = socket.socket()
try:
    s.bind(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
}

wait_for_listen() {
    local port="${1}"
    local max_tries="${2:-60}"
    local i=0
    while [[ "${i}" -lt "${max_tries}" ]]; do
        if "${PYTHON_BIN}" - "${port}" <<'PY' >/dev/null 2>&1; then
import socket
import sys

port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.2)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
            return 0
        fi
        sleep 0.5
        i=$((i + 1))
    done
    return 1
}

pick_port() {
    local base="${1}"
    local max_tries="${2:-50}"
    local port="${base}"
    local i=0
    while [[ "${i}" -lt "${max_tries}" ]]; do
        if is_port_free "${port}"; then
            echo "${port}"
            return 0
        fi
        port=$((port + 1))
        i=$((i + 1))
    done
    echo "Error: could not find a free port starting at ${base}" >&2
    return 1
}

SERVER_PORT="$(pick_port "${PREFERRED_PORT}" 100)"
if [[ "${SERVER_PORT}" != "${PREFERRED_PORT}" ]]; then
    echo "Port ${PREFERRED_PORT} is in use; using ${SERVER_PORT} instead."
fi

# Skip frontend build if -s flag is provided
if [[ "${SKIP_FRONTEND}" -ne 1 ]]; then
    echo "Building frontend..."
    cd frontend
    npm install --legacy-peer-deps
    npm run build
    cd ..
else
    echo "Skipping frontend build..."
fi

# Sync python dependencies
echo "Syncing dependencies (refresh teadata)..."
uv sync --upgrade-package teadata

# Check for cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Error: cloudflared is not installed. Install it with: brew install cloudflare/cloudflare/cloudflared"
    exit 1
fi

# Start the server in the background
echo "Starting server on http://localhost:${SERVER_PORT}..."
uv run uvicorn teadata_mcp.sse_server:app --reload --port "${SERVER_PORT}" &
SERVER_PID=$!

echo "Waiting for server to bind port ${SERVER_PORT}..."
if ! wait_for_listen "${SERVER_PORT}" 60; then
    echo "Error: server did not start listening on port ${SERVER_PORT}." >&2
    kill "${SERVER_PID}" 2>/dev/null || true
    exit 1
fi

# Start Cloudflare Tunnel and capture output
echo "Initializing Cloudflare Tunnel..."
cloudflared tunnel --url "http://localhost:${SERVER_PORT}" > .tunnel.log 2>&1 &
TUNNEL_PID=$!

# Wait for URL to appear in logs (max 30 seconds)
echo "Waiting for Tunnel URL..."
MAX_RETRIES=30
COUNT=0
URL=""
while [ -z "$URL" ] && [ $COUNT -lt $MAX_RETRIES ]; do
    sleep 1
URL=$(grep -oE 'https://[A-Za-z0-9-]+\.trycloudflare\.com' .tunnel.log | head -n 1 || true)
    ((COUNT++))
done

if [ -n "$URL" ]; then
    echo -e "\n\033[1;32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
    echo -e "\033[1;32m  SUCCESS: Cloudflare Tunnel is active!\033[0m"
    echo -e "\033[1;34m  Local server:\033[0m"
    echo -e "\n  \033[1;37mhttp://localhost:${SERVER_PORT}/mcp\033[0m"
    echo -e "\033[1;34m  Paste this URL into ChatGPT Apps & Connectors:\033[0m"
    echo -e "\n  \033[1;37m$URL/mcp\033[0m"
    echo -e "\033[1;32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n"
else
    echo "Error: Timed out waiting for Cloudflare Tunnel URL."
    echo "Check .tunnel.log for details."
    tail -n 50 .tunnel.log || true
    kill $SERVER_PID $TUNNEL_PID 2>/dev/null || true
    exit 1
fi

# Keep the script running to maintain processes
wait $TUNNEL_PID
