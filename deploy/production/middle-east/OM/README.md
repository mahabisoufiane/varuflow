# Oman — production

| Field | Value |
|-------|-------|
| ISO   | OM |
| Region | middle-east |
| Currency | OMR |
| VAT | 5.0% |
| Locale | ar-OM |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-om)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://om.varuflow.app
FRONTEND_URL=https://om.varuflow.app
PORTAL_BASE_URL=https://om.varuflow.app
DATABASE_URL=<tier-specific Postgres for OM>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-om)
NEXT_PUBLIC_API_URL=https://api-om-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=OM
NEXT_PUBLIC_DEFAULT_LOCALE=ar-OM
NEXT_PUBLIC_DEFAULT_CURRENCY=OMR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
