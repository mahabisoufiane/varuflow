# Argentina — preproduction

| Field | Value |
|-------|-------|
| ISO   | AR |
| Region | americas |
| Currency | ARS |
| VAT | 21.0% |
| Locale | es-AR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ar)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ar.varuflow.app
FRONTEND_URL=https://ar.varuflow.app
PORTAL_BASE_URL=https://ar.varuflow.app
DATABASE_URL=<tier-specific Postgres for AR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ar)
NEXT_PUBLIC_API_URL=https://api-ar-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=AR
NEXT_PUBLIC_DEFAULT_LOCALE=es-AR
NEXT_PUBLIC_DEFAULT_CURRENCY=ARS
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
