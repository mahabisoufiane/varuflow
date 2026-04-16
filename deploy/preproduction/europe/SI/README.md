# Slovenia — preproduction

| Field | Value |
|-------|-------|
| ISO   | SI |
| Region | europe |
| Currency | EUR |
| VAT | 22.0% |
| Locale | sl-SI |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-si)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://si.varuflow.app
FRONTEND_URL=https://si.varuflow.app
PORTAL_BASE_URL=https://si.varuflow.app
DATABASE_URL=<tier-specific Postgres for SI>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-si)
NEXT_PUBLIC_API_URL=https://api-si-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=SI
NEXT_PUBLIC_DEFAULT_LOCALE=sl-SI
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
