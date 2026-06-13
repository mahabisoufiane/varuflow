# Estonia — preproduction

| Field | Value |
|-------|-------|
| ISO   | EE |
| Region | europe |
| Currency | EUR |
| VAT | 22.0% |
| Locale | et-EE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ee)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ee.varuflow.app
FRONTEND_URL=https://ee.varuflow.app
PORTAL_BASE_URL=https://ee.varuflow.app
DATABASE_URL=<tier-specific Postgres for EE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ee)
NEXT_PUBLIC_API_URL=https://api-ee-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=EE
NEXT_PUBLIC_DEFAULT_LOCALE=et-EE
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
