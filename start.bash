#!/usr/bin/env bash
set -euo pipefail

PORT=${PORT:-8766}
HOST=${HOST:-0.0.0.0}
BASELINE_SPEC=${BASELINE_SPEC:-closed_loop.freeaskworld_connector.simple_baseline:create_baseline}

python start_cloudflared.py "$PORT" &
CLOUDFLARED_PID=$!

python -m closed_loop.freeaskworld_connector.server \
	--host "$HOST" \
	--port "$PORT" \
	--baseline "$BASELINE_SPEC"

wait "$CLOUDFLARED_PID"