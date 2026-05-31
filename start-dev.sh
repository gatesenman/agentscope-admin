#!/usr/bin/env bash
#
# One-command local dev for AgentScope Admin.
#
# Starts the FastAPI backend (port 8000) and the Vue/Element-Plus frontend
# (port 5777) together, and tears both down on Ctrl-C.
#
# Usage:
#   ./start-dev.sh            # start backend + frontend
#   ./start-dev.sh --seed     # also seed the enterprise-risk ontology first
#
# Prerequisites: Node >= 22, pnpm >= 11, Python 3.12, Redis on :6379.
#
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SEED=0
[ "${1:-}" = "--seed" ] && SEED=1

pids=()
cleanup() {
  echo
  echo "[dev] shutting down…"
  for pid in "${pids[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT INT TERM

# 1) Frontend deps -----------------------------------------------------------
if [ ! -d node_modules ]; then
  echo "[dev] installing frontend dependencies (pnpm install)…"
  pnpm install
fi

# 2) Optional seed -----------------------------------------------------------
if [ "$SEED" = "1" ]; then
  bash server/start.sh >/tmp/agentscope-backend.boot.log 2>&1 &
  boot=$!
  # Wait for the API to come up, then seed and stop the boot instance.
  for _ in $(seq 1 30); do
    curl -sf http://localhost:8000/health >/dev/null 2>&1 && break
    sleep 1
  done
  bash server/seed.sh || true
  kill "$boot" >/dev/null 2>&1 || true
  sleep 1
fi

# 3) Backend -----------------------------------------------------------------
echo "[dev] starting backend → http://localhost:8000 (docs at /docs)"
bash server/start.sh &
pids+=($!)

# 4) Frontend ----------------------------------------------------------------
echo "[dev] starting frontend → http://localhost:5777"
pnpm dev:ele &
pids+=($!)

echo "[dev] backend=8000  frontend=5777 — press Ctrl-C to stop both."
echo "[dev] CLI: ./server/agentscope-admin --help  (or: cd server && pip install -e .)"
wait
