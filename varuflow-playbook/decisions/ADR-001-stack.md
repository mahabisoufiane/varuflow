# ADR-001: Technology Stack Selection

- **Date:** 2026-04
- **Status:** Accepted
- **Decided by:** Varuflow founding team

---

## Context

Varuflow needs a stack that:

- Can be built by a small team (1–2 developers)
- Is self-hostable on ESXi infrastructure already available
- Supports rapid iteration without sacrificing type safety
- Has a clear path to production without vendor lock-in

---

## Decisions

### Frontend: Next.js 16 (App Router) + TypeScript + Tailwind CSS

**Why Next.js over a pure React SPA:**
- Server Components reduce client bundle size and improve initial load
- App Router enables per-page auth middleware natively
- next-intl integrates cleanly for Swedish/English i18n
- Vercel-compatible for future hosting flexibility

**Why TypeScript:**
- Catches API contract mismatches at compile time
- Supabase generates typed client from schema
- Reduces runtime errors in production

**Why Tailwind:**
- Fast to prototype, consistent design system via tokens
- No CSS-in-JS overhead
- Works well with shadcn/ui component library

### Backend: FastAPI (Python 3.12)

**Why FastAPI over Django REST Framework:**
- Automatic OpenAPI docs at `/docs`
- Async by default — needed for Fortnox API polling
- Pydantic v2 for request/response validation
- Lighter weight for a focused API (not a monolith)

**Why Python over Node.js:**
- Team expertise (Python automation background)
- Superior data processing libraries (pandas for future analytics)
- Poetry for reliable dependency management

### Auth: Supabase

**Why Supabase over custom JWT auth:**
- Magic link + password out of the box
- Row Level Security (RLS) built into Postgres
- SSR-compatible client (`@supabase/ssr`)
- Can be self-hosted (Docker) alongside the app

### Database: Supabase Postgres

**Why Postgres over MongoDB or MySQL:**
- Strong relational model for inventory (products → transactions → stock levels)
- JSON columns available for Fortnox webhook payloads
- RLS for multi-tenant security without application-level filtering
- Supabase migrations for schema versioning

### Infrastructure: Docker Compose on VMware ESXi

**Why self-hosted over cloud PaaS:**
- Zero infrastructure cost (ESXi already available)
- Full control over data — important for Fortnox financial data
- No Vercel/Railway/Render pricing surprises at scale
- Familiar Linux administration environment

**Trade-offs accepted:**
- Manual SSL certificate management (Caddy or nginx with Let's Encrypt)
- No auto-scaling (acceptable for early-stage SaaS under 1000 users)
- Backup responsibility falls on the team (automated via cron + rclone to S3)

---

## Alternatives Considered

| Option | Rejected because |
|--------|-----------------|
| Nuxt.js (Vue) | Team has no Vue experience |
| Django + HTMX | No TypeScript, harder to build interactive UI |
| Supabase cloud only | Want self-hosted option for data residency |
| PlanetScale (MySQL) | Less mature RLS, Fortnox data needs Postgres JSON support |
| Railway/Render hosting | Monthly cost adds up before revenue; ESXi already paid for |
