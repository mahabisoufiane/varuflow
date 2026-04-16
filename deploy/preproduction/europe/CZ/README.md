# Czechia — preproduction

| Field | Value |
|-------|-------|
| ISO   | CZ |
| Region | europe |
| Currency | CZK |
| VAT | 21.0% |
| Locale | cs-CZ |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-cz)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://cz.varuflow.app
FRONTEND_URL=https://cz.varuflow.app
PORTAL_BASE_URL=https://cz.varuflow.app
DATABASE_URL=<tier-specific Postgres for CZ>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-cz)
NEXT_PUBLIC_API_URL=https://api-cz-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CZ
NEXT_PUBLIC_DEFAULT_LOCALE=cs-CZ
NEXT_PUBLIC_DEFAULT_CURRENCY=CZK
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
