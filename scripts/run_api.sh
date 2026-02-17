#!/usr/bin/env bash
# Lightweight script to run the API locally using uvicorn.
# Usage: ./scripts/run_api.sh [--host HOST] [--port PORT] [--kill-existing] [--auto-port]

set -euo pipefail

HOST="127.0.0.1"
PORT="8000"
KILL_EXISTING=false
AUTO_PORT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --kill-existing) KILL_EXISTING=true; shift;;
    --auto-port) AUTO_PORT=true; shift;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --host HOST         Host to bind to (default: 127.0.0.1)"
      echo "  --port PORT         Port to bind to (default: 8000)"
      echo "  --kill-existing     Kill any existing process on the port before starting"
      echo "  --auto-port         Automatically use next available port if port is busy"
      echo "  --help, -h          Show this help message"
      exit 0
      ;;
    *) echo "Unknown argument: $1"; exit 1;;
  esac
done

export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src"

# Function to check if a port is in use
is_port_in_use() {
  local port="$1"
  # Try multiple methods to check port availability
  if command -v ss &> /dev/null; then
    ss -tuln | grep -q ":${port} " && return 0
  elif command -v netstat &> /dev/null; then
    netstat -tuln | grep -q ":${port} " && return 0
  elif command -v lsof &> /dev/null; then
    lsof -i ":${port}" &> /dev/null && return 0
  fi
  # Fallback: try to bind to the port
  python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', ${port})); s.close()" 2>/dev/null && return 1 || return 0
}

# Function to get PID of process using a port
get_pid_using_port() {
  local port="$1"
  if command -v lsof &> /dev/null; then
    lsof -ti ":${port}" 2>/dev/null | head -1
  elif command -v ss &> /dev/null; then
    local pid
    pid=$(ss -tlnp 2>/dev/null | grep ":${port} " | grep -oP 'pid=\K[0-9]+' | head -1)
    echo "$pid"
  fi
}

# Function to kill process on port
kill_process_on_port() {
  local port="$1"
  local pid
  pid=$(get_pid_using_port "$port")
  if [[ -n "$pid" ]]; then
    echo "Found process (PID: $pid) using port $port. Killing it..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    # Force kill if still running
    if is_port_in_use "$port"; then
      kill -9 "$pid" 2>/dev/null || true
      sleep 1
    fi
  fi
}

# Function to find next available port
find_available_port() {
  local start_port="$1"
  local port="$start_port"
  local max_attempts=100
  local attempt=0
  
  while [[ $attempt -lt $max_attempts ]]; do
    if ! is_port_in_use "$port"; then
      echo "$port"
      return 0
    fi
    ((port++))
    ((attempt++))
  done
  
  return 1
}

# Handle port already in use
if is_port_in_use "$PORT"; then
  if [[ "$AUTO_PORT" == true ]]; then
    echo "Port $PORT is already in use. Attempting to find an available port..."
    NEW_PORT=$(find_available_port $((PORT + 1)))
    if [[ -n "$NEW_PORT" ]]; then
      PORT="$NEW_PORT"
      echo "Using alternative port: $PORT"
    else
      echo "ERROR: Could not find an available port"
      exit 1
    fi
  elif [[ "$KILL_EXISTING" == true ]]; then
    echo "Port $PORT is already in use. Killing existing process..."
    kill_process_on_port "$PORT"
  else
    echo "ERROR: Port $PORT is already in use."
    echo ""
    echo "Options to resolve:"
    echo "  1. Run with --kill-existing to kill the process using the port"
    echo "  2. Run with --auto-port to automatically use next available port"
    echo "  3. Run with --port <NEW_PORT> to use a different port"
    echo ""
    echo "To see what's using the port, run:"
    echo "  lsof -i :$PORT"
    echo "  ss -tulpn | grep :$PORT"
    exit 1
  fi
fi

# Handle shutdown signals gracefully
cleanup() {
  echo ""
  echo "Shutting down API server..."
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting API on http://$HOST:$PORT"
echo "Press Ctrl+C to stop"
echo ""

exec uvicorn mcq_generator.asgi:app --host "$HOST" --port "$PORT" --reload
