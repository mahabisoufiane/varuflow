#!/usr/bin/env bash
# scripts/apply_railway_vars.sh
#
# Idempotently applies Varuflow backend env variables to a Railway service.
# Reads from deploy/<tier>/backend.env.example (placeholder values) and
# from a local, git-ignored file  deploy/<tier>/backend.env.secret  that
# YOU create with the real secrets.
#
# Usage:
#   1. railway login
#   2. cd into the Railway project:   railway link
#   3. Copy deploy/production/backend.env.example → deploy/production/backend.env.secret
#      and fill in the real Supabase / Stripe / Resend / OpenAI values.
#   4. Run:  bash scripts/apply_railway_vars.sh production
#
# The secret file is never pushed (see .gitignore entry added below).
# The script prints every variable name it sets but NEVER the value.

set -euo pipefail

TIER="${1:-production}"
ENV_FILE="deploy/${TIER}/backend.env.secret"
EXAMPLE_FILE="deploy/${TIER}/backend.env.example"

if ! command -v railway >/dev/null 2>&1; then
  echo "❌ railway CLI not found. Install with:"
  echo "   curl -fsSL https://railway.app/install.sh | sh"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ $ENV_FILE not found."
  echo "   Create it from the template:  cp $EXAMPLE_FILE $ENV_FILE"
  echo "   then fill in real values."
  exit 1
fi

# Verify you are linked to a Railway project
if ! railway status >/dev/null 2>&1; then
  echo "❌ Not linked to a Railway project. Run:  railway link"
  exit 1
fi

echo "🚂 Applying $TIER env vars to Railway …"
set_count=0
skip_count=0

# Parse KEY=VALUE lines (ignore blanks, comments, values starting with '<')
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" != *"="* ]] && continue

  key="${line%%=*}"
  val="${line#*=}"
  key="$(echo "$key" | xargs)"
  val="$(echo "$val" | xargs)"

  if [[ -z "$val" || "$val" =~ ^\< ]]; then
    echo "  ⏭  skipping $key (empty / placeholder)"
    skip_count=$((skip_count+1))
    continue
  fi

  railway variables --set "${key}=${val}" >/dev/null
  echo "  ✔ set $key"
  set_count=$((set_count+1))
done < "$ENV_FILE"

echo ""
echo "✅ Done. $set_count variables applied, $skip_count skipped."
echo ""
echo "Next step: redeploy the service so the new variables take effect:"
echo "    railway up --detach    # or trigger a redeploy from the Railway dashboard"
