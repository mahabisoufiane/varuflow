# CONVENTIONS.md — Code organization

How we keep files small and feature-scoped. When a module grows past ~500–600
lines, split it into a **package** (a directory) rather than letting it become a
monolith. The golden rule for the backend: **the public import path must not
change**, so `main.py`, other modules, and tests keep working untouched.

---

## Backend: large router → feature package

A single big `app/routers/<feature>.py` becomes `app/routers/<feature>/`:

```
routers/invoicing/                 # ← reference example (was invoicing.py, 1857 lines)
  __init__.py        # builds the public `router`; re-exports anything other
                     #   modules import from the package
  _shared.py         # helpers/constants/serializers shared by the route modules
  customers.py       # APIRouter() with one slice of the routes
  invoices.py
  payments.py
  payment_links.py
```

Rules:
1. **`__init__.py` rebuilds the public `router`** with the *exact* same
   `prefix=`, `tags=`, and `dependencies=[…]` the original had, then
   `router.include_router(<sub>)` for each route module. Mounted paths stay
   byte-identical — verify with the route snapshot (see Verification).
2. **Sub-route modules** declare a plain `router = APIRouter()` (no prefix) and
   keep their decorators' relative paths unchanged.
3. **Shared helpers live in `_shared.py`**, never in `__init__.py` (avoids
   circular imports). Sub-modules do `from ._shared import …`.
4. **Re-export the full external surface.** If anything elsewhere does
   `from app.routers.<feature> import _helper`, `__init__.py` must re-export
   `_helper` (e.g. invoicing re-exports `_generate_invoice_pdf`,
   `_generate_peppol_xml`, `_invoice_number` for portal/gdpr/einvoice). Find
   them first: `grep -rn "from app.routers.<feature> import" app tests`.
5. **Composite routers** (some files export `router` *and* `public_router` —
   bookings, recurring, reviews, after_sales, quotes): re-export **both**.
6. `main.py` is **not** edited — `from app.routers import <feature>` and
   `<feature>.router` still resolve.

## Backend: large service → package

Identical pattern. `app/services/email.py` → `app/services/email/` with
`__init__.py` re-exporting **every** public function currently imported
elsewhere (enumerate with `grep -rn "from app.services.email import" app tests`),
internals split by theme (`transactional.py`, `marketing.py`, `trial.py`,
`nps.py`, `_core.py` for the low-level sender + wrappers). Tests that load a
service via `importlib.spec_from_file_location("…", ".../service.py")` must point
at a concrete module file, not the package dir.

## Models are exempt
`app/models/` stays flat — no file is large, and `models/__init__.py` re-exports
every model for Alembic discovery (load-bearing). Don't touch it.

---

## Frontend: large page → feature-local components/hooks

Frontend routes are already feature-first under `app/[locale]/(app)/<feature>/`.
The problem is only large `page.tsx` files that inline tabs, hooks, types, and
sub-components. Split **within the feature directory** using Next.js private
folders (`_`-prefixed → excluded from routing):

```
settings/
  page.tsx           # thin: layout + tab switch + composition only
  _components/        # AccountTab.tsx, TeamTab.tsx, BillingTab.tsx, …
  _hooks/useSettings.ts   # data fetching + mutations (via @/lib/api-client)
  _types.ts           # the interfaces that were inline
  page.module.scss    # unchanged
```

Rules:
- Move code, don't rewrite it — no prop or behavior changes.
- Keep using `@/lib/api-client`, `@/components/ui/*`, `@/components/app/*`.
- Shared cross-feature components still go in `frontend/src/components/`;
  `_components/` is only for components private to that one page/feature.

---

## Verification (every split, no exceptions — it's moves-only)

Backend:
```
cd backend
poetry run python -c "import app.main"                 # wiring intact
poetry run ruff check app/routers/<feature>/           # no F401/F811/F821
poetry run pytest --ignore=tests/test_customer_contacts.py \
  --ignore=tests/test_customer_tags.py \
  --ignore=tests/test_stock_transfers.py \
  --ignore=tests/test_trial.py -q                      # 2624 passed, 8 pre-existing
```
Plus the **route snapshot** must be unchanged: dump
`sorted((r.path, methods) for r in app.routes)` before and after — identical.

Frontend:
```
cd frontend && npx tsc --noEmit -p tsconfig.json       # 0 errors
```

Source-reading tests (`_read`/`_src` that assert on router source text) are
already **dir-aware**: when a `.py` becomes a package directory they concatenate
its modules, so the assertions keep working with no per-test change.

Commit each green split on its own: `refactor(structure): <feature> → package`.
No behavior change should appear in any diff — only moves + import fixups.
