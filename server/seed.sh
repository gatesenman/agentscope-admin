#!/usr/bin/env bash
#
# Seed the complex enterprise-risk ontology (object types, properties,
# relations, action types and sample object instances) into the ontology DB.
#
# Safe to re-run: the seed script upserts by api_name.
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d .venv ]; then
  echo "[seed] virtualenv missing — run ./start.sh once first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "[seed] seeding enterprise-risk ontology…"
python scripts/seed_risk_ontology.py
echo "[seed] done."
