# Switzerland — preproduction

| Field | Value |
|-------|-------|
| ISO   | CH |
| Region | europe |
| Currency | CHF |
| VAT | 8.1% |
| Locale | de-CH |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ch)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ch.varuflow.app
FRONTEND_URL=https://ch.varuflow.app
PORTAL_BASE_URL=https://ch.varuflow.app
DATABASE_URL=<tier-specific Postgres for CH>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ch)
NEXT_PUBLIC_API_URL=https://api-ch-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CH
NEXT_PUBLIC_DEFAULT_LOCALE=de-CH
NEXT_PUBLIC_DEFAULT_CURRENCY=CHF
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
