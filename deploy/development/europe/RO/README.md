# Romania — development

| Field | Value |
|-------|-------|
| ISO   | RO |
| Region | europe |
| Currency | RON |
| VAT | 19.0% |
| Locale | ro-RO |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-ro)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ro.varuflow.app
FRONTEND_URL=https://ro.varuflow.app
PORTAL_BASE_URL=https://ro.varuflow.app
DATABASE_URL=<tier-specific Postgres for RO>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-ro)
NEXT_PUBLIC_API_URL=https://api-ro-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=RO
NEXT_PUBLIC_DEFAULT_LOCALE=ro-RO
NEXT_PUBLIC_DEFAULT_CURRENCY=RON
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
