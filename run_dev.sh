#!/bin/bash
set -e

usage() {
    cat <<'EOF'
Usage: ./run_dev.sh [--port PORT]

Runs the local dev server. If the requested port is already in use, the script
automatically selects the next available port.

Options:
  -p, --port PORT   Preferred port (default: $PORT or 8000)
  -h, --help        Show this help
EOF
}

PREFERRED_PORT="${PORT:-8000}"
while [[ $# -gt 0 ]]; do
    case "${1:-}" in
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

# Build the frontend
echo "Building frontend..."
cd frontend
npm install --legacy-peer-deps
npm run build
cd ..

# Sync python dependencies
echo "Syncing dependencies (refresh teadata)..."
uv sync --upgrade-package teadata

# Run the server
echo "Starting server on http://localhost:${SERVER_PORT}"
uv run uvicorn teadata_mcp.sse_server:app --reload --port "${SERVER_PORT}"
