# Ukraine — preproduction

| Field | Value |
|-------|-------|
| ISO   | UA |
| Region | europe |
| Currency | UAH |
| VAT | 20.0% |
| Locale | uk-UA |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ua)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ua.varuflow.app
FRONTEND_URL=https://ua.varuflow.app
PORTAL_BASE_URL=https://ua.varuflow.app
DATABASE_URL=<tier-specific Postgres for UA>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ua)
NEXT_PUBLIC_API_URL=https://api-ua-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=UA
NEXT_PUBLIC_DEFAULT_LOCALE=uk-UA
NEXT_PUBLIC_DEFAULT_CURRENCY=UAH
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
