#!/usr/bin/env bash
# scripts/set_missing_railway_secrets.sh
#
# Interactive CLI helper — prompts you for each currently-missing production
# secret and sets it on Railway via `railway variables --set`. Skips any
# variable you leave blank. Values are read from the terminal with -s (no
# echo) so they don't land in shell history or stdout.
#
# Usage:
#   bash scripts/set_missing_railway_secrets.sh
#
# The script uses --skip-deploys so nothing redeploys until you explicitly
# run:   railway redeploy
#
# Run `railway link` first if not already linked to the varuflow service.

set -euo pipefail

if ! command -v railway >/dev/null 2>&1; then
  echo "❌ railway CLI not found. Install: npm i -g @railway/cli"
  exit 1
fi

if ! railway status >/dev/null 2>&1; then
  echo "❌ Not linked. Run:  railway link --project varuflow --service varuflow"
  exit 1
fi

# name | human description (shown to user)
VARS=(
  "STRIPE_SECRET_KEY|Stripe secret key (sk_live_... or sk_test_...)"
  "STRIPE_WEBHOOK_SECRET|Stripe webhook signing secret (whsec_...)"
  "STRIPE_PRO_PRICE_ID|Stripe price ID for the Pro plan (price_...)"
  "RESEND_API_KEY|Resend API key (re_...)"
  "OPENAI_API_KEY|OpenAI API key (sk-...)"
  "FORTNOX_CLIENT_ID|Fortnox OAuth client ID"
  "FORTNOX_CLIENT_SECRET|Fortnox OAuth client secret"
  "FORTNOX_REDIRECT_URI|Fortnox redirect URI (https://.../api/integrations/fortnox/callback)"
  "SENTRY_DSN|Sentry DSN (optional — leave blank to skip)"
  "FRONTEND_URL|Frontend base URL (https://varuflow.vercel.app)"
  "SMTP_HOST|SMTP host (leave blank for dev-mode console output)"
  "SMTP_PORT|SMTP port (587 STARTTLS, 465 TLS)"
  "SMTP_USER|SMTP username"
  "SMTP_PASSWORD|SMTP password"
  "SMTP_FROM|From address (noreply@varuflow.se)"
)

existing="$(railway variables --service varuflow --kv 2>/dev/null | awk -F= '{print $1}')"

set_args=()
echo "You will be prompted for each missing secret. Leave blank to skip."
echo ""

for row in "${VARS[@]}"; do
  key="${row%%|*}"
  desc="${row#*|}"

  if echo "$existing" | grep -qx "$key"; then
    echo "  ⏭  $key already set on Railway — skipping"
    continue
  fi

  # -s hides input so the secret never appears in the terminal.
  printf "  %-24s %s\n    → " "$key" "$desc"
  read -rs value
  echo ""

  if [[ -z "$value" ]]; then
    echo "     (blank — skipped)"
    continue
  fi

  set_args+=(--set "${key}=${value}")
done

if [[ ${#set_args[@]} -eq 0 ]]; then
  echo ""
  echo "Nothing to set. Done."
  exit 0
fi

echo ""
echo "Applying $(( ${#set_args[@]} / 2 )) variables to Railway (no redeploy) …"
railway variables --service varuflow --skip-deploys "${set_args[@]}" >/dev/null
echo "✅ Done."
echo ""
echo "When you're ready to pick up the new values, redeploy:"
echo "    railway redeploy --service varuflow --yes"
