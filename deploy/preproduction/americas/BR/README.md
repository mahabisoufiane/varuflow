# Brazil — preproduction

| Field | Value |
|-------|-------|
| ISO   | BR |
| Region | americas |
| Currency | BRL |
| VAT | 17.0% |
| Locale | pt-BR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-br)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://br.varuflow.app
FRONTEND_URL=https://br.varuflow.app
PORTAL_BASE_URL=https://br.varuflow.app
DATABASE_URL=<tier-specific Postgres for BR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-br)
NEXT_PUBLIC_API_URL=https://api-br-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=BR
NEXT_PUBLIC_DEFAULT_LOCALE=pt-BR
NEXT_PUBLIC_DEFAULT_CURRENCY=BRL
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
