#!/usr/bin/env bash
# Rebuilds the storefront-api git history from scratch and runs every stage of the worked example.
# All output under logs/ is genuine output from this script. Exits 1 if any stage gives a result other than
# the one the book reports (logs/08-checks.txt lists each check).
set -uo pipefail
cd "$(dirname "$0")" || exit 1
HERE="$PWD"; PY="$HERE/.venv/bin/python"; export PYTHON="$PY"
G="git -c user.name=Example -c user.email=example@example.invalid"
FBL="${FBL_SRC:-$HERE/AgentFrictionLoop}"   # AgentFrictionLoop v0.3.0 checkout (see README)
rm -rf logs storefront-api; mkdir -p logs storefront-api; cp -a stages/baseline/. storefront-api/
find . -name __pycache__ -prune -exec rm -rf {} +
cd storefront-api || exit 1
git init -q -b main && git config user.name Example && git config user.email example@example.invalid && $G add -A && $G commit -q -m "Baseline storefront-api"

echo "### Stage 0: baseline checks" | tee "$HERE/logs/00-baseline.txt"
bash scripts/test.sh 2>&1 | tee -a "$HERE/logs/00-baseline.txt"

echo "### Stage 4a: red (new tests, old code)" | tee "$HERE/logs/01-red.txt"
$G checkout -q -b feature/availability
cp "$HERE/stages/with-contract/tests/test_availability.py" tests/
cp "$HERE/stages/with-contract/app/clients/inventory.py" app/clients/
"$PY" -m pytest -q -rf tests/test_availability.py 2>&1 | grep -E '^(FAILED|[0-9]+ (passed|failed))' | tee -a "$HERE/logs/01-red.txt"

echo "### Stage 4b: green (endpoint added)" | tee "$HERE/logs/02-green.txt"
cp "$HERE/stages/with-contract/app/main.py" app/
bash scripts/test.sh 2>&1 | tee -a "$HERE/logs/02-green.txt"
$G add -A && $G commit -q -m "Add GET /products/{sku}/availability (inventory contract 2.1.0)"

echo "### Stage 5: real behaviour, inventory 2.1.0 running" | tee "$HERE/logs/03-live-v2.txt"
"$HERE/run_live.sh" 2.1.0 2>&1 | tee -a "$HERE/logs/03-live-v2.txt"; LIVE_V2=${PIPESTATUS[0]}

echo "### Stage 6: the diff a reviewer sees" | tee "$HERE/logs/04-diffstat.txt"
git diff --stat main..feature/availability | tee -a "$HERE/logs/04-diffstat.txt"

echo "### Missing knowledge: no contract, names guessed" | tee "$HERE/logs/05-guessed.txt"
$G checkout -q -b scenario/guessed main
git rm -q contracts/inventory.openapi.yaml; printf 'none\n' > contracts/PINNED
for f in app/main.py app/clients/inventory.py tests/test_availability.py; do cp "$HERE/stages/guessed/$f" "$f"; done
"$PY" -m pytest -q 2>&1 | tail -1 | tee -a "$HERE/logs/05-guessed.txt"
"$HERE/run_live.sh" 2.1.0 2>&1 | tee -a "$HERE/logs/05-guessed.txt"; LIVE_GUESSED=${PIPESTATUS[0]}
$G add -A && $G commit -q -m "scenario: written without the contract (guessed names)"

echo "### Stale knowledge: provider has moved to 3.0.0, consumer still pinned to 2.1.0" | tee "$HERE/logs/06-stale.txt"
$G checkout -q feature/availability
INVENTORY_CONTRACT="$HERE/inventory-service/contracts/inventory.v3.openapi.yaml" bash scripts/test.sh 2>&1 | tee -a "$HERE/logs/06-stale.txt"
GATE_STALE=${PIPESTATUS[0]}; echo "(exit code of scripts/test.sh: $GATE_STALE)" | tee -a "$HERE/logs/06-stale.txt"
echo "-- tests alone, without the freshness gate:" | tee -a "$HERE/logs/06-stale.txt"
"$PY" -m pytest -q 2>&1 | tail -1 | tee -a "$HERE/logs/06-stale.txt"
"$HERE/run_live.sh" 3.0.0 2>&1 | tee -a "$HERE/logs/06-stale.txt"; LIVE_V3=${PIPESTATUS[0]}

echo "### Stage 7: record friction with AgentFrictionLoop" | tee "$HERE/logs/07-friction.txt"
if [ -f "$FBL/.apm/skills/friction-loop/install.py" ]; then
  FBL_HOME_DIR="$HERE/.fbl-home"; rm -rf "$FBL_HOME_DIR"
  "$PY" "$FBL/.apm/skills/friction-loop/install.py" --repo . --domain example --home "$FBL_HOME_DIR" --harness none --no-command-capture 2>&1 | sed "s#$HERE#<worked-example>#g" | tee -a "$HERE/logs/07-friction.txt"
  ./.fbl/bin/fbl-friction --origin verification "no documented way to run storefront against a live inventory service; started both with uvicorn by hand to check real behaviour" 2>&1 | tee -a "$HERE/logs/07-friction.txt"
  git checkout -q AGENTS.md 2>/dev/null || true
  $G commit -q --allow-empty -m "Record friction from the availability change"; sleep 4
  echo "-- records on the hidden insights branch:" | tee -a "$HERE/logs/07-friction.txt"
  git log fbl-insights --format='%s' 2>&1 | tee -a "$HERE/logs/07-friction.txt"
  REC=$(git -C .git/fbl/insights ls-files 'records/*' | head -1)
  [ -n "$REC" ] && "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print(json.dumps({k:d[k] for k in ('friction','diff_stats') if k in d},indent=1))" ".git/fbl/insights/$REC" | tee -a "$HERE/logs/07-friction.txt"
  echo "-- fbl-doctor on this repository:" | tee -a "$HERE/logs/07-friction.txt"
  ./.fbl/bin/fbl-doctor 2>&1 | sed "s#$HERE#<worked-example>#g" | tee -a "$HERE/logs/07-friction.txt"
else
  echo "AgentFrictionLoop not found at $FBL; stage skipped" | tee -a "$HERE/logs/07-friction.txt"
fi

echo "### Checks: does every stage give the result the book reports?" | tee "$HERE/logs/08-checks.txt"
expect() {  # log file, fixed string that must appear in it
  if grep -qF -- "$2" "$HERE/logs/$1"; then echo "ok    $1: $2"; else echo "FAIL  $1: expected: $2"; fi
}
expect_code() {  # what, actual exit code, expected exit code
  if [ "$2" = "$3" ]; then echo "ok    $1 exit code $2"; else echo "FAIL  $1 exit code $2, expected $3"; fi
}
{  # runs in a pipeline subshell, so failures are counted from the log afterwards
  expect 00-baseline.txt "ok: pinned 2.1.0, provider publishes 2.1.0"
  expect 00-baseline.txt "2 passed in"
  expect 01-red.txt "4 failed, 3 passed in"
  expect 02-green.txt "9 passed in"
  expect 03-live-v2.txt '{"sku":"MUG-001","available":9,"in_stock":true} [200]'
  expect 03-live-v2.txt '{"sku":"TEE-042","available":0,"in_stock":false} [200]'
  expect 03-live-v2.txt '{"detail":"unknown product"} [404]'
  expect_code "run_live.sh 2.1.0 (stage 5)" "${LIVE_V2:-unset}" 0
  expect 04-diffstat.txt "3 files changed, 121 insertions(+), 1 deletion(-)"
  expect 05-guessed.txt "8 passed in"
  expect 05-guessed.txt '{"detail":"unknown to inventory"} [404]'
  expect_code "run_live.sh 2.1.0 (guessed names)" "${LIVE_GUESSED:-unset}" 1
  expect 06-stale.txt "STALE: pinned inventory.openapi.yaml 2.1.0, provider publishes 3.0.0 (major change)"
  expect_code "scripts/test.sh (stale contract)" "${GATE_STALE:-unset}" 1
  expect 06-stale.txt "9 passed in"
  expect 06-stale.txt '{"detail":"inventory unavailable"} [502]'
  expect_code "run_live.sh 3.0.0 (stale contract)" "${LIVE_V3:-unset}" 1
  expect 07-friction.txt "friction recorded: verification / test-order"
  expect 07-friction.txt "nothing found"
} | tee -a "$HERE/logs/08-checks.txt"
fails=$(grep -c '^FAIL' "$HERE/logs/08-checks.txt")
if [ "$fails" -gt 0 ]; then echo "REPRODUCTION MISMATCH: $fails check(s) failed" | tee -a "$HERE/logs/08-checks.txt"; exit 1; fi
echo "all checks passed" | tee -a "$HERE/logs/08-checks.txt"
