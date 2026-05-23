# Varuflow

The operating system for Nordic wholesalers. Manage inventory, automate invoicing, track cash flow, and run your B2B business — built for Swedish, Norwegian, and Danish wholesale companies.

**Live:** https://varuflow.vercel.app  
**API:** https://varuflow-production.up.railway.app  
**API Docs:** https://varuflow-production.up.railway.app/docs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (App Router, Turbopack), TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI (Python 3.11+), SQLAlchemy (async), Alembic |
| Database | PostgreSQL 16 |
| Auth | Supabase Auth (production) + BankID (Swedish e-ID) |
| Hosting | Vercel (frontend) + Railway (backend) |
| Payments | Stripe (SaaS billing + invoice payment links) |
| Email | Resend |
| Accounting | Fortnox (SE), SIE4 export, Peppol BIS 3.0, EHF 3.0 (NO) |
| i18n | next-intl — Swedish (sv), English (en), Norwegian (no), Danish (da) |

---

## Features

- **Invoicing** — Create, send, and track invoices. PDF generation, OCR numbers (BGC), Peppol e-faktura, dunning automation (4 stages)
- **Inventory** — Stock management, purchase orders, warehouses, auto-reorder, stock counts, product variants
- **Customers** — CRM, B2B customer portal (magic link / OTP), loyalty, segments, campaigns
- **POS** — Point-of-sale with Swish, card, and cash. Z-reports, receipts, gift cards
- **Analytics** — Revenue, cash flow, forecasting, commissions, expense tracking
- **AI Engine** — Rules-based action cards, overdue alerts, restock signals, GPT-4o chat assistant
- **Integrations** — Fortnox OAuth sync, Bolagsverket company lookup, BankID e-ID
- **Compliance** — Swedish VAT (moms) 25%/12%/6%, Norwegian MVA, Danish moms, intra-EU reverse charge, SIE4 accounting export

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Local Development](docs/local-development.md) | Run the full stack locally with Docker |
| [Deployment](docs/deployment.md) | Deploy to Railway + Vercel |
| [Architecture](docs/architecture.md) | System design and data flow |
| [API Reference](docs/api.md) | Backend API overview |
| [Fortnox Integration](docs/integrations/fortnox.md) | Swedish accounting sync |
| [BankID Integration](docs/integrations/bankid.md) | Swedish e-ID setup |
| [Stripe Setup](docs/integrations/stripe.md) | Billing and payment links |
| [Peppol / E-faktura](docs/integrations/peppol.md) | Electronic invoicing (SE/NO) |
| [Swish Integration](docs/integrations/swish.md) | Swish Merchant API |
| [Swedish Invoice Requirements](docs/features/invoicing.md) | OCR, Bankgiro, legal requirements |
| [B2B Customer Portal](docs/features/portal.md) | Portal for wholesale customers |
| [Security Hardening](docs/operations/security-hardening.md) | Production security runbook |
| [Backup & Restore](docs/operations/backup-and-restore.md) | Database backup procedures |
| [Audit & Logging](docs/operations/audit-and-logging.md) | Observability and audit trail |
| [Security Policy](SECURITY.md) | Vulnerability reporting |
| [Contributing](CONTRIBUTING.md) | Dev workflow and conventions |
| [Changelog](CHANGELOG.md) | Release history |

---

## Quick Start (Local)

```bash
# 1. Start Docker Desktop (Windows/Mac) or Docker daemon (Linux)

# 2. Clone and start all services
git clone https://github.com/your-org/varuflow.git
cd varuflow
docker compose up -d

# 3. Open the app — no login required in dev mode
open http://localhost:3000
```

Services started:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Supabase (GoTrue) | http://localhost:9999 |
| n8n automation | http://localhost:5678 |
| PostgreSQL | localhost:5432 |

Full setup guide with troubleshooting: [docs/local-development.md](docs/local-development.md)

---

## Monorepo Layout

```
varuflow/
├── frontend/                  # Next.js 16 app
│   ├── src/
│   │   ├── app/               # App Router pages
│   │   │   ├── [locale]/      # Locale-prefixed routes (sv/en)
│   │   │   │   ├── (app)/     # Authenticated app routes
│   │   │   │   ├── (marketing)/
│   │   │   │   └── auth/
│   │   │   ├── portal/        # B2B customer portal
│   │   │   └── supplier-portal/
│   │   ├── components/
│   │   ├── lib/               # API client, Supabase helpers
│   │   └── i18n/              # next-intl routing config
│   └── messages/              # sv.json, en.json, no.json, da.json
│
├── backend/                   # FastAPI app
│   ├── app/
│   │   ├── routers/           # 86 endpoint modules
│   │   ├── models/            # 73 SQLAlchemy models
│   │   ├── services/          # 99 service modules
│   │   ├── middleware/        # Auth, CORS, rate limiting, readonly
│   │   └── config.py          # Settings (validates production secrets at startup)
│   └── migrations/            # 94 Alembic migration files
│
├── docs/                      # Project documentation
│   ├── integrations/          # Third-party integration guides
│   ├── features/              # Feature documentation
│   ├── operations/            # DevOps and security runbooks
│   └── legal/                 # Per-country VAT/legal requirements
│
└── docker-compose.yml         # Local full-stack dev environment
```

---

## Environment Variables

**Backend** — copy `backend/.env.example` → `backend/.env`  
**Frontend** — copy `frontend/.env.local.example` → `frontend/.env.local`

Production variables are managed in Railway (backend) and Vercel (frontend).  
See [docs/deployment.md](docs/deployment.md) for the full list.

---

## License

Proprietary — © Varuflow AB. All rights reserved.
