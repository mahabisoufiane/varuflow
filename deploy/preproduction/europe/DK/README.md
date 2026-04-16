# Denmark — preproduction

| Field | Value |
|-------|-------|
| ISO   | DK |
| Region | europe |
| Currency | DKK |
| VAT | 25.0% |
| Locale | da-DK |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-dk)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://dk.varuflow.app
FRONTEND_URL=https://dk.varuflow.app
PORTAL_BASE_URL=https://dk.varuflow.app
DATABASE_URL=<tier-specific Postgres for DK>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-dk)
NEXT_PUBLIC_API_URL=https://api-dk-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=DK
NEXT_PUBLIC_DEFAULT_LOCALE=da-DK
NEXT_PUBLIC_DEFAULT_CURRENCY=DKK
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
