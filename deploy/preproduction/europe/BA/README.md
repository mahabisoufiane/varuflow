# Bosnia — preproduction

| Field | Value |
|-------|-------|
| ISO   | BA |
| Region | europe |
| Currency | BAM |
| VAT | 17.0% |
| Locale | bs-BA |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ba)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ba.varuflow.app
FRONTEND_URL=https://ba.varuflow.app
PORTAL_BASE_URL=https://ba.varuflow.app
DATABASE_URL=<tier-specific Postgres for BA>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ba)
NEXT_PUBLIC_API_URL=https://api-ba-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=BA
NEXT_PUBLIC_DEFAULT_LOCALE=bs-BA
NEXT_PUBLIC_DEFAULT_CURRENCY=BAM
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
