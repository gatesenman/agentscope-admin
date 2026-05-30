#!/usr/bin/env bash
#
# Start the AgentScope Admin backend (FastAPI + AgentScope).
#
# Creates/activates a local virtualenv, installs dependencies on first run,
# ensures Redis is reachable, then launches uvicorn.
#
# Env overrides (all optional):
#   HOST                 bind host           (default 0.0.0.0)
#   PORT                 bind port           (default 8000)
#   RELOAD               "1" to auto-reload  (default 1)
#   AGENTSCOPE_ADMIN_REDIS_HOST / _REDIS_PORT / _REDIS_PASSWORD
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-1}"
REDIS_HOST="${AGENTSCOPE_ADMIN_REDIS_HOST:-localhost}"
REDIS_PORT="${AGENTSCOPE_ADMIN_REDIS_PORT:-6379}"

# 1) Virtualenv + deps -------------------------------------------------------
if [ ! -d .venv ]; then
  echo "[start] creating virtualenv (.venv)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import agentscope.app" >/dev/null 2>&1; then
  echo "[start] installing Python dependencies…"
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
fi

# 2) Redis check -------------------------------------------------------------
if command -v redis-cli >/dev/null 2>&1; then
  if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    echo "[start] Redis not reachable at $REDIS_HOST:$REDIS_PORT — trying to start a local instance…"
    (redis-server --daemonize yes >/dev/null 2>&1 || true)
    sleep 1
  fi
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1 \
    && echo "[start] Redis OK ($REDIS_HOST:$REDIS_PORT)" \
    || echo "[start] WARNING: Redis still unreachable — sessions/credentials will fail."
else
  echo "[start] WARNING: redis-cli not found; assuming Redis is available at $REDIS_HOST:$REDIS_PORT."
fi

# 3) Launch ------------------------------------------------------------------
echo "[start] launching uvicorn on $HOST:$PORT (reload=$RELOAD)…"
RELOAD_FLAG=""
[ "$RELOAD" = "1" ] && RELOAD_FLAG="--reload"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" $RELOAD_FLAG
