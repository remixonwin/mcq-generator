#!/usr/bin/env bash

set -euo pipefail

# default hostname and port
HOST="0.0.0.0"
PORT="8000"

# parse arguments
while [[ $# -gt 0 ]]; do
  case "${1}" in
    --host)
      HOST="${2}"
      shift 2
      ;;
    --port)
      PORT="${2}"
      shift 2
      ;;
    *)
      echo "Unknown argument: ${1}" >&2
      exit 1
      ;;
  esac
done

# run uvicorn with the application
PYTHONPATH=/app/src uvicorn mcq_generator.asgi:app --host "${HOST}" --port "${PORT}"
