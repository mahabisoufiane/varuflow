# Portugal — preproduction

| Field | Value |
|-------|-------|
| ISO   | PT |
| Region | europe |
| Currency | EUR |
| VAT | 23.0% |
| Locale | pt-PT |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-pt)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://pt.varuflow.app
FRONTEND_URL=https://pt.varuflow.app
PORTAL_BASE_URL=https://pt.varuflow.app
DATABASE_URL=<tier-specific Postgres for PT>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-pt)
NEXT_PUBLIC_API_URL=https://api-pt-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=PT
NEXT_PUBLIC_DEFAULT_LOCALE=pt-PT
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
