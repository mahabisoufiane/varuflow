# Venezuela — preproduction

| Field | Value |
|-------|-------|
| ISO   | VE |
| Region | americas |
| Currency | VES |
| VAT | 16.0% |
| Locale | es-VE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ve)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ve.varuflow.app
FRONTEND_URL=https://ve.varuflow.app
PORTAL_BASE_URL=https://ve.varuflow.app
DATABASE_URL=<tier-specific Postgres for VE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ve)
NEXT_PUBLIC_API_URL=https://api-ve-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=VE
NEXT_PUBLIC_DEFAULT_LOCALE=es-VE
NEXT_PUBLIC_DEFAULT_CURRENCY=VES
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
