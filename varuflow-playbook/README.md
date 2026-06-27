# Varuflow SaaS Playbook

A step-by-step playbook for building, launching, and growing Varuflow from idea to revenue. Each file maps to a stage of the SaaS journey. Since the product already exists, use this as a living checklist — check off what is done, and treat the rest as your active roadmap.

## Directory

| File | Stage | Focus |
|------|-------|-------|
| 00-10-problem-statement.md | 0 → 10 | Problem, user, outcome |
| 10-30-discovery.md | 10 → 30 | User research, feature list |
| 30-60-mvp-build.md | 30 → 60 | Core build checklist |
| 60-80-monetization.md | 60 → 80 | Pricing, Stripe, checkout |
| 80-100-growth.md | 80 → 100 | Retention, churn, activation |
| 30-day-roadmap.md | Now | Concrete week-by-week plan |
| decisions/ADR-001-stack.md | Reference | Why this stack was chosen |

## Stack

- **Frontend:** Next.js 16, TypeScript, Tailwind CSS, next-intl
- **Backend:** FastAPI (Python 3.12), port 8000
- **Auth:** Supabase (magic link + password)
- **Database:** Supabase Postgres
- **Infra:** Docker Compose, self-hosted on ESXi
- **Integrations:** Fortnox (ERP/accounting)

## How to use this playbook

1. Read each file in order.
2. Mark items `[x]` as you complete them.
3. Update `30-day-roadmap.md` weekly.
4. Add new ADRs to `decisions/` whenever you make a significant technical or product choice.
