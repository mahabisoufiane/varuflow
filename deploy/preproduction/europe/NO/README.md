# Norway — preproduction

| Field | Value |
|-------|-------|
| ISO   | NO |
| Region | europe |
| Currency | NOK |
| VAT | 25.0% |
| Locale | nb-NO |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-no)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://no.varuflow.app
FRONTEND_URL=https://no.varuflow.app
PORTAL_BASE_URL=https://no.varuflow.app
DATABASE_URL=<tier-specific Postgres for NO>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-no)
NEXT_PUBLIC_API_URL=https://api-no-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=NO
NEXT_PUBLIC_DEFAULT_LOCALE=nb-NO
NEXT_PUBLIC_DEFAULT_CURRENCY=NOK
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
