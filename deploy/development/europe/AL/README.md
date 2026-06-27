# Albania — development

| Field | Value |
|-------|-------|
| ISO   | AL |
| Region | europe |
| Currency | ALL |
| VAT | 20.0% |
| Locale | sq-AL |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-al)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://al.varuflow.app
FRONTEND_URL=https://al.varuflow.app
PORTAL_BASE_URL=https://al.varuflow.app
DATABASE_URL=<tier-specific Postgres for AL>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-al)
NEXT_PUBLIC_API_URL=https://api-al-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=AL
NEXT_PUBLIC_DEFAULT_LOCALE=sq-AL
NEXT_PUBLIC_DEFAULT_CURRENCY=ALL
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
