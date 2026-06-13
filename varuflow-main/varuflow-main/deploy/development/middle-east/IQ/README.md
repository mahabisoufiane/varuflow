# Iraq — development

| Field | Value |
|-------|-------|
| ISO   | IQ |
| Region | middle-east |
| Currency | IQD |
| VAT | 0.0% |
| Locale | ar-IQ |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-iq)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://iq.varuflow.app
FRONTEND_URL=https://iq.varuflow.app
PORTAL_BASE_URL=https://iq.varuflow.app
DATABASE_URL=<tier-specific Postgres for IQ>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-iq)
NEXT_PUBLIC_API_URL=https://api-iq-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=IQ
NEXT_PUBLIC_DEFAULT_LOCALE=ar-IQ
NEXT_PUBLIC_DEFAULT_CURRENCY=IQD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
