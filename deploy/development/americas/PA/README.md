# Panama — development

| Field | Value |
|-------|-------|
| ISO   | PA |
| Region | americas |
| Currency | PAB |
| VAT | 7.0% |
| Locale | es-PA |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-pa)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://pa.varuflow.app
FRONTEND_URL=https://pa.varuflow.app
PORTAL_BASE_URL=https://pa.varuflow.app
DATABASE_URL=<tier-specific Postgres for PA>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-pa)
NEXT_PUBLIC_API_URL=https://api-pa-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=PA
NEXT_PUBLIC_DEFAULT_LOCALE=es-PA
NEXT_PUBLIC_DEFAULT_CURRENCY=PAB
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
