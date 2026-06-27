# United States — production

| Field | Value |
|-------|-------|
| ISO   | US |
| Region | americas |
| Currency | USD |
| VAT | 0.0% |
| Locale | en-US |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-us)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://us.varuflow.app
FRONTEND_URL=https://us.varuflow.app
PORTAL_BASE_URL=https://us.varuflow.app
DATABASE_URL=<tier-specific Postgres for US>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-us)
NEXT_PUBLIC_API_URL=https://api-us-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=US
NEXT_PUBLIC_DEFAULT_LOCALE=en-US
NEXT_PUBLIC_DEFAULT_CURRENCY=USD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
