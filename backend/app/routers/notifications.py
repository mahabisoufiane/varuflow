"""Push notification registration + preferences (v25).

Endpoints
─────────
POST /api/notifications/register     → idempotently register a device
POST /api/notifications/unregister   → forget a device
GET  /api/notifications/preferences  → current user's push toggles
PUT  /api/notifications/preferences  → update push toggles

Registration is an UPSERT keyed on the Expo push token: re-installing
the app on the same device produces the same token and should not
create duplicate rows (each duplicate would cause a double-delivered
push).
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.notifications import DeviceToken
from app.models.organization import OrganizationMember

router = APIRouter(prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(require_module("settings"))])


# ── Schemas ────────────────────────────────────────────────────────────────────

class DeviceRegisterIn(BaseModel):
    device_token: str = Field(..., min_length=1, max_length=255)
    platform: Literal["android", "ios", "huawei"]


class DeviceUnregisterIn(BaseModel):
    device_token: str = Field(..., min_length=1, max_length=255)


class PreferencesOut(BaseModel):
    push_stockout_enabled: bool
    push_overdue_enabled: bool
    push_portal_order_enabled: bool


class PreferencesIn(BaseModel):
    push_stockout_enabled: bool | None = None
    push_overdue_enabled: bool | None = None
    push_portal_order_enabled: bool | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Register or refresh a device token for the current user+org.

    UPSERT on ``token``: if the same physical device re-registers
    (app reinstall, OS upgrade, login swap) the row's ``user_id`` /
    ``org_id`` / ``platform`` are rewritten and ``updated_at`` bumps.
    """
    _, member = ctx
    stmt = (
        pg_insert(DeviceToken.__table__)
        .values(
            id=uuid.uuid4(),
            org_id=member.org_id,
            user_id=member.user_id,
            token=payload.device_token,
            platform=payload.platform,
        )
        .on_conflict_do_update(
            index_elements=["token"],
            set_={
                "org_id": member.org_id,
                "user_id": member.user_id,
                "platform": payload.platform,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "registered"}


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    payload: DeviceUnregisterIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a device token. Scoped to (org, user) so a user can only
    unregister their own devices."""
    _, member = ctx
    await db.execute(
        delete(DeviceToken).where(
            DeviceToken.token == payload.device_token,
            DeviceToken.user_id == member.user_id,
            DeviceToken.org_id == member.org_id,
        )
    )
    await db.commit()


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    ctx: tuple = Depends(get_current_member),
) -> PreferencesOut:
    _, member = ctx
    return PreferencesOut(
        push_stockout_enabled=member.push_stockout_enabled,
        push_overdue_enabled=member.push_overdue_enabled,
        push_portal_order_enabled=member.push_portal_order_enabled,
    )


@router.put("/preferences", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    _, member = ctx
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No preference changes supplied",
        )
    await db.execute(
        update(OrganizationMember)
        .where(OrganizationMember.id == member.id)
        .values(**updates)
    )
    await db.commit()
    await db.refresh(member)
    return PreferencesOut(
        push_stockout_enabled=member.push_stockout_enabled,
        push_overdue_enabled=member.push_overdue_enabled,
        push_portal_order_enabled=member.push_portal_order_enabled,
    )


# ── Item 21: nightly business summary ────────────────────────────────────────

from datetime import time as _time  # noqa: E402
from fastapi import Request  # noqa: E402

from app.models.organization import Organization, OrgRole  # noqa: E402
from app.services.audit import log_action  # noqa: E402
from app.middleware.plan_check import require_module


class NightlySummarySettingsIn(BaseModel):
    # Both optional so the caller can toggle just one field at a time.
    enabled: bool | None = None
    # "HH:MM" — validated below. Kept as a string on the wire so the
    # frontend can round-trip a <input type="time"> value unchanged.
    time: str | None = Field(None, max_length=5)


class NightlySummarySettingsOut(BaseModel):
    enabled: bool
    time: str  # "HH:MM"


@router.get("/nightly-summary", response_model=NightlySummarySettingsOut)
async def get_nightly_summary_settings(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> NightlySummarySettingsOut:
    _, member = ctx
    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return NightlySummarySettingsOut(
        enabled=bool(org.nightly_summary_enabled),
        time=org.nightly_summary_time.strftime("%H:%M"),
    )


@router.put("/nightly-summary", response_model=NightlySummarySettingsOut)
async def update_nightly_summary_settings(
    body: NightlySummarySettingsIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> NightlySummarySettingsOut:
    """Owner-only: toggle nightly summary + set delivery time.

    Time is clamped to the 15-minute scheduler cadence by rounding
    down to the nearest quarter-hour. This keeps the "configured time
    falls in window" check deterministic — otherwise a user who set
    "07:23" would wait until 07:30 without a clear reason why.
    """
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only org owners can change nightly summary settings.",
        )
    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.enabled is not None:
        org.nightly_summary_enabled = bool(body.enabled)
    if body.time is not None:
        try:
            hh_str, mm_str = body.time.split(":", 1)
            hh, mm = int(hh_str), int(mm_str)
            if not (0 <= hh < 24 and 0 <= mm < 60):
                raise ValueError
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, detail="time must be HH:MM",
            )
        # Snap to 15-min grid so the scheduler fire-window logic is
        # deterministic (see nightly_summary_sweep).
        mm_snapped = (mm // 15) * 15
        org.nightly_summary_time = _time(hh, mm_snapped)

    await log_action(
        db,
        action="NIGHTLY_SUMMARY_SETTINGS_UPDATED",
        org_id=member.org_id,
        actor_user_id=member.user_id,
        target_type="organization",
        target_id=str(member.org_id),
        request=request,
        extra={
            "enabled": org.nightly_summary_enabled,
            "time": org.nightly_summary_time.strftime("%H:%M"),
        },
    )
    await db.commit()
    await db.refresh(org)

    return NightlySummarySettingsOut(
        enabled=bool(org.nightly_summary_enabled),
        time=org.nightly_summary_time.strftime("%H:%M"),
    )
