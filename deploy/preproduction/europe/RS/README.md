# Serbia — preproduction

| Field | Value |
|-------|-------|
| ISO   | RS |
| Region | europe |
| Currency | RSD |
| VAT | 20.0% |
| Locale | sr-RS |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-rs)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://rs.varuflow.app
FRONTEND_URL=https://rs.varuflow.app
PORTAL_BASE_URL=https://rs.varuflow.app
DATABASE_URL=<tier-specific Postgres for RS>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-rs)
NEXT_PUBLIC_API_URL=https://api-rs-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=RS
NEXT_PUBLIC_DEFAULT_LOCALE=sr-RS
NEXT_PUBLIC_DEFAULT_CURRENCY=RSD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
