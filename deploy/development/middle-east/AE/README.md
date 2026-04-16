# United Arab Emirates — development

| Field | Value |
|-------|-------|
| ISO   | AE |
| Region | middle-east |
| Currency | AED |
| VAT | 5.0% |
| Locale | ar-AE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-ae)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ae.varuflow.app
FRONTEND_URL=https://ae.varuflow.app
PORTAL_BASE_URL=https://ae.varuflow.app
DATABASE_URL=<tier-specific Postgres for AE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-ae)
NEXT_PUBLIC_API_URL=https://api-ae-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=AE
NEXT_PUBLIC_DEFAULT_LOCALE=ar-AE
NEXT_PUBLIC_DEFAULT_CURRENCY=AED
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
