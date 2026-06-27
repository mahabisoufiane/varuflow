# Yemen — production

| Field | Value |
|-------|-------|
| ISO   | YE |
| Region | middle-east |
| Currency | YER |
| VAT | 5.0% |
| Locale | ar-YE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-ye)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ye.varuflow.app
FRONTEND_URL=https://ye.varuflow.app
PORTAL_BASE_URL=https://ye.varuflow.app
DATABASE_URL=<tier-specific Postgres for YE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-ye)
NEXT_PUBLIC_API_URL=https://api-ye-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=YE
NEXT_PUBLIC_DEFAULT_LOCALE=ar-YE
NEXT_PUBLIC_DEFAULT_CURRENCY=YER
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
