"""External integrations: Fortnox OAuth2, AI assistant."""
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.organization import FortnoxOAuthState, OrgPlan, OrgRole, Organization
from app.models.invoicing import Invoice, InvoiceStatus
from app.services.crypto import decrypt_token, encrypt_token
from app.services.plan_limits import RESOURCE_AI_CALLS_PER_DAY, LimitExceededError, check_limit

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

FORTNOX_AUTH_URL  = "https://apps.fortnox.se/oauth-v1/auth"
FORTNOX_TOKEN_URL = "https://apps.fortnox.se/oauth-v1/token"
FORTNOX_API_BASE  = "https://api.fortnox.se/3"
FORTNOX_SCOPES    = "bookkeeping invoice customer"

# ── In-process AI call counter (single-worker, resets at midnight UTC) ────────
# Keyed by (org_id_str, iso_date) → call_count. Stale entries are evicted when
# the key date changes, bounding memory growth to ~1 entry per active org.
_ai_call_counts: dict[tuple[str, str], int] = {}


def _check_ai_call_limit(org_id: uuid.UUID, plan: OrgPlan) -> None:
    """Raise HTTP 403 when the org has exhausted its daily AI chat allowance."""
    today = date.today().isoformat()
    key = (str(org_id), today)
    current = _ai_call_counts.get(key, 0)
    try:
        check_limit(plan, RESOURCE_AI_CALLS_PER_DAY, current)
    except LimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAN_LIMIT_EXCEEDED",
                "resource": RESOURCE_AI_CALLS_PER_DAY,
                "current_plan": plan.value,
                "limit": exc.limit,
                "current": exc.current,
            },
        )
    _ai_call_counts[key] = current + 1

FORTNOX_AUTH_URL  = "https://apps.fortnox.se/oauth-v1/auth"
FORTNOX_TOKEN_URL = "https://apps.fortnox.se/oauth-v1/token"
FORTNOX_API_BASE  = "https://api.fortnox.se/3"
FORTNOX_SCOPES    = "bookkeeping invoice customer"

# CSRF nonce expiry — Fortnox should redirect back within this window
_OAUTH_STATE_TTL_MINUTES = 10


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _require_owner_or_admin(ctx: tuple) -> None:
    """Fortnox holds the tenant's full accounting data — connect/disconnect
    and manual syncs must be gated to owners and admins so a rogue MEMBER
    cannot sever the integration or trigger an unexpected data push."""
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage integrations",
        )


# ── Status ────────────────────────────────────────────────────────────────────

class FortnoxStatus(BaseModel):
    connected:    bool
    token_expiry: Optional[datetime] = None


@router.get("/fortnox/status", response_model=FortnoxStatus)
async def fortnox_status(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, _org_id(ctx))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return FortnoxStatus(
        connected=bool(org.fortnox_access_token),
        token_expiry=org.fortnox_token_expiry,
    )


# ── Connect (OAuth2 initiation) ───────────────────────────────────────────────

@router.get("/fortnox/connect")
async def fortnox_connect(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    """Start Fortnox OAuth2 flow.

    Generates a cryptographically random nonce and stores it in the DB.
    The nonce is passed as the OAuth2 `state` parameter and validated on
    callback to prevent CSRF attacks.
    """
    _require_owner_or_admin(ctx)
    if not settings.FORTNOX_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Fortnox not configured — add FORTNOX_CLIENT_ID")
    if not settings.FORTNOX_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Fortnox not configured — add FORTNOX_REDIRECT_URI")

    # Clean up expired nonces for this org before creating a new one
    await db.execute(
        delete(FortnoxOAuthState).where(
            FortnoxOAuthState.org_id == _org_id(ctx),
        )
    )

    nonce      = secrets.token_hex(32)          # 64-char hex, 256-bit entropy
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OAUTH_STATE_TTL_MINUTES)
    db.add(FortnoxOAuthState(nonce=nonce, org_id=_org_id(ctx), expires_at=expires_at))
    await db.commit()

    params = {
        "client_id":     settings.FORTNOX_CLIENT_ID,
        "redirect_uri":  settings.FORTNOX_REDIRECT_URI,
        "scope":         FORTNOX_SCOPES,
        "state":         nonce,                 # CSRF nonce — NOT the org_id
        "access_type":   "offline",
        "response_type": "code",
    }
    return RedirectResponse(f"{FORTNOX_AUTH_URL}?{urlencode(params)}")


# ── Callback (OAuth2 token exchange) ──────────────────────────────────────────

@router.get("/fortnox/callback")
async def fortnox_callback(
    code:  str = Query(...),
    state: str = Query(...),
    db:    AsyncSession = Depends(get_db),
):
    """Exchange the Fortnox authorisation code for an access token.

    The `state` parameter is a one-time CSRF nonce created in /connect and
    stored in the DB. We validate and delete it here so it cannot be replayed.
    """
    if not settings.FORTNOX_CLIENT_ID or not settings.FORTNOX_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Fortnox not configured")

    # ── Validate CSRF nonce ───────────────────────────────────────────────────
    # Atomic consume: DELETE … RETURNING guarantees that if two callbacks
    # arrive with the same nonce (e.g. user double-clicks a link or an
    # attacker replays), at most one succeeds. Serialised by Postgres via
    # the row lock acquired by DELETE.
    from sqlalchemy import delete as _delete
    consumed = await db.execute(
        _delete(FortnoxOAuthState)
        .where(FortnoxOAuthState.nonce == state)
        .returning(FortnoxOAuthState.org_id, FortnoxOAuthState.expires_at)
    )
    row = consumed.one_or_none()
    await db.commit()
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state. Please try connecting again.")

    now = datetime.now(timezone.utc)
    state_expiry = row.expires_at
    if state_expiry.tzinfo is None:
        state_expiry = state_expiry.replace(tzinfo=timezone.utc)
    if state_expiry < now:
        raise HTTPException(status_code=400, detail="OAuth state expired. Please try connecting again.")

    org_id = row.org_id

    # Timeout is mandatory — without it a hung Fortnox endpoint can pin a
    # worker forever. 15s is plenty for an OAuth token exchange.
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            FORTNOX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.FORTNOX_REDIRECT_URI,
                "client_id": settings.FORTNOX_CLIENT_ID,
                "client_secret": settings.FORTNOX_CLIENT_SECRET,
            },
        )
        if resp.status_code != 200:
            # Don't echo Fortnox's response body to the client — it may contain
            # the authorisation code or other sensitive fields. Log server-side
            # for debugging and return a generic message.
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "fortnox token exchange failed",
                extra={"org_id": str(org_id), "status": resp.status_code},
            )
            raise HTTPException(status_code=502, detail="Fortnox authorisation failed. Please try again.")
        data = resp.json()

    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.fortnox_access_token  = encrypt_token(data["access_token"])
    org.fortnox_refresh_token = encrypt_token(data.get("refresh_token"))
    expires_in = data.get("expires_in", 3600)
    org.fortnox_token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    await db.commit()

    # Redirect back to the frontend settings page.
    # FRONTEND_URL is set in Railway Variables (https://varuflow.vercel.app).
    # Never hard-code localhost here — the callback runs on Railway, not the dev machine.
    return RedirectResponse(f"{settings.FRONTEND_URL}/settings?tab=integrations&connected=1")


# ── Disconnect ────────────────────────────────────────────────────────────────

@router.delete("/fortnox/disconnect")
async def fortnox_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org = await db.get(Organization, _org_id(ctx))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.fortnox_access_token = None
    org.fortnox_refresh_token = None
    org.fortnox_token_expiry = None
    await db.commit()
    return {"disconnected": True}


# ── Token refresh helper ───────────────────────────────────────────────────────

async def _get_valid_token(org: Organization, db: AsyncSession) -> str:
    if not org.fortnox_access_token:
        raise HTTPException(status_code=400, detail="Fortnox not connected")

    # Refresh if expiring within 5 minutes
    if org.fortnox_token_expiry and org.fortnox_token_expiry < datetime.now(timezone.utc) + timedelta(minutes=5):
        if not org.fortnox_refresh_token:
            raise HTTPException(status_code=400, detail="Fortnox token expired — reconnect")
        refresh_plaintext = decrypt_token(org.fortnox_refresh_token)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                FORTNOX_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_plaintext,
                    "client_id": settings.FORTNOX_CLIENT_ID,
                    "client_secret": settings.FORTNOX_CLIENT_SECRET,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                org.fortnox_access_token  = encrypt_token(data["access_token"])
                org.fortnox_refresh_token = encrypt_token(data.get("refresh_token")) or org.fortnox_refresh_token
                org.fortnox_token_expiry  = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
            else:
                # Refresh failed — typically because the refresh_token was
                # revoked from the Fortnox side (user disconnected the app,
                # password changed, 60-day sliding window elapsed). Clear
                # the stored tokens AND commit immediately so the next API
                # call surfaces a clean "reconnect" prompt. Raising before
                # committing was a silent bug: SQLAlchemy rolls back the
                # open transaction on HTTPException, so the token-clear
                # was discarded every time and the user got stuck in an
                # infinite "token expired" loop (same dead tokens tried
                # again on every sync click). Commit BEFORE raising.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "fortnox refresh failed | org_id=%s status=%s",
                    org.id, resp.status_code,
                )
                org.fortnox_access_token  = None
                org.fortnox_refresh_token = None
                org.fortnox_token_expiry  = None
                try:
                    await db.commit()
                except Exception:
                    # Persisting the clear is best-effort — if the commit
                    # itself fails (db down, etc.) fall back to the old
                    # behaviour and let the caller retry next time.
                    await db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Fortnox token expired — reconnect",
                )

    return decrypt_token(org.fortnox_access_token)


def _fortnox_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ── Sync invoices → Fortnox ───────────────────────────────────────────────────

class SyncResult(BaseModel):
    synced: int
    errors: list[str]


@router.post("/fortnox/sync-invoices", response_model=SyncResult)
async def sync_invoices_to_fortnox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    _require_owner_or_admin(ctx)
    from sqlalchemy.orm import selectinload
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.idempotency import IdempotencyKey
    org_id = _org_id(ctx)
    org = await db.get(Organization, org_id)
    token = await _get_valid_token(org, db)
    await db.commit()  # save refreshed token

    _SYNC_ENDPOINT = "integrations.fortnox_sync_invoice"

    # Exclude invoices already pushed to Fortnox on a prior call. Without
    # this, clicking "Sync" twice silently creates duplicate invoices in
    # Fortnox (the upstream API does not dedupe on YourReference), leading
    # to double-bookkeeping the customer has to unwind by hand.
    #
    # Do the NOT-IN filter in SQL rather than loading every historical
    # key into Python memory. The sync-invoice idempotency markers are
    # permanent (see scheduler._PERMANENT_IDEMPOTENCY_ENDPOINTS) so after
    # a year of use a tenant can easily accumulate 10k+ keys — the old
    # "fetch all keys + set-difference in Python + fetch 50 + N invoice
    # rows" pattern was O(N) memory and DB IO on every click. A correlated
    # subquery lets Postgres use the
    # (org_id, endpoint, key) unique index and short-circuit. Keys are
    # stored as str(invoice.id) so cast the UUID column to text to match.
    from sqlalchemy import cast, String as _String
    synced_key_subq = (
        select(IdempotencyKey.key).where(
            IdempotencyKey.org_id == org_id,
            IdempotencyKey.endpoint == _SYNC_ENDPOINT,
        )
    )

    # Fetch sent/overdue invoices not yet synced
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.PAID]),
            cast(Invoice.id, _String).not_in(synced_key_subq),
        )
        .order_by(Invoice.created_at)
        .limit(50)
    )
    invoices = list(result.scalars().all())

    synced = 0
    errors = []

    async with httpx.AsyncClient(timeout=30) as client:
        for inv in invoices:
            try:
                rows = [
                    {
                        "Description": li.description,
                        "DeliveredQuantity": float(li.quantity),
                        "Price": float(li.unit_price),
                        "VAT": int(li.tax_rate),
                    }
                    for li in inv.line_items
                ]
                payload = {
                    "Invoice": {
                        "InvoiceDate": str(inv.issue_date),
                        "DueDate": str(inv.due_date),
                        "CustomerName": inv.customer.company_name,
                        "CustomerNumber": str(inv.customer.id)[:10],
                        "InvoiceRows": rows,
                        "Currency": "SEK",
                        "YourReference": inv.invoice_number,
                    }
                }
                resp = await client.post(
                    f"{FORTNOX_API_BASE}/invoices",
                    json=payload,
                    headers=_fortnox_headers(token),
                )
                if resp.status_code in (200, 201):
                    # Record the successful sync so a retry of this
                    # endpoint won't push the same invoice again.
                    # ON CONFLICT DO NOTHING so a concurrent sync-run
                    # on the same invoice can't raise IntegrityError
                    # and abort the batch.
                    ins = (
                        pg_insert(IdempotencyKey.__table__)
                        .values(
                            org_id=org_id,
                            endpoint=_SYNC_ENDPOINT,
                            key=str(inv.id),
                            target_id=str(inv.id),
                        )
                        .on_conflict_do_nothing(
                            index_elements=["org_id", "endpoint", "key"]
                        )
                    )
                    await db.execute(ins)
                    # Commit the idempotency marker immediately. Deferring
                    # it to the end-of-batch commit lets a client
                    # disconnect, worker crash, or later Exception roll
                    # back the whole transaction — Fortnox already has
                    # the invoice (upstream 201), but our records don't,
                    # so the next /sync-invoices click pushes every
                    # already-synced invoice again and Fortnox creates
                    # duplicates (no dedupe on YourReference).
                    await db.commit()
                    synced += 1
                else:
                    # Don't echo Fortnox's body to the client \u2014 it has been
                    # observed to include account details in error paths. Log
                    # server-side and return a generic per-row status.
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        "fortnox invoice sync row failed",
                        extra={
                            "org_id": str(org_id),
                            "invoice_number": inv.invoice_number,
                            "status": resp.status_code,
                        },
                    )
                    errors.append(f"{inv.invoice_number}: upstream error {resp.status_code}")
            except Exception as e:
                # Keep a short, generic per-row message in the response;
                # full traceback goes to server logs only.
                import logging as _logging
                _logging.getLogger(__name__).exception(
                    "fortnox invoice sync row exception",
                    extra={"org_id": str(org_id), "invoice_number": inv.invoice_number},
                )
                errors.append(f"{inv.invoice_number}: sync failed")

    await db.commit()
    return SyncResult(synced=synced, errors=errors)


# ── Sync customers ← Fortnox ──────────────────────────────────────────────────

@router.post("/fortnox/sync-customers", response_model=SyncResult)
async def sync_customers_from_fortnox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    _require_owner_or_admin(ctx)
    from app.models.invoicing import Customer

    org_id = _org_id(ctx)
    org = await db.get(Organization, org_id)
    token = await _get_valid_token(org, db)
    await db.commit()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FORTNOX_API_BASE}/customers",
            headers=_fortnox_headers(token),
        )
        if resp.status_code != 200:
            # Don't return Fortnox's raw error text — may leak internal
            # customer data or tokens in edge cases.
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "fortnox customers sync failed",
                extra={"org_id": str(org_id), "status": resp.status_code},
            )
            raise HTTPException(status_code=502, detail="Fortnox sync failed. Please try again.")
        customers_data = resp.json().get("Customers", [])

    # Cap per-call work — Fortnox may return thousands of customers but we
    # hold an open DB transaction for the whole loop (with one SELECT per
    # customer). Process at most MAX_PER_CALL per request; users can call
    # again to continue syncing. Protects workers from being pinned.
    MAX_PER_CALL = 500
    if len(customers_data) > MAX_PER_CALL:
        customers_data = customers_data[:MAX_PER_CALL]

    synced = 0
    errors = []

    for fc in customers_data:
        try:
            # Fortnox does not enforce our column-length caps, so defensively
            # clamp every string to the DB column size. An oversize field
            # would otherwise raise IntegrityError mid-loop and abort the
            # entire commit, losing all successfully parsed rows.
            def _clip(v: str | None, n: int) -> str | None:
                if v is None:
                    return None
                s = str(v).strip()
                return s[:n] if s else None

            company_name = _clip(fc.get("Name"), 255)
            if not company_name:
                continue

            # Fortnox occasionally returns "N/A" or malformed values in the
            # Email field. Reject anything that isn't a plausible address —
            # we'd rather skip the field than poison our own mail-sending.
            email_raw = (fc.get("Email") or "").strip().lower()
            email = None
            if email_raw and "@" in email_raw and "." in email_raw.split("@")[-1]:
                email = email_raw[:255]

            # Dedupe by company_name. The Customer table has no UNIQUE
            # constraint on (org_id, company_name) — two legitimately-
            # distinct customers can share a name (e.g. different branches
            # of the same franchise, or a manually-added duplicate). Cap
            # the lookup to 1 row so `db.scalar()` cannot raise
            # MultipleResultsFound and knock out the import of this
            # Fortnox customer via the generic "import failed" branch
            # below.
            existing = await db.scalar(
                select(Customer).where(
                    Customer.org_id == org_id,
                    Customer.company_name == company_name,
                ).limit(1)
            )
            if existing:
                continue

            addr1 = fc.get("Address1") or ""
            addr2 = fc.get("Address2") or ""
            address = (addr1 + (" " + addr2 if addr2 else "")).strip() or None

            customer = Customer(
                org_id=org_id,
                company_name=company_name,
                org_number=_clip(fc.get("OrganisationNumber"), 20),
                email=email,
                phone=_clip(fc.get("Phone1"), 50),
                address=_clip(address, 500),
            )
            db.add(customer)
            synced += 1
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).exception(
                "fortnox customer import row exception",
                extra={"org_id": str(org_id)},
            )
            errors.append(f"{fc.get('Name', '?')}: import failed")

    await db.commit()
    return SyncResult(synced=synced, errors=errors)


# ── AI Assistant ──────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    # Cap user input to control OpenAI token cost and prevent prompt-stuffing
    # abuse. 2000 chars is plenty for a conversational query.
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str


@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(
    body: ChatMessage,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI not configured — add OPENAI_API_KEY")

    from sqlalchemy import func
    from app.models.inventory import Product, StockLevel
    from app.models.invoicing import Invoice, InvoiceStatus, Payment

    org_id = _org_id(ctx)

    # ── Per-day AI call limit ─────────────────────────────────────────────────
    _ai_org = await db.get(Organization, org_id)
    if _ai_org:
        _check_ai_call_limit(org_id, _ai_org.plan)

    # Build context
    # Low-stock list for GPT-4o context. Aggregate quantity across ALL
    # warehouses per product and compare against Product.reorder_level —
    # the canonical low-stock signal used by _check_low_stock, the weekly
    # digest, and the dashboard KPI. The previous version compared against
    # StockLevel.min_threshold, a column no endpoint ever writes to (it
    # stays at its 0 default), so the HAVING `min_threshold > 0` filter
    # silently excluded every product and the AI was always told "no low
    # stock" — fabricating reassurance to the owner and missing the one
    # signal the whole product is built around.
    low_stock = await db.execute(
        select(
            Product.name,
            Product.reorder_level,
            func.coalesce(func.sum(StockLevel.quantity), 0).label("quantity"),
        )
        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
        .where(
            Product.org_id == org_id,
            Product.is_active == True,  # noqa: E712
            Product.reorder_level > 0,
        )
        .group_by(Product.id, Product.name, Product.reorder_level)
        .having(
            func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level,
        )
        .limit(10)
    )
    low_stock_rows = low_stock.all()

    # Overdue invoices for GPT-4o context. Show the REMAINING balance
    # (invoice total minus payments already recorded) — not the gross
    # total. An invoice with 10 000 SEK face value and a 7 000 SEK partial
    # bank transfer is overdue for 3 000 SEK; telling the AI "customer
    # owes 10 000" leads to wrong reminders, wrong prioritisation, and
    # wrong cash-flow summaries. Matches the remaining-balance logic in
    # analytics.get_overview and ai_engine.get_action_cards.
    paid_subq = (
        select(
            Payment.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("paid"),
        )
        # Scope to the caller's org — defence-in-depth. Payment.invoice_id
        # is a FK to an Invoice that already carries org_id, so in practice
        # the outer `Invoice.org_id == org_id` filter isolates tenants,
        # but matching the pattern used in analytics.get_overview and
        # ai_engine.get_action_cards keeps the subquery locally correct
        # regardless of which outer join/filter it gets combined with.
        .where(Payment.org_id == org_id)
        .group_by(Payment.invoice_id)
        .subquery()
    )
    remaining_expr = Invoice.total_sek - func.coalesce(paid_subq.c.paid, 0)
    # Use the same SENT/OVERDUE + `due_date < today` criterion as
    # analytics.get_overview, ai_engine.get_action_cards and the
    # /aging report. Filtering on `status == OVERDUE` alone hid every
    # invoice that was past its due date but still in SENT — the
    # `mark_overdue` bulk-update only runs when the cron or the owner's
    # "Mark overdue" button fires, so a freshly-past-due invoice stays
    # SENT for up to 24 h. The dashboard/cards show it, the chat doesn't,
    # and the AI gave factually wrong answers ("You have no overdue
    # invoices") while the dashboard next to it listed several.
    from datetime import date as _date
    _today = _date.today()
    overdue = await db.execute(
        select(
            Invoice.invoice_number,
            remaining_expr.label("remaining"),
            Invoice.due_date,
        )
        .outerjoin(paid_subq, paid_subq.c.invoice_id == Invoice.id)
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
            Invoice.due_date < _today,
            remaining_expr > 0,
        )
        .order_by(Invoice.due_date.asc())
        .limit(10)
    )
    overdue_rows = overdue.all()

    revenue_result = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek), 0))
        .where(Invoice.org_id == org_id, Invoice.status == InvoiceStatus.PAID)
    )

    context = f"""You are the AI intelligence layer of Varuflow — a B2B SaaS platform for Nordic wholesale businesses.
You are a proactive, context-aware business co-pilot specializing in inventory, invoicing, and cash flow.

LIVE BUSINESS DATA:
- Total paid revenue (all time): {float(revenue_result or 0):,.0f} SEK
- Low stock alerts ({len(low_stock_rows)}): {', '.join(f"{r.name} ({int(r.quantity)} units, reorder at {int(r.reorder_level)})" for r in low_stock_rows) or 'none'}
- Overdue invoices ({len(overdue_rows)}): {', '.join(f"{r.invoice_number} ({float(r.remaining):,.0f} SEK remaining, due {r.due_date})" for r in overdue_rows) or 'none'}

YOUR CAPABILITIES:
1. INVENTORY INTELLIGENCE — stockout risk, dead stock, purchase order drafts, demand forecasting
2. MARGIN OPTIMIZER — gross margin analysis, price suggestions, bundle opportunities
3. WORKFLOW AUTOMATION — detect anomalies, classify problems, prescribe ranked actions
4. CUSTOMER INTELLIGENCE — RFM segmentation, late payer alerts, churn detection, win-back campaigns

OUTPUT FORMAT for recommendations:
Always structure your response as: [DIAGNOSIS] → [INSIGHT] → [ACTION] → [IMPACT]
Example: "STOCK_RISK detected for Kaffe Mellanrost → 4 units left, 3/day velocity, 5-day lead time → Draft PO for 45 units → Prevents ~4,500 SEK stockout loss"

GUARDRAILS:
- Never suggest price changes >15% without noting human approval required
- Add ⚠️ LOW CONFIDENCE if data is insufficient
- Always cite the actual data above when making recommendations
- Respond in the same language as the user (Swedish or English or Norwegian or Danish)"""

    try:
        import openai
        # Hard client-side timeout: a hung upstream would otherwise tie up
        # a worker for minutes. 20 s is generous for a 500-token gpt-4o
        # completion; most respond in 3–6 s.
        client_ai = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=20.0,
            max_retries=0,
        )
        resp = await client_ai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": body.message},
            ],
            max_tokens=500,
            temperature=0.4,
        )
        reply = resp.choices[0].message.content or "No response"
    except Exception as e:
        # Never leak upstream OpenAI error text to the client — it can expose
        # model/account details or internal org metadata in rare error paths.
        import logging as _logging
        _logging.getLogger(__name__).error(
            "ai_chat openai call failed",
            extra={"org_id": str(org_id), "error": str(e)[:500]},
        )
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable")

    return ChatResponse(reply=reply)


# ── AI Contract Drafting ──────────────────────────────────────────────────────
# GPT-4o only in integrations.py — per project CLAUDE.md rule 10.

class ContractDraftIn(BaseModel):
    customer_id: str
    contract_type: str = "service_agreement"  # service_agreement | nda | supply | retainer
    key_terms: str = ""  # Free text: scope, payment terms, special clauses the user wants included


class ContractDraftResponse(BaseModel):
    draft_body: str
    contract_type: str
    customer_name: str


@router.post(
    "/api/ai/contracts/draft",
    response_model=ContractDraftResponse,
    summary="Draft a business contract using GPT-4o",
)
async def draft_contract(
    body: ContractDraftIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI not configured — add OPENAI_API_KEY")

    from app.models.invoicing import Customer
    org_id = _org_id(ctx)

    # Load customer context
    cust_r = await db.execute(
        select(Customer).where(
            Customer.id == __import__("uuid").UUID(body.customer_id),
            Customer.org_id == org_id,
        )
    )
    customer = cust_r.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    type_labels = {
        "service_agreement": "Service Agreement",
        "nda": "Non-Disclosure Agreement (NDA)",
        "supply": "Supply / Procurement Agreement",
        "retainer": "Retainer Agreement",
    }
    contract_label = type_labels.get(body.contract_type, body.contract_type.replace("_", " ").title())

    system_prompt = f"""You are a commercial contract drafting assistant for Nordic B2B businesses.
Draft a professional {contract_label} in plain business language.
The contract should be complete, legally structured (recitals, definitions, obligations, payment,
confidentiality, termination, governing law), and ready for legal review.
Use Swedish law / Nordic commercial standards unless the key terms specify otherwise.
Use Markdown for structure (## Headings, numbered clauses).
Output ONLY the contract text — no preamble, no meta-commentary."""

    user_prompt = f"""Draft a {contract_label} with the following parties and terms:

PARTIES:
- Supplier / Service Provider: [ORGANIZATION_NAME] (to be filled by user)
- Client / Counterparty: {customer.company_name}
  - Org. number: {customer.org_number or 'N/A'}
  - Address: [encrypted — not included]

KEY TERMS PROVIDED BY USER:
{body.key_terms or 'Standard terms — use typical Nordic B2B defaults.'}

Produce the full contract draft."""

    try:
        import openai
        client_ai = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0,
            max_retries=0,
        )
        resp = await client_ai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        draft_body = resp.choices[0].message.content or "Draft unavailable"
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "draft_contract openai call failed",
            extra={"org_id": str(org_id), "error": str(e)[:500]},
        )
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable")

    return ContractDraftResponse(
        draft_body=draft_body,
        contract_type=contract_label,
        customer_name=customer.company_name,
    )
