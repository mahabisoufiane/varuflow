# Guatemala — production

| Field | Value |
|-------|-------|
| ISO   | GT |
| Region | americas |
| Currency | GTQ |
| VAT | 12.0% |
| Locale | es-GT |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-gt)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://gt.varuflow.app
FRONTEND_URL=https://gt.varuflow.app
PORTAL_BASE_URL=https://gt.varuflow.app
DATABASE_URL=<tier-specific Postgres for GT>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-gt)
NEXT_PUBLIC_API_URL=https://api-gt-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=GT
NEXT_PUBLIC_DEFAULT_LOCALE=es-GT
NEXT_PUBLIC_DEFAULT_CURRENCY=GTQ
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
