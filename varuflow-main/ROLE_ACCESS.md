# ROLE_ACCESS.md — Role-within-module access control

Varuflow access has **three** dimensions. All three must agree.

| Dimension | Question | Where enforced |
|-----------|----------|----------------|
| **Plan** | Is this feature in the org's plan tier? | `require_plan` / `require_module` (backend) |
| **Module grant** | Is this member assigned this module? | `require_module` + `member_modules` table |
| **Role-within-module** | Is the member's role senior enough for *this* action? | `require_role` (backend) + `RoleGuard` / `minRole` (frontend) |

The third dimension is the one added in `feat(access)` — before it, having a
module meant seeing *all* of it.

## Role ladder

```
MEMBER  <  ADMIN  <  OWNER
```

| Role | Job function | Sees |
|------|-------------|------|
| `MEMBER` | regular employee | own data: own leave, own shifts, own timesheet, submit expenses/PRs |
| `ADMIN` | manager / dept head | team data: roster, approvals, reviews, dashboards, financials, payroll |
| `OWNER` | owner | everything + destructive actions (org erasure, GDPR export, billing) |

## How to gate a feature

**Backend** — add to the router (or a single endpoint):
```python
from app.middleware.plan_check import require_module, require_role
from app.models.organization import OrgRole

router = APIRouter(dependencies=[
    Depends(require_module("hr")),
    Depends(require_role(OrgRole.ADMIN)),   # manager-level whole router
])
```
For a mixed router (employees read, managers write), put `require_role` only on
the manager endpoints via `dependencies=[...]` on the route decorator.

**Frontend** — mirror it so the page can't be reached by direct URL:
```tsx
import { RoleGuard } from "@/components/app/RoleContext";

export default function Page() {
  return <RoleGuard minRole="ADMIN"><PageInner /></RoleGuard>;
}
```
And tag the sidebar item with `minRole` in `AppShell.tsx` so the link hides.

> The frontend guard is UX; the **backend `require_role` is the security
> boundary**. Always add the backend guard — never rely on hiding the link.

## Rollout status

### ✅ Enforced (backend + frontend)
| Area | Router | minRole | Why |
|------|--------|---------|-----|
| Employee profiles / contracts / emergency contacts | `hr_employees` (per-route) | ADMIN | decrypted national_id + bank_account, contracts |
| Payroll runs (salaries) | `payroll` | ADMIN | salary data; GET handlers were previously unguarded |
| Ledger | `accounting` | ADMIN | manager-level finance |
| VAT returns | `vat_return` | ADMIN | manager-level finance |
| Bank feed / balances | `bank_feed` | ADMIN | sensitive bank data |
| Budgets | `budget` | ADMIN | manager planning data |
| Reconciliation | `reconciliation` | ADMIN | manager finance task |
| CEO dashboards | `ceo_dashboard` | ADMIN | company-wide KPIs |
| Roster / overtime / swap approvals | `scheduling` | ADMIN | members view own shifts via self-service `/api/shifts` |
| Org chart | `hr_org_chart` | ADMIN | reporting lines |

> **Important nuance — `hr_employees` is gated per-route, NOT at the router
> level.** The plain employee **list** (`GET /api/hr/employees`) stays open to
> any HR-module member because the self-service `/hr/shifts` and `/hr/leave`
> pages need it to show colleague names. Only the sensitive sub-resources
> (profiles with PII, contracts, emergency contacts) require ADMIN. Gating the
> whole router would 403 a member viewing their own shifts.

### ✅ Open to all members (self-service — correct as-is)
`/hr/leave`, `/hr/shifts`, `/hr/timesheets` (own data), `/expenses`,
`/purchase-requests` (submit), `/dashboard`, `/invoices`, `/customers`,
`/inventory`, `/pos`.

Decision (2026): Nordic SMBs push bookkeeping to an *external* accountant
(Fortnox/Visma sync + accountant-forwarding exist for this). An in-house person
touching ledger/VAT/bank/budget is a finance manager → give them the **ADMIN**
role. True MEMBERs (cashier, warehouse, field tech) never see financials. All
finance/HR manager routers above are therefore enforced at ADMIN.

### ✅ Enforced (per-endpoint, inside member-open routers)
These routers stay open to members for self-service, but the *approval* action
is ADMIN-gated via `dependencies=_MANAGER_ONLY` on the route:

| Endpoint | Router | minRole |
|----------|--------|---------|
| `POST /api/hr/leave/{id}/approve` · `/reject` | `hr_leave` | ADMIN |
| `POST /api/purchase-requests/{id}/approve` · `/reject` | `purchase_requests` | ADMIN |

Requesting/submitting and viewing one's own items stays open to MEMBER.

### 🔲 Still to review
| Area | Router | Proposed | Note |
|------|--------|----------|------|
| `/governance/*` | governance | ADMIN/OWNER | approvals, policy docs |
| `/admin/*` | admin | OWNER | already uses X-Admin-Key on some routes — audit role coverage |
| Expense report approval | `expense_reports` | ADMIN | already has ad-hoc `_require_owner_or_admin`; migrate to `require_role` |

## Where roles come from

`/api/auth/me` returns `role`. The frontend `RoleProvider` fetches it once and
shares it via `useRole()`. Keep `lib/roles.ts` `ROLE_RANK` in sync with
`plan_check._ROLE_RANK`.
