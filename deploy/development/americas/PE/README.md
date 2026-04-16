# Peru — development

| Field | Value |
|-------|-------|
| ISO   | PE |
| Region | americas |
| Currency | PEN |
| VAT | 18.0% |
| Locale | es-PE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-pe)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://pe.varuflow.app
FRONTEND_URL=https://pe.varuflow.app
PORTAL_BASE_URL=https://pe.varuflow.app
DATABASE_URL=<tier-specific Postgres for PE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-pe)
NEXT_PUBLIC_API_URL=https://api-pe-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=PE
NEXT_PUBLIC_DEFAULT_LOCALE=es-PE
NEXT_PUBLIC_DEFAULT_CURRENCY=PEN
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
