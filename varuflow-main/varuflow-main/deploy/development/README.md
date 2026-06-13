# Development deployments

This directory contains per-country deployment manifests for the **development** tier.

- `backend.env.example` — Railway env template for this tier
- `frontend.env.example` — Vercel env template for this tier
- `<region>/<country>/` — per-country overrides (domain, Stripe keys, DB URL)

Never commit real secrets. Use Railway / Vercel environment variables.
