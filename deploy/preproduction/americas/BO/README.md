# Bolivia — preproduction

| Field | Value |
|-------|-------|
| ISO   | BO |
| Region | americas |
| Currency | BOB |
| VAT | 13.0% |
| Locale | es-BO |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-bo)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://bo.varuflow.app
FRONTEND_URL=https://bo.varuflow.app
PORTAL_BASE_URL=https://bo.varuflow.app
DATABASE_URL=<tier-specific Postgres for BO>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-bo)
NEXT_PUBLIC_API_URL=https://api-bo-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=BO
NEXT_PUBLIC_DEFAULT_LOCALE=es-BO
NEXT_PUBLIC_DEFAULT_CURRENCY=BOB
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
