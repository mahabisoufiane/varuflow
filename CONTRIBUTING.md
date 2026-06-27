# Contributing to Varuflow

Thank you for contributing. This document covers the development workflow, code conventions, and review process.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Branch Strategy](#branch-strategy)
- [Commit Conventions](#commit-conventions)
- [Backend Conventions](#backend-conventions)
- [Frontend Conventions](#frontend-conventions)
- [Database Changes](#database-changes)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Code Review Checklist](#code-review-checklist)

---

## Development Setup

```bash
# Start all services
docker compose up -d

# Watch logs
docker compose logs -f

# Restart after env var changes (restart alone doesn't apply them)
docker compose up -d --force-recreate
```

If you get `Module not found: Can't resolve 'react-is'`:
```bash
docker volume rm varuflow_frontend_node_modules
docker compose up -d
```

Full instructions: [docs/local-development.md](../docs/local-development.md)

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production — deploys to Railway + Vercel automatically |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `chore/<name>` | Tooling, deps, docs |

- Branch from `main`
- Keep branches short-lived (merge within a week)
- Delete branches after merging

---

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>

[optional body]
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`

Examples:
```
feat(invoicing): add OCR number generation per BGC Luhn spec
fix(auth): remove stray NameError in get_current_user return dict
chore(deps): upgrade next-intl to 4.9.1
docs(fortnox): add bidirectional sync runbook
```

---

## Backend Conventions

### Every new endpoint must have:
1. Auth dependency — `user: dict = Depends(get_current_user)`
2. `org_id` filter on every DB query — users must never see another org's data
3. `try/except HTTPException: raise` + `except Exception` → 500
4. Structured log on error: `logger.error("...", extra={"org_id": ..., "user_id": ...})`
5. Input validation via Pydantic schema

### Auth dependency pattern:
```python
@router.get("/api/my-resource")
async def get_resource(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(MyModel).where(MyModel.org_id == user["org_id"])
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_resource failed: {e}", extra={"org_id": user["org_id"]})
        raise HTTPException(status_code=500, detail="Internal server error")
```

### HTTP status codes:
- `401` — unauthenticated (no/invalid token)
- `403` — authenticated but not authorized
- `404` — resource not found
- `422` — validation error (Pydantic handles automatically)
- `500` — unexpected error

### CORS: Never use `allow_origins=["*"]`. Read from `CORS_ORIGINS` env var.

---

## Frontend Conventions

### All API calls must go through `src/lib/api-client.ts`:
```typescript
try {
  const data = await apiClient.get('/api/endpoint')
  setData(data)
} catch (error) {
  if (error.status === 401) {
    router.push(`/${locale}/auth/login`)
  } else {
    toast.error('Something went wrong. Please try again.')
  }
}
```

### Never hardcode URLs:
```typescript
// Bad
fetch("https://varuflow-production.up.railway.app/api/...")
fetch("http://localhost:8000/api/...")

// Good
const BASE = process.env.NEXT_PUBLIC_API_URL ?? ""
```

### New pages must have translations in all 4 locale files:
- `frontend/messages/sv.json`
- `frontend/messages/en.json`
- `frontend/messages/no.json`
- `frontend/messages/da.json`

### Never import Supabase directly — use the lazy singleton:
```typescript
// Bad
import { createClient } from '@supabase/supabase-js'

// Good
import { supabase } from '@/lib/supabase/client'
```

---

## Database Changes

Every model change requires an Alembic migration:

```bash
cd backend

# Generate migration
alembic revision --autogenerate -m "add bankgiro to organizations"

# Review the generated file in migrations/versions/ before applying

# Apply
alembic upgrade head

# Verify
alembic current
```

Rules:
- Always review auto-generated migrations before applying — Alembic sometimes misses things
- New foreign key columns must have a DB-level index
- Never drop a column without a data backup step first
- Use soft deletes (`deleted_at`) on core entities — never hard delete customers, invoices, products

---

## Testing

```bash
# Backend tests
cd backend
pytest

# Frontend type check
cd frontend
npx tsc --noEmit

# Frontend lint
npx eslint src/
```

Before opening a PR, run:
```bash
# No hardcoded production URLs in frontend
grep -r "varuflow-production.up.railway.app" frontend/src
# → must return 0 results

# No wildcard CORS
grep -r 'allow_origins=\["*"\]' backend/
# → must return 0 results

# No secrets in code
grep -rn "sk_live\|sk_test\|whsec_\|re_[a-zA-Z]" backend/app/
# → must return 0 results
```

---

## Pull Request Process

1. Open a PR against `main`
2. Fill in the PR template — summary, test plan, screenshots for UI changes
3. Ensure CI passes (type check, lint, tests)
4. Request review from at least one other engineer
5. Squash-merge when approved

---

## Code Review Checklist

Reviewer must verify:

- [ ] Every new endpoint has auth dependency
- [ ] Every DB query filters by `org_id`
- [ ] No endpoint returns data from a different org
- [ ] `try/except` on every endpoint
- [ ] No stack traces in API responses
- [ ] No hardcoded URLs or secrets
- [ ] New env vars added to `.env.example` and documented
- [ ] New pages have translations in all 4 locale files
- [ ] New FK columns have indexes
- [ ] Alembic migration present for model changes
- [ ] CORSMiddleware is still first in `main.py` after backend changes

---

## Getting Help

- Check `CLAUDE.md` for project-specific rules (non-negotiable)
- Check `docs/` for feature and integration documentation
- Open an issue for bugs or questions
