# North Macedonia — production

| Field | Value |
|-------|-------|
| ISO   | MK |
| Region | europe |
| Currency | MKD |
| VAT | 18.0% |
| Locale | mk-MK |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-mk)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://mk.varuflow.app
FRONTEND_URL=https://mk.varuflow.app
PORTAL_BASE_URL=https://mk.varuflow.app
DATABASE_URL=<tier-specific Postgres for MK>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-mk)
NEXT_PUBLIC_API_URL=https://api-mk-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=MK
NEXT_PUBLIC_DEFAULT_LOCALE=mk-MK
NEXT_PUBLIC_DEFAULT_CURRENCY=MKD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
