#!/usr/bin/env bash
# scripts/apply_vercel_vars.sh
#
# Idempotently applies Varuflow frontend env variables to a Vercel project.
# Mirror of apply_railway_vars.sh for the Next.js side.
#
# Usage:
#   1. npx vercel login
#   2. cd frontend && npx vercel link
#   3. cp deploy/production/frontend.env.example deploy/production/frontend.env.secret
#      and fill in real values.
#   4. Run:  bash scripts/apply_vercel_vars.sh production
#
# Vercel env tiers: "development" | "preview" | "production"
# We map  preproduction → preview  (Vercel's convention for staging).

set -euo pipefail

TIER="${1:-production}"
case "$TIER" in
  development|preproduction|production) ;;
  *) echo "❌ Tier must be development | preproduction | production"; exit 1 ;;
esac

VERCEL_TIER="$TIER"
[[ "$TIER" == "preproduction" ]] && VERCEL_TIER="preview"

ENV_FILE="deploy/${TIER}/frontend.env.secret"
EXAMPLE_FILE="deploy/${TIER}/frontend.env.example"

if ! command -v npx >/dev/null 2>&1; then
  echo "❌ npx not found — install Node 18+."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ $ENV_FILE not found."
  echo "   Create from the template:  cp $EXAMPLE_FILE $ENV_FILE"
  exit 1
fi

echo "▲ Applying $TIER ($VERCEL_TIER) env vars to Vercel …"
set_count=0
skip_count=0

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" != *"="* ]] && continue

  key="${line%%=*}"
  val="${line#*=}"
  key="$(echo "$key" | xargs)"
  val="$(echo "$val" | xargs)"

  if [[ -z "$val" || "$val" =~ ^\< ]]; then
    echo "  ⏭  skipping $key"
    skip_count=$((skip_count+1))
    continue
  fi

  # `vercel env add` refuses to overwrite, so remove first (silent) then add.
  (cd frontend && npx --yes vercel env rm "$key" "$VERCEL_TIER" --yes >/dev/null 2>&1 || true)
  (cd frontend && echo "$val" | npx --yes vercel env add "$key" "$VERCEL_TIER" >/dev/null)
  echo "  ✔ set $key"
  set_count=$((set_count+1))
done < "$ENV_FILE"

echo ""
echo "✅ Done. $set_count variables applied, $skip_count skipped."
echo ""
echo "Next step: redeploy so the new variables are baked into the build:"
echo "    cd frontend && npx vercel --prod      # or redeploy from the dashboard"
