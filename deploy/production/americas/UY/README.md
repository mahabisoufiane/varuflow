# Uruguay — production

| Field | Value |
|-------|-------|
| ISO   | UY |
| Region | americas |
| Currency | UYU |
| VAT | 22.0% |
| Locale | es-UY |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-uy)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://uy.varuflow.app
FRONTEND_URL=https://uy.varuflow.app
PORTAL_BASE_URL=https://uy.varuflow.app
DATABASE_URL=<tier-specific Postgres for UY>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-uy)
NEXT_PUBLIC_API_URL=https://api-uy-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=UY
NEXT_PUBLIC_DEFAULT_LOCALE=es-UY
NEXT_PUBLIC_DEFAULT_CURRENCY=UYU
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
