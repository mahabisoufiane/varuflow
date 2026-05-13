"""Public waitlist endpoint — no auth required.

Admin endpoints are guarded by `ADMIN_API_KEY` — a shared secret sent via
the `X-Admin-Key` header. The waitlist lives outside any organization, so
there is no per-org role to check against.
"""
import csv
import io
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.waitlist import Waitlist
from app.services.audit import log_action

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


async def _require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    """Verify the X-Admin-Key header against current or previous keys.

    During a rotation window both ``ADMIN_API_KEY`` (new) and
    ``ADMIN_API_KEY_PREVIOUS`` (old) are accepted so scheduled jobs and
    downstream scripts don't 401 while operators hand out the new key.
    Every request that authenticates via the *previous* key emits an
    ``ADMIN_KEY_ROTATION_USED`` audit record so we can see who is still
    on the old key and follow up before clearing the env var.
    """
    current = getattr(settings, "ADMIN_API_KEY", "") or ""
    previous = getattr(settings, "ADMIN_API_KEY_PREVIOUS", "") or ""

    if not current and not previous:
        # Never accept a request when no key is configured — otherwise a
        # blank-string comparison would accept an empty header.
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if not x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key",
        )

    # constant-time comparison against each configured key
    accepted = None
    if current and secrets.compare_digest(x_admin_key, current):
        accepted = "current"
    elif previous and secrets.compare_digest(x_admin_key, previous):
        accepted = "previous"

    if accepted is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key",
        )

    if accepted == "previous":
        # Audit-log then commit in a nested try so a DB hiccup can't 500
        # a legitimate admin request. The caller's request continues on
        # the normal get_db session, so we flush here and defer commit
        # to the router function's own commit — for GETs that don't
        # commit, an explicit commit is needed to persist the audit row.
        try:
            await log_action(
                db,
                action="ADMIN_KEY_ROTATION_USED",
                org_id=None,
                actor_user_id=None,
                target_type="admin_api",
                target_id=None,
                request=request,
                extra={"path": request.url.path},
            )
            await db.commit()
        except Exception as e:  # noqa: BLE001
            log.error("admin_rotation_audit_failed err=%s", e)
            await db.rollback()


class WaitlistJoin(BaseModel):
    # Length caps match the DB columns (varchar(255)) so we reject oversize
    # payloads before hitting the database and producing an IntegrityError.
    email: str = Field(min_length=3, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


@router.post("", status_code=status.HTTP_201_CREATED)
async def join_waitlist(body: WaitlistJoin, db: AsyncSession = Depends(get_db)):
    # NO AUTH — intentionally public. This is the pre-signup waitlist entry
    # point; users have no account yet and therefore no JWT to attach.
    # Rule 2 exception: documented here as required by CLAUDE.md.
    # Idempotent insert: two simultaneous signups with the same email must
    # not both hit the DB constraint and produce a 500. ON CONFLICT keeps
    # the first row and silently ignores subsequent duplicates. Response is
    # uniform so an attacker can't enumerate existing waitlist entries.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = (
        pg_insert(Waitlist.__table__)
        .values(email=body.email, company_name=body.company_name)
        .on_conflict_do_nothing(index_elements=["email"])
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}


@router.get("", dependencies=[Depends(_require_admin)])
async def list_waitlist(db: AsyncSession = Depends(get_db), limit: int = 500, offset: int = 0):
    limit = max(1, min(limit, 1000))
    result = await db.scalars(
        select(Waitlist).order_by(Waitlist.created_at.desc()).limit(limit).offset(offset)
    )
    rows = result.all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": str(r.id),
                "email": r.email,
                "company_name": r.company_name,
                "welcome_sent": r.welcome_sent,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/export.csv", dependencies=[Depends(_require_admin)])
async def export_waitlist_csv(db: AsyncSession = Depends(get_db)):
    # Cap the export at 100k rows so a runaway signup bot cannot OOM the
    # worker when an admin clicks "Download CSV". If the real list ever
    # exceeds this, admins can paginate via the JSON endpoint instead.
    MAX_ROWS = 100_000
    result = await db.scalars(
        select(Waitlist)
        .order_by(Waitlist.created_at.desc())
        .limit(MAX_ROWS)
    )
    buf = io.StringIO()
    w = csv.writer(buf)

    # CSV formula-injection guard (CWE-1236): prefix any cell that starts with
    # =, +, -, @, TAB or CR with a single quote so Excel / LibreOffice / Sheets
    # treat it as literal text rather than evaluating it as a formula.
    def _safe(v) -> str:
        s = "" if v is None else str(v)
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + s
        return s

    w.writerow(["email", "company_name", "welcome_sent", "created_at"])
    for r in result.all():
        w.writerow([
            _safe(r.email),
            _safe(r.company_name or ""),
            _safe(r.welcome_sent),
            _safe(r.created_at.isoformat() if r.created_at else ""),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'},
    )
