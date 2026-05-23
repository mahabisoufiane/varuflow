# Mexico — preproduction

| Field | Value |
|-------|-------|
| ISO   | MX |
| Region | americas |
| Currency | MXN |
| VAT | 16.0% |
| Locale | es-MX |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-mx)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://mx.varuflow.app
FRONTEND_URL=https://mx.varuflow.app
PORTAL_BASE_URL=https://mx.varuflow.app
DATABASE_URL=<tier-specific Postgres for MX>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-mx)
NEXT_PUBLIC_API_URL=https://api-mx-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=MX
NEXT_PUBLIC_DEFAULT_LOCALE=es-MX
NEXT_PUBLIC_DEFAULT_CURRENCY=MXN
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
