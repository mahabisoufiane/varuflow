# Moldova — development

| Field | Value |
|-------|-------|
| ISO   | MD |
| Region | europe |
| Currency | MDL |
| VAT | 20.0% |
| Locale | ro-MD |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-md)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://md.varuflow.app
FRONTEND_URL=https://md.varuflow.app
PORTAL_BASE_URL=https://md.varuflow.app
DATABASE_URL=<tier-specific Postgres for MD>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-md)
NEXT_PUBLIC_API_URL=https://api-md-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=MD
NEXT_PUBLIC_DEFAULT_LOCALE=ro-MD
NEXT_PUBLIC_DEFAULT_CURRENCY=MDL
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
