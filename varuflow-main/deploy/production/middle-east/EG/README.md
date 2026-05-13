# Egypt — production

| Field | Value |
|-------|-------|
| ISO   | EG |
| Region | middle-east |
| Currency | EGP |
| VAT | 14.0% |
| Locale | ar-EG |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-eg)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://eg.varuflow.app
FRONTEND_URL=https://eg.varuflow.app
PORTAL_BASE_URL=https://eg.varuflow.app
DATABASE_URL=<tier-specific Postgres for EG>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-eg)
NEXT_PUBLIC_API_URL=https://api-eg-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=EG
NEXT_PUBLIC_DEFAULT_LOCALE=ar-EG
NEXT_PUBLIC_DEFAULT_CURRENCY=EGP
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
