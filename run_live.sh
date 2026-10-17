#!/usr/bin/env bash
# Start the provider (inventory) and consumer (storefront), then exercise the endpoint like a user.
# Usage: run_live.sh [inventory API version]   e.g. 2.1.0 or 3.0.0
# Exit 0 only if every response has the status the 2.1.0 contract and the brief promise
# (MUG-001 200, TEE-042 200, NOPE-000 404); 1 if any differs; 2 if the services can't be started.
set -uo pipefail
cd "$(dirname "$0")" || exit 2
V="${1:-2.1.0}"
for port in 8000 8001; do
  if curl -s -o /dev/null "localhost:$port/"; then echo "port $port is already in use; stop that process first" >&2; exit 2; fi
done
INVENTORY_API_VERSION="$V" .venv/bin/python -m uvicorn --app-dir inventory-service app:app --port 8001 --log-level warning & P1=$!
(cd storefront-api && INVENTORY_URL=http://127.0.0.1:8001 ../.venv/bin/python -m uvicorn app.main:app --port 8000 --log-level warning) & P2=$!
trap 'kill $P1 $P2 2>/dev/null; wait 2>/dev/null' EXIT
ready=0
for _ in $(seq 1 100); do   # wait up to 10 s for both services
  if curl -s -o /dev/null localhost:8001/v2/stock/MUG-001 && curl -s -o /dev/null localhost:8000/products/MUG-001; then ready=1; break; fi
  sleep 0.1
done
if [ "$ready" != 1 ]; then echo "services did not start within 10 s" >&2; exit 2; fi
bad=0
for check in MUG-001:200 TEE-042:200 NOPE-000:404; do
  sku="${check%%:*}"; want="${check##*:}"
  echo "\$ curl -s -w ' [%{http_code}]' localhost:8000/products/$sku/availability"
  out=$(curl -s -w " [%{http_code}]" "localhost:8000/products/$sku/availability")
  echo "$out"
  [[ "$out" == *" [$want]" ]] || bad=$((bad + 1))
done
if [ "$bad" -gt 0 ]; then echo "(live check: $bad of 3 responses not as the contract promises; exit 1)"; exit 1; fi
