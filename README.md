# Varuflow

The operating system for Swedish wholesalers. Manage inventory, automate invoicing, and track cash flow — built for Swedish B2B businesses.

## Tech Stack

- **Backend:** Python 3.11 + FastAPI + PostgreSQL (async SQLAlchemy)
- **Frontend:** Next.js 14 (App Router) + Tailwind CSS + shadcn/ui
- **Auth:** Supabase Auth
- **Database:** Supabase (PostgreSQL)
- **Email:** Resend
- **i18n:** English + Swedish (next-intl)

## Quick Start

```bash
# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Start all services
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Health: http://localhost:8000/health

## Project Structure

```
varuflow/
├── frontend/    # Next.js 14
├── backend/     # FastAPI
└── docker-compose.yml
```
