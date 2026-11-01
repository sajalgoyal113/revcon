#!/bin/sh
# Local only: bound to 127.0.0.1. Uses .venv when present.
cd "$(dirname "$0")"
PORT="${PORT:-8502}"
if [ -d ".venv" ]; then
  exec .venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port "$PORT"
else
  exec streamlit run app.py --server.address 127.0.0.1 --server.port "$PORT"
fi
