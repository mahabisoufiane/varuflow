# Iceland — development

| Field | Value |
|-------|-------|
| ISO   | IS |
| Region | europe |
| Currency | ISK |
| VAT | 24.0% |
| Locale | is-IS |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-is)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://is.varuflow.app
FRONTEND_URL=https://is.varuflow.app
PORTAL_BASE_URL=https://is.varuflow.app
DATABASE_URL=<tier-specific Postgres for IS>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-is)
NEXT_PUBLIC_API_URL=https://api-is-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=IS
NEXT_PUBLIC_DEFAULT_LOCALE=is-IS
NEXT_PUBLIC_DEFAULT_CURRENCY=ISK
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
