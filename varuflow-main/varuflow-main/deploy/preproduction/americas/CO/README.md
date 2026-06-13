# Colombia — preproduction

| Field | Value |
|-------|-------|
| ISO   | CO |
| Region | americas |
| Currency | COP |
| VAT | 19.0% |
| Locale | es-CO |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-co)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://co.varuflow.app
FRONTEND_URL=https://co.varuflow.app
PORTAL_BASE_URL=https://co.varuflow.app
DATABASE_URL=<tier-specific Postgres for CO>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-co)
NEXT_PUBLIC_API_URL=https://api-co-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CO
NEXT_PUBLIC_DEFAULT_LOCALE=es-CO
NEXT_PUBLIC_DEFAULT_CURRENCY=COP
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
