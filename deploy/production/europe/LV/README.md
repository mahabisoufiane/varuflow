# Latvia — production

| Field | Value |
|-------|-------|
| ISO   | LV |
| Region | europe |
| Currency | EUR |
| VAT | 21.0% |
| Locale | lv-LV |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-lv)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://lv.varuflow.app
FRONTEND_URL=https://lv.varuflow.app
PORTAL_BASE_URL=https://lv.varuflow.app
DATABASE_URL=<tier-specific Postgres for LV>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-lv)
NEXT_PUBLIC_API_URL=https://api-lv-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=LV
NEXT_PUBLIC_DEFAULT_LOCALE=lv-LV
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
