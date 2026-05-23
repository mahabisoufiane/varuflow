# Greece — production

| Field | Value |
|-------|-------|
| ISO   | GR |
| Region | europe |
| Currency | EUR |
| VAT | 24.0% |
| Locale | el-GR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-gr)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://gr.varuflow.app
FRONTEND_URL=https://gr.varuflow.app
PORTAL_BASE_URL=https://gr.varuflow.app
DATABASE_URL=<tier-specific Postgres for GR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-gr)
NEXT_PUBLIC_API_URL=https://api-gr-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=GR
NEXT_PUBLIC_DEFAULT_LOCALE=el-GR
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
