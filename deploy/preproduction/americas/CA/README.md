# Canada — preproduction

| Field | Value |
|-------|-------|
| ISO   | CA |
| Region | americas |
| Currency | CAD |
| VAT | 5.0% |
| Locale | en-CA |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ca)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ca.varuflow.app
FRONTEND_URL=https://ca.varuflow.app
PORTAL_BASE_URL=https://ca.varuflow.app
DATABASE_URL=<tier-specific Postgres for CA>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ca)
NEXT_PUBLIC_API_URL=https://api-ca-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CA
NEXT_PUBLIC_DEFAULT_LOCALE=en-CA
NEXT_PUBLIC_DEFAULT_CURRENCY=CAD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
