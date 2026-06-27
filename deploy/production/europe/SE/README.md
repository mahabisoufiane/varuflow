# Sweden — production

| Field | Value |
|-------|-------|
| ISO   | SE |
| Region | europe |
| Currency | SEK |
| VAT | 25.0% |
| Locale | sv-SE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-se)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://se.varuflow.app
FRONTEND_URL=https://se.varuflow.app
PORTAL_BASE_URL=https://se.varuflow.app
DATABASE_URL=<tier-specific Postgres for SE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-se)
NEXT_PUBLIC_API_URL=https://api-se-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=SE
NEXT_PUBLIC_DEFAULT_LOCALE=sv-SE
NEXT_PUBLIC_DEFAULT_CURRENCY=SEK
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
