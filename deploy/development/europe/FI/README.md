# Finland — development

| Field | Value |
|-------|-------|
| ISO   | FI |
| Region | europe |
| Currency | EUR |
| VAT | 25.5% |
| Locale | fi-FI |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-fi)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://fi.varuflow.app
FRONTEND_URL=https://fi.varuflow.app
PORTAL_BASE_URL=https://fi.varuflow.app
DATABASE_URL=<tier-specific Postgres for FI>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-fi)
NEXT_PUBLIC_API_URL=https://api-fi-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=FI
NEXT_PUBLIC_DEFAULT_LOCALE=fi-FI
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
