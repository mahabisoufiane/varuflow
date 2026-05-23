# Jamaica — production

| Field | Value |
|-------|-------|
| ISO   | JM |
| Region | americas |
| Currency | JMD |
| VAT | 15.0% |
| Locale | en-JM |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-jm)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://jm.varuflow.app
FRONTEND_URL=https://jm.varuflow.app
PORTAL_BASE_URL=https://jm.varuflow.app
DATABASE_URL=<tier-specific Postgres for JM>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-jm)
NEXT_PUBLIC_API_URL=https://api-jm-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=JM
NEXT_PUBLIC_DEFAULT_LOCALE=en-JM
NEXT_PUBLIC_DEFAULT_CURRENCY=JMD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
