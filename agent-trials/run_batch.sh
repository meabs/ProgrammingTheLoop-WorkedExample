#!/usr/bin/env bash
# Sequential, interleaved arms so time-of-day / service drift hits both alike.
cd "$(dirname "$0")"
for n in $(seq "${1:-1}" "${2:-6}"); do
  for arm in A B; do
    echo "=== $(date +%H:%M:%S) $arm-$n"
    python3 harness.py run "$arm" "$n" > "runs/$arm-$n.harness.log" 2>&1
    tail -1 "runs/$arm-$n.harness.log"
  done
done
echo "=== batch done $(date +%H:%M:%S)"
