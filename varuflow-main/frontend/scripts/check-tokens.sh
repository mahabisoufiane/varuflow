#!/usr/bin/env bash
# Design-token guard (Phase 1B) — fails CI when NEW hardcoded design values
# are introduced outside the token files. Tokens live in src/app/globals.css
# and src/styles/*; everything else must use --vf-* vars / Tailwind theme.
#
# Baseline debt is grandfathered via the *_MAX counts below; ratchet them
# DOWN as batches migrate. Raising a max is a review-blocking event.
set -uo pipefail
cd "$(dirname "$0")/.."

SRC="src"
EXCLUDE=(--exclude-dir=node_modules --exclude=globals.css --exclude-dir=styles)

count() { grep -rEo "$1" "$SRC" "${EXCLUDE[@]}" --include='*.tsx' --include='*.ts' 2>/dev/null | wc -l; }

ARB_COLOR=$(count '(bg|text|border|from|to|via|ring)-\[#[0-9a-fA-F]{3,8}\]')
ARB_SIZE=$(count 'text-\[[0-9.]+(px|rem)\]')
ARB_RADIUS=$(count 'rounded(-[a-z]+)?-\[[^]]+\]')
ARB_SHADOW=$(count 'shadow-\[[^]]+\]')

# Baseline = total OCCURRENCES as of 2026-07-06 (Phase 1A). Only ratchet DOWN.
ARB_COLOR_MAX=980
ARB_SIZE_MAX=379
ARB_RADIUS_MAX=6
ARB_SHADOW_MAX=11

fail=0
check() { # name current max
  if [ "$2" -gt "$3" ]; then
    echo "FAIL: $1 = $2 (max $3) — new hardcoded design values introduced"
    fail=1
  else
    echo "ok:   $1 = $2 (max $3)"
  fi
}
check "arbitrary Tailwind colors" "$ARB_COLOR" "$ARB_COLOR_MAX"
check "arbitrary font sizes"      "$ARB_SIZE"  "$ARB_SIZE_MAX"
check "arbitrary radii"           "$ARB_RADIUS" "$ARB_RADIUS_MAX"
check "arbitrary shadows"         "$ARB_SHADOW" "$ARB_SHADOW_MAX"
exit $fail
