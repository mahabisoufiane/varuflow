# Qatar — preproduction

| Field | Value |
|-------|-------|
| ISO   | QA |
| Region | middle-east |
| Currency | QAR |
| VAT | 0.0% |
| Locale | ar-QA |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-qa)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://qa.varuflow.app
FRONTEND_URL=https://qa.varuflow.app
PORTAL_BASE_URL=https://qa.varuflow.app
DATABASE_URL=<tier-specific Postgres for QA>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-qa)
NEXT_PUBLIC_API_URL=https://api-qa-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=QA
NEXT_PUBLIC_DEFAULT_LOCALE=ar-QA
NEXT_PUBLIC_DEFAULT_CURRENCY=QAR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
