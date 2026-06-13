# Paraguay — preproduction

| Field | Value |
|-------|-------|
| ISO   | PY |
| Region | americas |
| Currency | PYG |
| VAT | 10.0% |
| Locale | es-PY |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-py)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://py.varuflow.app
FRONTEND_URL=https://py.varuflow.app
PORTAL_BASE_URL=https://py.varuflow.app
DATABASE_URL=<tier-specific Postgres for PY>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-py)
NEXT_PUBLIC_API_URL=https://api-py-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=PY
NEXT_PUBLIC_DEFAULT_LOCALE=es-PY
NEXT_PUBLIC_DEFAULT_CURRENCY=PYG
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
