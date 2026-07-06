#!/usr/bin/env bash
# Silent-swallow guard (P0 regression fence, 2026-07-06).
# `.catch(() => [])` / `.catch(() => null)` on data fetches turn API failures
# into fake empty data — on the dashboard that rendered "0 kr outstanding"
# when the backend was down. Failed and empty must stay distinguishable.
# Ratchet: baseline = today's count; only goes DOWN. Raising it is a
# review-blocking event.
set -uo pipefail
cd "$(dirname "$0")/.."

COUNT=$(grep -rEo '\.catch\(\(\) => (\[\]|null)' src \
  --include='*.ts' --include='*.tsx' --exclude-dir=node_modules 2>/dev/null | wc -l)

MAX=55

if [ "$COUNT" -gt "$MAX" ]; then
  echo "FAIL: $COUNT silent-swallow catches (max $MAX) — new '.catch(() => [])' or '.catch(() => null)' introduced."
  echo "Handle the error (per-widget error state / toast) instead of faking empty data."
  grep -rEn '\.catch\(\(\) => (\[\]|null)' src --include='*.ts' --include='*.tsx' | tail -5
  exit 1
fi
echo "ok: silent-swallow catches = $COUNT (max $MAX)"
