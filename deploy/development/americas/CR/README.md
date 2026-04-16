# Costa Rica — development

| Field | Value |
|-------|-------|
| ISO   | CR |
| Region | americas |
| Currency | CRC |
| VAT | 13.0% |
| Locale | es-CR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-cr)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://cr.varuflow.app
FRONTEND_URL=https://cr.varuflow.app
PORTAL_BASE_URL=https://cr.varuflow.app
DATABASE_URL=<tier-specific Postgres for CR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-cr)
NEXT_PUBLIC_API_URL=https://api-cr-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CR
NEXT_PUBLIC_DEFAULT_LOCALE=es-CR
NEXT_PUBLIC_DEFAULT_CURRENCY=CRC
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
