#!/usr/bin/env bash
# One command for every check an agent (or a person) needs before reporting a change.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-../.venv/bin/python}"
echo "== contract freshness"; "$PY" scripts/check_contract.py
echo "== tests"; "$PY" -m pytest -q
