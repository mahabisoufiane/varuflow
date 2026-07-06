# Fortnox Gap Analysis — Phase 1C (read-only audit)

Audited 2026-07-06 against the four Fortnox-grade criteria groups. Five screens:
Dashboard, Invoice list, Invoice create, Invoice detail, Inventory (products)
list, Customer list. Effort: **S** < 1 h · **M** 1–3 h · **L** > 3 h.
No fixes applied — this is the Phase 2 backlog, one priority tier per batch.

Context that shaped findings: Invoice/Products/Customers lists were recently
migrated to the shared `ContentPanel` (shadcn Table + detail Sheet), which
gives them skeletons + selection for free — most list-level gaps concentrate
in the Dashboard and in cross-cutting patterns, not per-screen one-offs.

---

## Screen 1 — Dashboard (`src/app/[locale]/(app)/dashboard/page.tsx`, 583 lines)

| Criterion | Status |
|---|---|
| Density & hierarchy | Mixed — KPI cards fine; **6 accent-colored elements** compete (should be ≤1 primary action) |
| States | Loading: partial (2 local skeletons, not full-page). Empty: partial (4 `length===0` branches). **Error: none — impossible by construction** |
| Feedback | n/a (read-only screen) — but silent failure is worse than an error |
| Forms | n/a |

**Findings**
- **P0 · M** — All four data fetches swallow errors (`api.get(...).catch(() => [])`, lines 125–128). If the backend is down, the dashboard renders **zeros that look like real business data**. A wholesaler glancing at "0 kr outstanding" must never mean "the API failed". Needs an error banner + per-widget error state. `dashboard/page.tsx:125-128`
- **P1 · S** — 6 accent-colored elements on one screen; demote quick links to ghost/secondary so the single primary action stands out. `dashboard/page.tsx`
- **P2 · S** — Skeleton coverage is partial; the KPI strip pops in. Extend the existing local `skeleton` helper to all widgets. `dashboard/page.tsx:56`

## Screen 2 — Invoice list (`invoices/page.tsx`, 277 lines)

| Criterion | Status |
|---|---|
| Density & hierarchy | Good — KPI strip, filter tabs, one accent CTA in header ✓, Amount right-aligned ✓ |
| States | Skeleton ✓ (ContentPanel) · EmptyState with CTA ✓ · error → toast ✓ |
| Feedback | ✓ toasts on send/mark-paid/flag-overdue; buttons disabled while updating |
| Forms | n/a (create lives on its own screen) |

**Findings**
- **P1 · M (cross-cutting)** — Table rows are ~52 px (`ui/table.tsx` `h-12` headers + `p-4` cells). Fortnox uses ~34 px. Add a `dense` variant to the shared Table/ContentPanel and default list screens to it — one change fixes Invoices, Products, Customers, Quotes, Suppliers, POs at once. `src/components/ui/table.tsx:76`, `src/components/console/ContentPanel.tsx`
- **P2 · S** — When the detail Sheet is open, its "Send" button is a second visible accent action; make the row-level context win (sheet primary, header CTA stays). `invoices/page.tsx`

## Screen 3 — Invoice create (`invoices/new/page.tsx`, 307 lines)

| Criterion | Status |
|---|---|
| Density & hierarchy | OK — single submit action (but **off-token navy `#1a2332`**) |
| States | **No loading state for the customers fetch** — the select renders empty then pops |
| Feedback | Errors shown inline (line 296) ✓ · success = navigation (acceptable) |
| Forms | HTML `required` ×7 ✓ · focus rings ×10 ✓ · submit disabled-while-saving ✓ |

**Findings**
- **P1 · S** — Submit button uses hardcoded `bg-[#1a2332]` — invisible to theming and off the approved accent. Swap to `vf-btn`. `invoices/new/page.tsx:300` *(same navy family appears on quotes/new, products/new, suppliers, warehouses, POs — fold into token batch 1B-4)*
- **P1 · S** — No pending state while customers load; disable the select + show a subtle skeleton until the fetch resolves. `invoices/new/page.tsx:50-55`
- **P2 · S** — Validation is submit-time only (HTML `required`); add inline "field required" hints on blur for the two fields users actually miss (customer, due date). `invoices/new/page.tsx:101-125`

## Screen 4 — Invoice detail (`invoices/[id]/page.tsx`, 402 lines)

| Criterion | Status |
|---|---|
| Density & hierarchy | Good — line-item table right-aligns all numerics (×18) ✓ |
| States | Loading pulse ✓ (line 154) · not-found message ✓ (line 160) · inline error banners ✓ |
| Feedback | Mutations disable buttons ✓ — but **no toasts**; success feedback is a bare `sendMsg` string |
| Forms | Payment form: disabled-while-paying ✓, focus rings ×4 ✓ |

**Findings**
- **P1 · S** — Feedback pattern diverges from the rest of the app: list screens toast, this screen sets inline strings (`sendMsg`, error divs at 250/390). Standardize on sonner toasts for mutation outcomes; keep inline only for field-level validation. `invoices/[id]/page.tsx:104-110,250,390`
- **P2 · S** — Not-found state is a bare red `<p>`; use the EmptyState component with a "Back to invoices" CTA. `invoices/[id]/page.tsx:160`

## Screen 5 — Inventory / Products list (`inventory/products/page.tsx`, 331 lines)

| Criterion | Status |
|---|---|
| Density & hierarchy | Good — Buy/Sell/Margin right-aligned ✓, KPI strip, search; **accent CTA is off-token navy `#0d1117`** |
| States | Skeleton ✓ (ContentPanel) · custom empty with CTA ✓ · errors → toast ✓ |
| Feedback | ✓ CSV import + actions toast (×10) |
| Forms | (create is its own screen — same navy/token findings as invoices/new) |

**Findings**
- **P1 · S** — "New product" / "Import CSV" use hardcoded `#0d1117` navy instead of the accent tokens. `inventory/products/page.tsx:210-215` *(1B-4 scope)*
- **P2 · S** — Search filters client-side over the first 100 rows while the API supports `?search=` — wire the input to the server query (debounced) so catalogs > 100 products search correctly. `inventory/products/page.tsx:91-96,180-183`

## Screen 6 — Customer list (`customers/page.tsx`, 336 lines)

| Criterion | Status |
|---|---|
| Density & hierarchy | Good — one accent CTA ✓; Terms column left-aligned (minor) |
| States | Skeleton ✓ (ContentPanel) · EmptyState with CTA ✓ · errors → toast ✓ |
| Feedback | ✓ create/update toast; save button disabled-while-saving ✓ |
| Forms | `required` ×10 ✓ · `vf-input` focus rings ✓ (from the shared primitive) |

**Findings**
- **P2 · S** — "Net 30d" terms column reads as data; right-align it with the numerics convention. `customers/page.tsx`
- **P2 · S** — Dialog validation is submit-time HTML only; org-number format (`556xxx-xxxx`) is never validated client-side though the backend rejects bad ones. Add a pattern hint. `customers/page.tsx:116-135`

---

## Ranked backlog (Phase 2 batches = one tier at a time)

| # | Pri | Effort | Finding | File |
|---|-----|--------|---------|------|
| 1 | **P0** | M | Dashboard swallows all fetch errors → renders fake zeros | `dashboard/page.tsx:125-128` |
| 2 | P1 | M | Table density ~52px → add shared `dense` variant (~34px), fixes 6 list screens at once | `ui/table.tsx:76`, `console/ContentPanel.tsx` |
| 3 | P1 | S | Off-token navy CTAs (`#1a2332`/`#0d1117`) on create/list screens → `vf-btn` | `invoices/new:300`, `products:210` +4 siblings |
| 4 | P1 | S | Dashboard: 6 accent elements → 1 primary, rest ghost | `dashboard/page.tsx` |
| 5 | P1 | S | Invoice detail: inline-string feedback → standard toasts | `invoices/[id]:104,250,390` |
| 6 | P1 | S | Invoice create: no pending state on customers fetch | `invoices/new:50-55` |
| 7 | P2 | S | Detail-sheet double-accent when open | `invoices/page.tsx` |
| 8 | P2 | S | Not-found → EmptyState + CTA | `invoices/[id]:160` |
| 9 | P2 | S | Products search: client-side over 100 rows → server `?search=` | `products:91,180` |
| 10 | P2 | S | Customers: terms alignment + org-number pattern hint | `customers/page.tsx` |
| 11 | P2 | S | Dashboard skeleton coverage | `dashboard/page.tsx:56` |
| 12 | P2 | S | Invoice create: inline validation on blur | `invoices/new:101` |

## Gate 1C status
- [x] All 5 screens (6 files — invoice detail & create audited separately) have entries for all four criteria groups
- [x] Every finding has a priority, an effort estimate, and a file:line reference
- [ ] **STOPPED — fixes are Phase 2, one tier per batch, starting with the single P0**
