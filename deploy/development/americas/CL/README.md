# Chile — development

| Field | Value |
|-------|-------|
| ISO   | CL |
| Region | americas |
| Currency | CLP |
| VAT | 19.0% |
| Locale | es-CL |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-cl)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://cl.varuflow.app
FRONTEND_URL=https://cl.varuflow.app
PORTAL_BASE_URL=https://cl.varuflow.app
DATABASE_URL=<tier-specific Postgres for CL>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-cl)
NEXT_PUBLIC_API_URL=https://api-cl-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CL
NEXT_PUBLIC_DEFAULT_LOCALE=es-CL
NEXT_PUBLIC_DEFAULT_CURRENCY=CLP
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
