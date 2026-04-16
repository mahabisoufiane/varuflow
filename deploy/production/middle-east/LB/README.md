# Lebanon — production

| Field | Value |
|-------|-------|
| ISO   | LB |
| Region | middle-east |
| Currency | LBP |
| VAT | 11.0% |
| Locale | ar-LB |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-lb)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://lb.varuflow.app
FRONTEND_URL=https://lb.varuflow.app
PORTAL_BASE_URL=https://lb.varuflow.app
DATABASE_URL=<tier-specific Postgres for LB>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-lb)
NEXT_PUBLIC_API_URL=https://api-lb-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=LB
NEXT_PUBLIC_DEFAULT_LOCALE=ar-LB
NEXT_PUBLIC_DEFAULT_CURRENCY=LBP
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
