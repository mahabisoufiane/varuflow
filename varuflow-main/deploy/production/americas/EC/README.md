# Ecuador — production

| Field | Value |
|-------|-------|
| ISO   | EC |
| Region | americas |
| Currency | USD |
| VAT | 15.0% |
| Locale | es-EC |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-ec)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ec.varuflow.app
FRONTEND_URL=https://ec.varuflow.app
PORTAL_BASE_URL=https://ec.varuflow.app
DATABASE_URL=<tier-specific Postgres for EC>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-ec)
NEXT_PUBLIC_API_URL=https://api-ec-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=EC
NEXT_PUBLIC_DEFAULT_LOCALE=es-EC
NEXT_PUBLIC_DEFAULT_CURRENCY=USD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
