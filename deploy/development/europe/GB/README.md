# United Kingdom — development

| Field | Value |
|-------|-------|
| ISO   | GB |
| Region | europe |
| Currency | GBP |
| VAT | 20.0% |
| Locale | en-GB |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-gb)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://gb.varuflow.app
FRONTEND_URL=https://gb.varuflow.app
PORTAL_BASE_URL=https://gb.varuflow.app
DATABASE_URL=<tier-specific Postgres for GB>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-gb)
NEXT_PUBLIC_API_URL=https://api-gb-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=GB
NEXT_PUBLIC_DEFAULT_LOCALE=en-GB
NEXT_PUBLIC_DEFAULT_CURRENCY=GBP
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
