# Cyprus — development

| Field | Value |
|-------|-------|
| ISO   | CY |
| Region | europe |
| Currency | EUR |
| VAT | 19.0% |
| Locale | el-CY |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-cy)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://cy.varuflow.app
FRONTEND_URL=https://cy.varuflow.app
PORTAL_BASE_URL=https://cy.varuflow.app
DATABASE_URL=<tier-specific Postgres for CY>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-cy)
NEXT_PUBLIC_API_URL=https://api-cy-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=CY
NEXT_PUBLIC_DEFAULT_LOCALE=el-CY
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
