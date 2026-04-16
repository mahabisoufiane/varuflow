# Israel — preproduction

| Field | Value |
|-------|-------|
| ISO   | IL |
| Region | middle-east |
| Currency | ILS |
| VAT | 18.0% |
| Locale | he-IL |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-il)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://il.varuflow.app
FRONTEND_URL=https://il.varuflow.app
PORTAL_BASE_URL=https://il.varuflow.app
DATABASE_URL=<tier-specific Postgres for IL>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-il)
NEXT_PUBLIC_API_URL=https://api-il-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=IL
NEXT_PUBLIC_DEFAULT_LOCALE=he-IL
NEXT_PUBLIC_DEFAULT_CURRENCY=ILS
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
