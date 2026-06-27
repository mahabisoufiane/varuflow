# Saudi Arabia — development

| Field | Value |
|-------|-------|
| ISO   | SA |
| Region | middle-east |
| Currency | SAR |
| VAT | 15.0% |
| Locale | ar-SA |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-sa)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://sa.varuflow.app
FRONTEND_URL=https://sa.varuflow.app
PORTAL_BASE_URL=https://sa.varuflow.app
DATABASE_URL=<tier-specific Postgres for SA>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-sa)
NEXT_PUBLIC_API_URL=https://api-sa-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=SA
NEXT_PUBLIC_DEFAULT_LOCALE=ar-SA
NEXT_PUBLIC_DEFAULT_CURRENCY=SAR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
