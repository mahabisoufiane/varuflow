# Bahrain — production

| Field | Value |
|-------|-------|
| ISO   | BH |
| Region | middle-east |
| Currency | BHD |
| VAT | 10.0% |
| Locale | ar-BH |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-bh)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://bh.varuflow.app
FRONTEND_URL=https://bh.varuflow.app
PORTAL_BASE_URL=https://bh.varuflow.app
DATABASE_URL=<tier-specific Postgres for BH>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-bh)
NEXT_PUBLIC_API_URL=https://api-bh-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=BH
NEXT_PUBLIC_DEFAULT_LOCALE=ar-BH
NEXT_PUBLIC_DEFAULT_CURRENCY=BHD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
